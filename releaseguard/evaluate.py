"""Eval Set 실행. 대상 저장소의 커밋을 하나씩 분석해 정답과 비교한다.

정답은 두 종류다.
- 자동 정답: 같은 커밋에서 실제로 수정·추가된 테스트 파일 → 관련 테스트 탐색(3단계)과 에이전트 추천 테스트의 precision/recall
- 수기 정답: eval/cases.yaml의 expected (기대 판정) → 판정 정확도, 과잉·과소 경고

에이전트는 비용 때문에 수기 정답이 있는 커밋에만 돌린다.
"""

from pathlib import Path

import yaml

from .analyze import ImpactRunner, analyze
from .classify import RuleSet
from .decide import SEVERITY
from .git_ops import run_git


def load_cases(path: Path) -> tuple[Path, dict[str, dict]]:
    """(대상 저장소 경로, {짧은 sha: 라벨}). 저장소 경로는 cases 파일 위치 기준."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    repo = (path.parent / raw["repo"]).resolve()
    return repo, {str(c["sha"]): c for c in raw.get("cases", [])}


def list_commits(repo: Path) -> list[tuple[str, str]]:
    """부모가 있는 커밋만 (오래된 순). 첫 커밋은 비교 대상이 없어서 뺀다."""
    out = run_git(repo, "log", "--reverse", "--min-parents=1", "--format=%H%x09%s")
    return [tuple(line.split("\t", 1)) for line in out.splitlines()]


def _label_for(sha: str, labels: dict[str, dict]) -> dict | None:
    return next((c for short, c in labels.items() if sha.startswith(short)), None)


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def evaluate(cases_path: Path, ruleset: RuleSet, run_impact: ImpactRunner | None = None) -> dict:
    repo, labels = load_cases(cases_path)
    rows = []
    for sha, subject in list_commits(repo):
        label = _label_for(sha, labels)
        result = analyze(repo, f"{sha}~1", sha, ruleset, run_impact if label else None)
        actual = sorted({f["path"] for f in result["changed_files"] if f["category"] == "test" and f["status"] != "D"})
        predicted = sorted({t["path"] for c in result["coverage"] for t in c["tests"]})
        row = {
            "sha": sha[:7],
            "subject": subject,
            "by_category": result["summary"]["by_category"],
            "decision": result["decision"],
            "rules": [f["rule_id"] for f in result["findings"]],
            "has_source": bool(result["coverage"]),
            "actual_tests": actual,
            "predicted_tests": predicted,
            "expected": label["expected"] if label else None,
            "labeled_by": label.get("labeled_by") if label else None,
            "note": label.get("note") if label else None,
            "agent": None,
        }
        if result["impact"] is not None or result["agent_error"]:
            row["agent"] = _agent_row(result, actual)
        rows.append(row)
    return {"repo": str(repo), "rules_version": ruleset.version, "metrics": metrics(rows), "rows": rows}


def _agent_row(result: dict, actual: list[str]) -> dict:
    if result["agent_error"]:
        return {"error": result["agent_error"]}
    impact, meta = result["impact"], result["agent"]
    items = [i for key in ("impacts", "risks", "recommended_tests") for i in impact[key]]
    return {
        "error": None,
        "llm_calls": meta["llm_calls"],
        "tool_calls": meta["tool_calls"],
        "input_tokens": meta["input_tokens"],
        "output_tokens": meta["output_tokens"],
        "seconds": meta["seconds"],
        "items": len(items),
        "verified_items": sum(i["verified"] for i in items),
        "high_risks": sum(r["level"] == "HIGH" for r in impact["risks"]),
        "recommended_existing": sorted({t["target"] for t in impact["recommended_tests"] if t["kind"] == "run_existing"}),
        "add_new": len([t for t in impact["recommended_tests"] if t["kind"] == "add_new"]),
        "actual_tests": actual,
        # 위험 내용이 후속 수정과 맞는지 사람이 대조할 수 있게 남긴다
        "risks": [{k: r[k] for k in ("level", "title", "verified", "evidence")} for r in impact["risks"]],
        "tools_used": [t["name"] for t in meta["tool_log"]],
    }


def _retrieval(pairs: list[tuple[list[str], list[str]]]) -> dict:
    """(예측, 실제) 목록의 micro precision/recall. 실제 정답이 빈 커밋은 정답을 알 수 없어서 뺀다."""
    pairs = [(set(p), set(a)) for p, a in pairs if a]
    tp = sum(len(p & a) for p, a in pairs)
    return {
        "commits": len(pairs),
        "precision": _ratio(tp, sum(len(p) for p, _ in pairs)),
        "recall": _ratio(tp, sum(len(a) for _, a in pairs)),
    }


def metrics(rows: list[dict]) -> dict:
    n = len(rows)
    rule_counts: dict[str, int] = {}
    for r in rows:
        for rule in r["rules"]:
            rule_counts[rule] = rule_counts.get(rule, 0) + 1
    decisions: dict[str, int] = {}
    for r in rows:
        decisions[r["decision"]] = decisions.get(r["decision"], 0) + 1

    labeled = [r for r in rows if r["expected"]]
    confusion: dict[str, int] = {}
    for r in labeled:
        key = f"{r['expected']} → {r['decision']}"
        confusion[key] = confusion.get(key, 0) + 1

    out = {
        "commits": n,
        "decisions": dict(sorted(decisions.items())),
        "rule_fire_rate": {k: _ratio(v, n) for k, v in sorted(rule_counts.items())},
        "test_retrieval": _retrieval([(r["predicted_tests"], r["actual_tests"]) for r in rows if r["has_source"]]),
        "decision": {
            "labeled": len(labeled),
            "accuracy": _ratio(sum(r["decision"] == r["expected"] for r in labeled), len(labeled)),
            "over_warning": sum(SEVERITY[r["decision"]] > SEVERITY[r["expected"]] for r in labeled),
            "under_warning": sum(SEVERITY[r["decision"]] < SEVERITY[r["expected"]] for r in labeled),
            "confusion": dict(sorted(confusion.items())),
        },
        "agent": None,
    }

    ran = [r["agent"] for r in rows if r["agent"]]
    ok = [a for a in ran if not a["error"]]
    if ran:
        avg = lambda key: round(sum(a[key] for a in ok) / len(ok), 1) if ok else None  # noqa: E731
        out["agent"] = {
            "runs": len(ran),
            "errors": len(ran) - len(ok),
            "avg_llm_calls": avg("llm_calls"),
            "avg_tool_calls": avg("tool_calls"),
            "avg_input_tokens": avg("input_tokens"),
            "avg_output_tokens": avg("output_tokens"),
            "avg_seconds": avg("seconds"),
            "verified_item_ratio": _ratio(sum(a["verified_items"] for a in ok), sum(a["items"] for a in ok)),
            "high_risks": sum(a["high_risks"] for a in ok),
            "test_retrieval": _retrieval([(a["recommended_existing"], a["actual_tests"]) for a in ok]),
        }
    return out


def to_markdown(ev: dict) -> str:
    m = ev["metrics"]
    tr, d = m["test_retrieval"], m["decision"]
    lines = [
        "# ReleaseGuard Eval 결과",
        "",
        f"- 저장소: `{ev['repo']}` · 커밋 {m['commits']}개 · 분류 규칙 v{ev['rules_version']}",
        f"- 판정 분포: " + ", ".join(f"{k} {v}" for k, v in m["decisions"].items()),
        f"- 규칙 발동률: " + ", ".join(f"{k} {v:.0%}" for k, v in m["rule_fire_rate"].items()),
        f"- 관련 테스트 탐색 (규칙, 테스트가 함께 바뀐 커밋 {tr['commits']}개): precision {tr['precision']}, recall {tr['recall']}",
        f"- 판정 (수기 정답 {d['labeled']}개): 정확도 {d['accuracy']}, 과잉 경고 {d['over_warning']}, 과소 경고 {d['under_warning']}",
    ]
    for k, v in d["confusion"].items():
        lines.append(f"  - {k}: {v}")
    if a := m["agent"]:
        atr = a["test_retrieval"]
        lines += [
            f"- 에이전트 ({a['runs']}회, 실패 {a['errors']}): 평균 LLM {a['avg_llm_calls']}회, 도구 {a['avg_tool_calls']}회, "
            f"입력 토큰 {a['avg_input_tokens']:,}, {a['avg_seconds']}초",
            f"  - 근거 확인 비율 {a['verified_item_ratio']}, HIGH 위험 {a['high_risks']}건",
            f"  - 추천 기존 테스트 (커밋 {atr['commits']}개): precision {atr['precision']}, recall {atr['recall']}",
        ]
    lines += ["", "## 커밋별", "", "| 커밋 | 제목 | 판정 | 기대 | 규칙 | 실제 테스트 | 예측 테스트 | 에이전트 |", "|---|---|---|---|---|---|---|---|"]
    for r in ev["rows"]:
        mark = "" if not r["expected"] else (" ✓" if r["expected"] == r["decision"] else " ✗")
        agent = "-"
        if r["agent"]:
            ag = r["agent"]
            agent = f"실패: {ag['error']}" if ag["error"] else f"도구 {ag['tool_calls']}, 토큰 {ag['input_tokens']:,}, HIGH {ag['high_risks']}, 확인 {ag['verified_items']}/{ag['items']}"
        lines.append(
            f"| `{r['sha']}` | {r['subject']} | {r['decision']}{mark} | {r['expected'] or '-'} | {', '.join(r['rules']) or '-'} | "
            f"{'<br>'.join(r['actual_tests']) or '-'} | {'<br>'.join(r['predicted_tests']) or '-'} | {agent} |"
        )
    lines.append("")
    return "\n".join(lines)
