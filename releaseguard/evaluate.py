"""Eval Set 실행. 대상 저장소의 커밋을 하나씩 분석해 정답과 비교한다.

정답은 세 종류다.
- 자동 정답: 같은 커밋에서 실제로 수정·추가된 테스트 파일 → 관련 테스트 탐색(3단계)과 에이전트 추천 테스트의 precision/recall
- 수기 정답: eval/cases.yaml의 expected (기대 판정) → 판정 정확도, 과잉·과소 경고
- 후속 수정: cases.yaml의 followup_fix (이후 커밋에서 문제가 고쳐짐) → 에이전트 HIGH 위험이 실제 문제를 잡는지

에이전트는 비용 때문에 수기 정답이 있는 커밋에만 돌린다. repeat > 1이면 같은 커밋을 여러 번 돌려 일관성을 잰다.
"""

from itertools import combinations
from pathlib import Path

import yaml

from .analyze import ImpactRunner, analyze
from .classify import RuleSet
from .decide import SAFE, SEVERITY
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


def evaluate(cases_path: Path, ruleset: RuleSet, run_impact: ImpactRunner | None = None, repeat: int = 1) -> dict:
    repo, labels = load_cases(cases_path)
    rows = []
    for sha, subject in list_commits(repo):
        label = _label_for(sha, labels) or {}
        with_agent = bool(label) and run_impact is not None
        results = [
            analyze(repo, f"{sha}~1", sha, ruleset, run_impact if with_agent else None)
            for _ in range(repeat if with_agent else 1)
        ]
        first = results[0]
        actual = sorted({f["path"] for f in first["changed_files"] if f["category"] == "test" and f["status"] != "D"})
        rows.append({
            "sha": sha[:7],
            "subject": subject,
            "by_category": first["summary"]["by_category"],
            "decision": first["decision"],
            "decisions": [r["decision"] for r in results],  # 실행마다 (규칙만이면 1개)
            "rules": [f["rule_id"] for f in first["findings"]],
            "has_source": bool(first["coverage"]),
            "actual_tests": actual,
            "predicted_tests": sorted({t["path"] for c in first["coverage"] for t in c["tests"]}),
            "expected": label.get("expected"),
            "followup_fix": label.get("followup_fix"),
            "labeled_by": label.get("labeled_by"),
            "note": label.get("note"),
            "agent_runs": [_agent_row(r, actual) for r in results] if with_agent else [],
        })
    return {"repo": str(repo), "rules_version": ruleset.version, "repeat": repeat, "metrics": metrics(rows), "rows": rows}


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
        "verified_high": sum(r["level"] == "HIGH" and r["verified"] for r in impact["risks"]),  # R07에 들어가는 것
        "recommended_existing": sorted({t["target"] for t in impact["recommended_tests"] if t["kind"] == "run_existing"}),
        "add_new": len([t for t in impact["recommended_tests"] if t["kind"] == "add_new"]),
        "actual_tests": actual,
        # 위험 내용이 후속 수정과 맞는지 사람이 대조할 수 있게 남긴다
        "summary": impact["summary"],
        "risks": [{k: r[k] for k in ("level", "title", "detail", "verified", "evidence")} for r in impact["risks"]],
        "tools_used": [f"{t['name']} {t['arguments']}" for t in meta["tool_log"]],
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


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa | sb else 1.0


def metrics(rows: list[dict]) -> dict:
    n = len(rows)
    rule_counts: dict[str, int] = {}
    for r in rows:
        for rule in r["rules"]:
            rule_counts[rule] = rule_counts.get(rule, 0) + 1
    decisions: dict[str, int] = {}
    for r in rows:
        decisions[r["decision"]] = decisions.get(r["decision"], 0) + 1

    # 판정은 (커밋, 실행) 단위로 센다. 규칙만이면 커밋당 1개.
    labeled = [r for r in rows if r["expected"]]
    pairs = [(r["expected"], d) for r in labeled for d in r["decisions"]]
    confusion: dict[str, int] = {}
    for exp, got in pairs:
        confusion[f"{exp} → {got}"] = confusion.get(f"{exp} → {got}", 0) + 1

    out = {
        "commits": n,
        "decisions": dict(sorted(decisions.items())),
        "rule_fire_rate": {k: _ratio(v, n) for k, v in sorted(rule_counts.items())},
        "test_retrieval": _retrieval([(r["predicted_tests"], r["actual_tests"]) for r in rows if r["has_source"]]),
        "decision": {
            "labeled": len(labeled),
            "judgments": len(pairs),
            "accuracy": _ratio(sum(exp == got for exp, got in pairs), len(pairs)),
            "over_warning": sum(SEVERITY[got] > SEVERITY[exp] for exp, got in pairs),
            "under_warning": sum(SEVERITY[got] < SEVERITY[exp] for exp, got in pairs),
            "confusion": dict(sorted(confusion.items())),
        },
        "agent": None,
    }

    ran = [a for r in rows for a in r["agent_runs"]]
    ok = [a for a in ran if not a["error"]]
    if not ran:
        return out
    avg = lambda key: round(sum(a[key] for a in ok) / len(ok), 1) if ok else None  # noqa: E731

    def high_hits(subset: list[dict]) -> dict:
        """커밋별로 verified HIGH가 나온 실행 수를 센다."""
        per = [sum(a["verified_high"] > 0 for a in r["agent_runs"] if not a["error"]) for r in subset]
        runs = sum(len([a for a in r["agent_runs"] if not a["error"]]) for r in subset)
        return {
            "commits": len(subset),
            "run_rate": _ratio(sum(per), runs),  # 실행 단위 비율
            "any_run": sum(p > 0 for p in per),  # 한 번이라도 HIGH
            "every_run": sum(p > 0 and p == len([a for a in r["agent_runs"] if not a["error"]]) for p, r in zip(per, subset)),
        }

    with_runs = [r for r in rows if r["agent_runs"]]
    multi = [r for r in with_runs if len([a for a in r["agent_runs"] if not a["error"]]) >= 2]
    jaccards = [
        _jaccard(a["recommended_existing"], b["recommended_existing"])
        for r in multi
        for a, b in combinations([x for x in r["agent_runs"] if not x["error"]], 2)
    ]
    out["agent"] = {
        "runs": len(ran),
        "errors": len(ran) - len(ok),
        "avg_llm_calls": avg("llm_calls"),
        "avg_tool_calls": avg("tool_calls"),
        "max_tool_calls": max((a["tool_calls"] for a in ok), default=None),
        "avg_input_tokens": avg("input_tokens"),
        "max_input_tokens": max((a["input_tokens"] for a in ok), default=None),
        "avg_seconds": avg("seconds"),
        "verified_item_ratio": _ratio(sum(a["verified_items"] for a in ok), sum(a["items"] for a in ok)),
        "test_retrieval": _retrieval([(a["recommended_existing"], a["actual_tests"]) for a in ok]),
        # 후속 수정이 있었던 커밋에서 HIGH가 나왔는가 (높을수록 좋음)
        "high_on_followup": high_hits([r for r in with_runs if r["followup_fix"]]),
        # SAFE 기대 커밋에서 HIGH가 나왔는가 (낮을수록 좋음)
        "high_on_safe": high_hits([r for r in with_runs if r["expected"] == SAFE]),
        "consistency": {
            "commits": len(multi),
            "decision_same": sum(len(set(r["decisions"])) == 1 for r in multi),
            "high_same": sum(len({a["verified_high"] > 0 for a in r["agent_runs"] if not a["error"]}) == 1 for r in multi),
            "avg_tests_jaccard": round(sum(jaccards) / len(jaccards), 3) if jaccards else None,
        },
    }
    return out


def to_markdown(ev: dict) -> str:
    m = ev["metrics"]
    tr, d = m["test_retrieval"], m["decision"]
    lines = [
        "# ReleaseGuard Eval 결과",
        "",
        f"- 저장소: `{ev['repo']}` · 커밋 {m['commits']}개 · 분류 규칙 v{ev['rules_version']} · 에이전트 반복 {ev['repeat']}회",
        f"- 판정 분포 (첫 실행): " + ", ".join(f"{k} {v}" for k, v in m["decisions"].items()),
        f"- 규칙 발동률 (첫 실행): " + ", ".join(f"{k} {v:.0%}" for k, v in m["rule_fire_rate"].items()),
        f"- 관련 테스트 탐색 (규칙, 테스트가 함께 바뀐 커밋 {tr['commits']}개): precision {tr['precision']}, recall {tr['recall']}",
        f"- 판정 (수기 정답 {d['labeled']}개, 판정 {d['judgments']}회): 정확도 {d['accuracy']}, "
        f"과잉 경고 {d['over_warning']}, 과소 경고 {d['under_warning']}",
    ]
    for k, v in d["confusion"].items():
        lines.append(f"  - {k}: {v}")
    if a := m["agent"]:
        atr, fu, sf, c = a["test_retrieval"], a["high_on_followup"], a["high_on_safe"], a["consistency"]
        lines += [
            f"- 에이전트 ({a['runs']}회, 실패 {a['errors']}): 평균 LLM {a['avg_llm_calls']}회, 도구 {a['avg_tool_calls']}회 (최대 {a['max_tool_calls']}), "
            f"입력 토큰 {a['avg_input_tokens']:,} (최대 {a['max_input_tokens']:,}), {a['avg_seconds']}초",
            f"  - 근거 확인 비율 {a['verified_item_ratio']}",
            f"  - 추천 기존 테스트: precision {atr['precision']}, recall {atr['recall']}",
            f"  - 후속 수정 커밋 {fu['commits']}개의 verified HIGH: 실행 비율 {fu['run_rate']}, 한 번이라도 {fu['any_run']}개, 매번 {fu['every_run']}개",
            f"  - SAFE 커밋 {sf['commits']}개의 verified HIGH: 실행 비율 {sf['run_rate']}, 한 번이라도 {sf['any_run']}개",
            f"  - 일관성 (커밋 {c['commits']}개): 판정 같음 {c['decision_same']}, HIGH 여부 같음 {c['high_same']}, 추천 테스트 Jaccard {c['avg_tests_jaccard']}",
        ]
    lines += ["", "## 커밋별", "", "| 커밋 | 제목 | 판정 | 기대 | 규칙 | 실제 테스트 | 예측 테스트 | 에이전트 |", "|---|---|---|---|---|---|---|---|"]
    for r in ev["rows"]:
        decision = " / ".join(r["decisions"])
        mark = "" if not r["expected"] else (" ✓" if all(x == r["expected"] for x in r["decisions"]) else " ✗")
        agent = "-"
        if r["agent_runs"]:
            parts = []
            for ag in r["agent_runs"]:
                parts.append("실패" if ag["error"] else f"도구 {ag['tool_calls']}, 토큰 {ag['input_tokens']:,}, HIGH {ag['verified_high']}/{ag['high_risks']}")
            agent = "<br>".join(parts)
        lines.append(
            f"| `{r['sha']}` | {r['subject']} | {decision}{mark} | {r['expected'] or '-'} | {', '.join(r['rules']) or '-'} | "
            f"{'<br>'.join(r['actual_tests']) or '-'} | {'<br>'.join(r['predicted_tests']) or '-'} | {agent} |"
        )

    risky = [r for r in ev["rows"] if any(not a["error"] and a["risks"] for a in r["agent_runs"])]
    if risky:
        lines += ["", "## 에이전트 위험 (HIGH·MEDIUM)", ""]
        for r in risky:
            fix = f" · 후속 수정 {', '.join(r['followup_fix'])}" if r["followup_fix"] else ""
            lines.append(f"### `{r['sha']}` {r['subject']} (기대 {r['expected']}{fix})")
            lines.append("")
            for i, ag in enumerate(r["agent_runs"], 1):
                if ag["error"]:
                    continue
                for risk in ag["risks"]:
                    if risk["level"] != "LOW":
                        ok = "" if risk["verified"] else " (근거 미확인)"
                        lines.append(f"- 실행 {i} · {risk['level']}{ok}: {risk['title']}")
            lines.append("")
    lines.append("")
    return "\n".join(lines)
