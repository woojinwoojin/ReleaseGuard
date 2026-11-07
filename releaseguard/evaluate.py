"""Eval v2. 세 가지로 잰다.

1. evaluate — 대상 저장소의 커밋 전체를 분석한다.
   - 자동 정답: 같은 커밋에서 바뀐 테스트 파일 ↔ 바뀐 줄을 실제로 실행한 테스트 파일
   - 수기 라벨 v2 (eval/cases*.yaml): need(사람이 봐야 했나) → 과소·과잉 경고, expected_scope → 검증 범위 일치
   - 결정성: 수기 정답 커밋을 repeat번 돌려 판정·공백·테스트 목록이 같은지
2. run_seeds — 대상 저장소를 임시로 clone해 결함을 심고, 기대 판정·규칙이 나오는지 본다.
3. run_szz — 고친 커밋이 지우거나 바꾼 줄을 blame으로 거슬러 "결함을 들여온 커밋·줄"을 찾고,
   그 줄이 들어올 때 검증 공백이었는지 본다. (SZZ 알고리즘의 단순판)

에이전트(공백 설명)는 비용 때문에 evaluate의 수기 정답 커밋에만, --agent일 때만 돌린다.
"""

import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from statistics import median

import yaml

from .analyze import ExplainRunner, analyze
from .classify import RuleSet, classify
from .decide import NOTE, SAFE
from .gap_groups import preservation
from .git_ops import resolve, run_git
from .runner import find_python


def load_yaml(path: Path) -> tuple[Path, dict, Path | None]:
    """(대상 저장소 경로, 내용, 테스트를 돌릴 Python). 경로는 yaml 파일 위치 기준. python이 없으면 대상 저장소의 .venv."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    repo = (path.parent / raw["repo"]).resolve()
    python = (path.parent / raw["python"]).resolve() if raw.get("python") else find_python(repo)
    return repo, raw, python


def list_commits(repo: Path) -> list[tuple[str, str]]:
    """부모가 있는 커밋만 (오래된 순). 첫 커밋은 비교 대상이 없어서 뺀다."""
    out = run_git(repo, "log", "--reverse", "--min-parents=1", "--format=%H%x09%s")
    return [tuple(line.split("\t", 1)) for line in out.splitlines()]


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def _test_file(nodeid: str) -> str:
    return nodeid.split("::", 1)[0]


def _rules(result: dict) -> list[str]:
    return [f["rule_id"] for f in result["findings"] if f["decision"] != NOTE]


def _need(value) -> str | None:
    """YAML 1.1은 yes/no를 불리언으로 읽는다. 라벨은 문자열 yes/no로 맞춘다."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value not in ("yes", "no"):
        raise ValueError(f"need는 yes 또는 no: {value!r}")
    return value


def _signature(result: dict) -> tuple:
    """결정성 비교용: 판정, 규칙, 공백, 실행한 테스트."""
    return (
        result["decision"],
        result["scope"]["status"],
        tuple(_rules(result)),
        tuple((fl["path"], tuple(map(tuple, fl["gaps"]))) for fl in result["lines"]),
        tuple((g["path"], g["name"], g["gap_lines"], g["review_priority"]) for g in result["gap_groups"]),  # 그룹과 순서까지
        tuple(sorted({t for fl in result["lines"] for t in fl["tests"]})),
    )


# ---------------------------------------------------------------- 1. 커밋 전체


def evaluate(cases_path: Path, ruleset: RuleSet, explain: ExplainRunner | None = None, repeat: int = 1) -> dict:
    repo, raw, python = load_yaml(cases_path)
    labels = {str(c["sha"]): c for c in raw.get("cases", [])}
    rows = []
    for sha, subject in list_commits(repo):
        label = next((c for short, c in labels.items() if sha.startswith(short)), {})
        times = repeat if label else 1
        results = [analyze(repo, f"{sha}~1", sha, ruleset, python=python, explain=explain if label else None) for _ in range(times)]
        first = results[0]
        actual = sorted({f["path"] for f in first["changed_files"] if f["category"] == "test" and f["status"] != "D"})
        rows.append({
            "sha": sha[:7],
            "subject": subject,
            "by_category": first["summary"]["by_category"],
            "decision": first["decision"],
            "scope": first["scope"]["status"],
            "decisions": [r["decision"] for r in results],
            "deterministic": len({_signature(r) for r in results}) == 1 if times > 1 else None,
            "rules": _rules(first),
            "notes": [f["rule_id"] for f in first["findings"] if f["decision"] == NOTE],
            "test_status": first["test_run"]["status"],
            "test_counts": first["test_run"]["counts"],
            "test_seconds": first["test_run"]["seconds"],
            "coverage": first["test_run"]["coverage"],
            "gap_lines": sum(fl["gap_lines"] for fl in first["lines"]),
            "executable_lines": sum(fl["executable"] for fl in first["lines"]),
            "gaps": [f"{fl['path']}:{s}" + (f"-{e}" if e != s else "") for fl in first["lines"] for s, e in fl["gaps"]],
            # 함수별 공백 (검토 순서대로)과, 줄 단위 공백을 빠짐없이 옮겼는지
            "gap_groups": [
                {k: g[k] for k in ("path", "kind", "name", "start_line", "gap_lines", "gap_ranges", "review_priority")}
                for g in first["gap_groups"]
            ],
            "gap_preservation": preservation(first["lines"], first["gap_groups"]),
            # 분기 공백 (판정 미반영): 바뀐 분기 줄의 분기 수와 실행 안 된 분기
            "branches": sum(fl["branches"] for fl in first["lines"]),
            "branch_gaps": [f"{fl['path']}:{a}->{b}" for fl in first["lines"] for a, b in fl["branch_gaps"]],
            "fixture_only": sum(fl["fixture_only"] for fl in first["lines"]),
            "actual_tests": actual,
            "executed_tests": sorted({_test_file(t) for fl in first["lines"] for t in fl["tests"]}),
            "need": _need(label.get("need")),
            "need_reason": label.get("need_reason"),
            "expected_scope": label.get("expected_scope"),
            "followup_fix": label.get("followup_fix", []),
            "need_labeled_by": label.get("need_labeled_by"),
            "scope_labeled_by": label.get("scope_labeled_by"),
            "note": label.get("note"),
            "explanations": [_explain_row(r) for r in results if r["explanations"] is not None or r["agent_error"]],
        })
    return {"repo": str(repo), "repeat": repeat, "metrics": metrics(rows), "rows": rows}


def _explain_row(result: dict) -> dict:
    if result["agent_error"]:
        return {"error": result["agent_error"]}
    items = [i for i in result["explanations"] if not i["error"]]
    return {
        "error": None,
        **{k: result["agent"][k] for k in ("gaps", "llm_calls", "tool_calls", "input_tokens", "output_tokens", "seconds", "errors")},
        "references_valid": sum(i["references_valid"] for i in items),
        "test_path_invalid": sum(not i["test_path_valid"] for i in items),
        "new_test_file": sum(i["new_test_file"] for i in items),
        "items": [
            {k: i[k] for k in ("path", "start", "end", "behavior", "suggested_test", "references_valid", "invalid_references", "test_path_valid")} for i in items
        ],
    }


def _retrieval(pairs: list[tuple[list[str], list[str]]]) -> dict:
    """(예측, 실제) 목록의 micro precision/recall. 실제 정답이 빈 커밋은 정답을 알 수 없어서 뺀다."""
    pairs = [(set(p), set(a)) for p, a in pairs if a]
    tp = sum(len(p & a) for p, a in pairs)
    return {"commits": len(pairs), "precision": _ratio(tp, sum(len(p) for p, _ in pairs)), "recall": _ratio(tp, sum(len(a) for _, a in pairs))}


def _count(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))


def metrics(rows: list[dict]) -> dict:
    n = len(rows)
    labeled = [r for r in rows if r["need"] is not None]
    ran = [r for r in rows if r["test_status"] not in ("skipped",)]
    out = {
        "commits": n,
        "decisions": _count(r["decision"] for r in rows),
        "scope": _count(r["scope"] for r in rows),
        "test_status": _count(r["test_status"] for r in rows),
        "rule_fire_rate": {k: _ratio(v, n) for k, v in _count(x for r in rows for x in r["rules"]).items()},
        "note_rate": {k: _ratio(v, n) for k, v in _count(x for r in rows for x in r["notes"]).items()},
        "gaps": {
            "commits_with_gap": sum(r["gap_lines"] > 0 for r in rows),
            "gap_lines": sum(r["gap_lines"] for r in rows),
            "executable_lines": sum(r["executable_lines"] for r in rows),
            "fixture_only_lines": sum(r["fixture_only"] for r in rows),
        },
        "gap_groups": {
            "groups": sum(len(r["gap_groups"]) for r in rows),
            "by_kind": _count(g["kind"] for r in rows for g in r["gap_groups"]),
            "low_groups": sum(g["review_priority"] == "LOW" for r in rows for g in r["gap_groups"]),
            "low_paths": sorted({g["path"] for r in rows for g in r["gap_groups"] if g["review_priority"] == "LOW"}),
            "missing": sum(r["gap_preservation"]["missing"] for r in rows),
            "extra": sum(r["gap_preservation"]["extra"] for r in rows),
            "duplicate": sum(r["gap_preservation"]["duplicate"] for r in rows),
        },
        # 줄 공백과 따로 센다. branch_gap_only = 줄 공백은 없고 분기 공백만 있는 커밋 (줄 단위로는 놓쳤을 커밋)
        "branch_gaps": {
            "commits_with_branch_gap": sum(bool(r["branch_gaps"]) for r in rows),
            "commits_branch_gap_only": sum(bool(r["branch_gaps"]) and r["gap_lines"] == 0 for r in rows),
            "branch_gaps": sum(len(r["branch_gaps"]) for r in rows),
            "branches": sum(r["branches"] for r in rows),
        },
        # Changed-test Retrieval: 바뀐 줄을 실행한 테스트 파일 ↔ 같은 커밋에서 바뀐 테스트 파일.
        # 실제 "관련 테스트" 정답이 아니라 대리 지표다 (바뀌지 않은 관련 테스트는 정답에 없다).
        "changed_test_retrieval": _retrieval([(r["executed_tests"], r["actual_tests"]) for r in rows if r["coverage"]]),
        "run_seconds": {
            "avg": round(sum(r["test_seconds"] for r in ran) / len(ran), 1) if ran else None,
            "max": max((r["test_seconds"] for r in ran), default=None),
        },
        "labels": label_metrics(labeled),
        "determinism": None,
        "agent": None,
    }
    multi = [r for r in rows if r["deterministic"] is not None]
    if multi:
        out["determinism"] = {"commits": len(multi), "identical": sum(r["deterministic"] for r in multi)}
    runs = [x for r in rows for x in r["explanations"]]
    ok = [x for x in runs if not x["error"]]
    if runs:
        explained = sum(x["gaps"] - x["errors"] for x in ok)
        out["agent"] = {
            "runs": len(runs),
            "errors": len(runs) - len(ok) + sum(x["errors"] for x in ok),
            "gaps_explained": explained,
            "references_valid_ratio": _ratio(sum(x["references_valid"] for x in ok), explained),
            "test_path_invalid": sum(x["test_path_invalid"] for x in ok),
            "new_test_file_ratio": _ratio(sum(x["new_test_file"] for x in ok), explained),
            "avg_tool_calls_per_gap": round(sum(x["tool_calls"] for x in ok) / explained, 1) if explained else None,
            "avg_input_tokens_per_gap": round(sum(x["input_tokens"] for x in ok) / explained) if explained else None,
        }
    return out


def over_warning_cause(rules: list[str]) -> str:
    """need=no인데 경고한 이유. 심각한 쪽부터: BLOCK 규칙 → G01 → E02만(범위 정책의 비용, 의도된 것) → 그 밖."""
    if block := [r for r in rules if r in ("B01", "B03", "B04")]:
        return block[0]
    if "G01" in rules:
        return "G01"
    if rules and set(rules) <= {"E02"}:
        return "scope_only"
    return "other"


def label_metrics(labeled: list[dict]) -> dict:
    """수기 라벨 v2. 반복 실행이면 실행마다 센다 (판정이 흔들리면 그대로 드러난다)."""
    need = [(r, d) for r in labeled if r["need"] == "yes" for d in r["decisions"]]
    no_need = [(r, d) for r in labeled if r["need"] == "no" for d in r["decisions"]]
    over = [r for r, d in no_need if d != SAFE]
    # 실행 환경이 정상인 커밋만: 실행 실패로 생긴 범위 불일치를 라벨 오류로 오해하지 않도록
    scoped = [r for r in labeled if r["expected_scope"] and r["test_status"] not in ("error", "timeout", "not_run")]

    def under(pairs: list) -> dict:
        return {"count": sum(d == SAFE for _, d in pairs), "of": len(pairs), "commits": sorted({r["sha"] for r, d in pairs if d == SAFE})}
    return {
        "labeled": len(labeled),
        "need_yes": sum(r["need"] == "yes" for r in labeled),
        "need_no": sum(r["need"] == "no" for r in labeled),
        # 가장 위험: 봐야 했는데 SAFE
        "under_warning": under(need),
        # need_reason별: untested·followup_fix는 이 도구가 잡아야 할 것, risky_area·policy는 원리상 못 보는 것 (제품 범위의 한계)
        # followup_fix는 이후 커밋을 보고 단 사후 라벨이다 (ReleaseGuard 실행과는 독립이지만 미래 정보를 쓴다)
        "under_warning_by_reason": {
            reason: under([(r, d) for r, d in need if r["need_reason"] == reason])
            for reason in sorted({r["need_reason"] for r, _ in need if r["need_reason"]})
        },
        "over_warning": {"count": len(over), "of": len(no_need),
                         "by_cause": _count(over_warning_cause(r["rules"]) for r in over),
                         "commits": sorted({r["sha"] for r in over})},
        "scope_agreement": {"agree": sum(r["expected_scope"] == r["scope"] for r in scoped), "of": len(scoped),
                            "mismatch": [f"{r['sha']} ({r['expected_scope']} → {r['scope']})" for r in scoped if r["expected_scope"] != r["scope"]]},
    }


def to_markdown(ev: dict) -> str:
    m = ev["metrics"]
    lb, tr, g = m["labels"], m["changed_test_retrieval"], m["gaps"]
    lines = [
        "# ReleaseGuard Eval — 커밋 전체",
        "",
        f"- 저장소: `{ev['repo']}` · 커밋 {m['commits']}개 · 수기 정답 커밋 반복 {ev['repeat']}회",
        "- 판정 분포 (첫 실행): " + ", ".join(f"{k} {v}" for k, v in m["decisions"].items()),
        "- 검증 범위: " + ", ".join(f"{k} {v}" for k, v in m["scope"].items()),
        "- 테스트 실행 상태: " + ", ".join(f"{k} {v}" for k, v in m["test_status"].items())
        + f" · 평균 {m['run_seconds']['avg']}초, 최대 {m['run_seconds']['max']}초",
        "- 규칙 발동률: " + (", ".join(f"{k} {v:.0%}" for k, v in m["rule_fire_rate"].items()) or "없음"),
        "- 참고 표시율: " + (", ".join(f"{k} {v:.0%}" for k, v in m["note_rate"].items()) or "없음"),
        f"- 검증 공백: 커밋 {g['commits_with_gap']}개, 바뀐 실행 줄 {g['executable_lines']}줄 중 {g['gap_lines']}줄"
        f" (covered 중 fixture에서만 실행 {g['fixture_only_lines']}줄)",
        f"- 분기 공백 (판정 미반영): 커밋 {m['branch_gaps']['commits_with_branch_gap']}개 "
        f"(그중 줄 공백 없이 분기 공백만 {m['branch_gaps']['commits_branch_gap_only']}개), "
        f"바뀐 분기 줄의 분기 {m['branch_gaps']['branches']}개 중 {m['branch_gaps']['branch_gaps']}개",
        f"- 함수별 공백 그룹 {m['gap_groups']['groups']}개 ({', '.join(f'{k} {v}' for k, v in m['gap_groups']['by_kind'].items()) or '-'}), "
        f"LOW {m['gap_groups']['low_groups']}개 · 줄 보존: 누락 {m['gap_groups']['missing']}, 추가 {m['gap_groups']['extra']}, 중복 {m['gap_groups']['duplicate']}",
        f"- Changed-test Retrieval (바뀐 줄을 실행한 테스트 ↔ 같은 커밋에서 바뀐 테스트, 대리 지표, 커밋 {tr['commits']}개): "
        f"precision {tr['precision']}, recall {tr['recall']}",
    ]
    if lb["labeled"]:
        u, o, sc = lb["under_warning"], lb["over_warning"], lb["scope_agreement"]
        lines += [
            f"- 수기 라벨 {lb['labeled']}개 (봐야 했음 {lb['need_yes']}, 아님 {lb['need_no']})",
            f"  - 과소 경고 (봐야 했는데 SAFE): **{u['count']}/{u['of']}** " + ", ".join(f"`{c}`" for c in u["commits"]),
            *(f"    - {k}: {v['count']}/{v['of']} " + ", ".join(f"`{c}`" for c in v["commits"]) for k, v in lb["under_warning_by_reason"].items()),
            f"  - 과잉 경고 (안 봐도 됐는데 경고): {o['count']}/{o['of']} — 원인 "
            + (", ".join(f"{k} {v}" for k, v in o["by_cause"].items()) or "-") + " " + ", ".join(f"`{c}`" for c in o["commits"]),
            f"  - 검증 범위 일치 (실행 정상 커밋): {sc['agree']}/{sc['of']}" + (" — 불일치 " + ", ".join(sc["mismatch"]) if sc["mismatch"] else ""),
        ]
    if det := m["determinism"]:
        lines.append(f"- 결정성: 반복 실행 결과가 완전히 같은 커밋 {det['identical']}/{det['commits']}")
    if a := m["agent"]:
        lines.append(
            f"- 공백 설명 에이전트: 실행 {a['runs']}회, 오류 {a['errors']}, 설명한 공백 {a['gaps_explained']}개, "
            f"근거 참조 유효 {a['references_valid_ratio']}, 테스트 경로 오류 {a['test_path_invalid']}, 새 테스트 파일 제안 {a['new_test_file_ratio']}, "
            f"공백당 도구 {a['avg_tool_calls_per_gap']}회·입력 {a['avg_input_tokens_per_gap']} 토큰"
        )
    lines += [
        "",
        "## 커밋별",
        "",
        "| 커밋 | 제목 | 판정 | 범위 | 봐야 했나 | 기대 범위 | 규칙 | 테스트 | 공백/실행 줄 | 분기 공백/분기 | 바뀐 테스트 | 실행한 테스트 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in ev["rows"]:
        decision = " / ".join(dict.fromkeys(r["decisions"]))
        mark = ""
        if r["need"] == "yes" and SAFE in r["decisions"]:
            mark = " ✗ 과소"
        elif r["need"] == "no" and any(x != SAFE for x in r["decisions"]):
            mark = " △ 과잉"
        lines.append(
            f"| `{r['sha']}` | {r['subject']} | {decision}{mark} | {r['scope']} | {r['need'] or '-'} | {r['expected_scope'] or '-'} | {', '.join(r['rules']) or '-'} | "
            f"{r['test_status']} | {r['gap_lines']}/{r['executable_lines']} | {len(r['branch_gaps'])}/{r['branches']} | "
            f"{'<br>'.join(r['actual_tests']) or '-'} | "
            f"{'<br>'.join(r['executed_tests']) or '-'} |"
        )
    explained = [r for r in ev["rows"] if any(not x["error"] for x in r["explanations"])]
    if explained:
        lines += ["", "## 공백 설명 (첫 실행)", ""]
        for r in explained:
            x = next(x for x in r["explanations"] if not x["error"])
            lines.append(f"### `{r['sha']}` {r['subject']}")
            lines.append("")
            for i in x["items"]:
                t = i["suggested_test"]
                ok = "" if i["references_valid"] else " (근거 참조 오류)"
                lines.append(f"- `{i['path']}` {i['start']}-{i['end']}{ok}: {i['behavior']} → `{t['file']}::{t['name']}`")
            lines.append("")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- 2. 결함을 심은 사례


def _apply(clone: Path, edit: dict) -> None:
    path = clone / edit["path"]
    if edit.get("delete"):
        path.unlink()
    elif "create" in edit:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(edit["create"], encoding="utf-8", newline="\n")
    else:
        text = path.read_text(encoding="utf-8")
        if text.count(edit["find"]) != 1:
            raise ValueError(f"{edit['path']}: find가 정확히 한 번 나와야 합니다 ({text.count(edit['find'])}번)")
        path.write_text(text.replace(edit["find"], edit["replace"]), encoding="utf-8", newline="\n")


def _git(clone: Path, *args: str) -> str:
    return run_git(clone, "-c", "user.name=releaseguard", "-c", "user.email=releaseguard@localhost", *args)


def run_seeds(seeds_path: Path, ruleset: RuleSet) -> dict:
    """대상 저장소를 임시 폴더에 clone해서 사례마다 변경을 심고 분석한다. 원래 저장소는 건드리지 않는다."""
    repo, raw, python = load_yaml(seeds_path)
    rows = []
    with tempfile.TemporaryDirectory(prefix="rg_seeds_", ignore_cleanup_errors=True) as tmp:
        clone = Path(tmp) / "clone"
        subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(repo), str(clone)], check=True)
        base = resolve(clone, raw.get("base", "HEAD"))
        for seed in raw["seeds"]:
            _git(clone, "checkout", "--quiet", "--detach", base)
            for edit in seed["edits"]:
                _apply(clone, edit)
            _git(clone, "add", "-A")
            _git(clone, "commit", "--quiet", "--allow-empty", "-m", f"seed {seed['id']}")
            result = analyze(clone, base, "HEAD", ruleset, python=python)
            rules = _rules(result)
            expect_rules = seed.get("expect_rules", [])
            scope = result["scope"]["status"]
            ok = (
                result["decision"] == seed["expected"]
                and set(expect_rules) <= set(rules)
                and seed.get("expect_scope", scope) == scope
            )
            rows.append({
                "id": seed["id"],
                "description": seed["description"],
                "expected": seed["expected"],
                "expect_rules": expect_rules,
                "decision": result["decision"],
                "expect_scope": seed.get("expect_scope"),
                "scope": scope,
                "rules": rules,
                "gaps": [f"{fl['path']}:{s}" + (f"-{e}" if e != s else "") for fl in result["lines"] for s, e in fl["gaps"]],
                "failures": [f"{f['nodeid']} ({f['comparison']})" for f in result["test_run"]["failures"]],
                "test_status": result["test_run"]["status"],
                "pass": ok,
            })
    return {"repo": str(repo), "base": base, "passed": sum(r["pass"] for r in rows), "total": len(rows), "rows": rows}


def seeds_markdown(ev: dict) -> str:
    lines = [
        f"# ReleaseGuard Eval — 결함을 심은 사례 ({ev['passed']}/{ev['total']} 통과)",
        "",
        f"- 저장소: `{ev['repo']}` (임시 clone에서 실행) · base `{ev['base'][:7]}`",
        "",
        "| id | 심은 변경 | 기대 | 결과 | 기대 범위 | 범위 | 기대 규칙 | 발동 규칙 | 근거 | 통과 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in ev["rows"]:
        evidence = "<br>".join(r["failures"] + r["gaps"]) or "-"
        lines.append(
            f"| {r['id']} | {r['description']} | {r['expected']} | {r['decision']} | {r['expect_scope'] or '-'} | {r['scope']} | "
            f"{', '.join(r['expect_rules']) or '-'} | "
            f"{', '.join(r['rules']) or '-'} | {evidence} | {'✓' if r['pass'] else '✗'} |"
        )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- 3. SZZ


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def removed_lines(repo: Path, fix: str, ruleset: RuleSet) -> dict[str, list[int]]:
    """고친 커밋이 지우거나 바꾼 줄 (fix~1 기준 줄 번호). Python 소스만."""
    out: dict[str, list[int]] = {}
    path = None
    for line in run_git(repo, "diff", "-U0", "--no-color", "--no-ext-diff", f"{fix}~1", fix).splitlines():
        if line.startswith("--- "):
            target = line[4:]
            path = target[2:] if target.startswith("a/") else None
            if path and not (path.endswith(".py") and classify(path, ruleset)[0] == "source"):
                path = None
        elif path and (m := _HUNK.match(line)):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            out.setdefault(path, []).extend(range(start, start + count))  # count가 0이면 순수 추가라 blame할 줄이 없다
    return out


def blame_origins(repo: Path, fix: str, path: str, lines: list[int]) -> list[dict]:
    """줄마다 그 줄을 마지막으로 바꾼 커밋과 그 커밋에서의 경로·줄 번호. 빈 줄·주석은 뺀다."""
    out = []
    for n in lines:
        porcelain = run_git(repo, "blame", "-w", "--porcelain", "-L", f"{n},{n}", f"{fix}~1", "--", path)
        rows = porcelain.splitlines()
        sha, orig_line = rows[0].split()[:2]
        orig_path = next((r[9:] for r in rows if r.startswith("filename ")), path)
        content = next((r[1:] for r in rows if r.startswith("\t")), "")
        if content.strip() and not content.strip().startswith("#"):
            out.append({"sha": sha, "path": orig_path, "line": int(orig_line), "fix": fix, "text": content.strip()[:120]})
    return out


def _first_hit(groups: list[dict], defects: set[tuple[str, int]]) -> tuple[int, int, int]:
    """(결함이 든 첫 그룹의 순위, 그 그룹을 끝까지 읽을 때 공백 줄 수, 그 그룹의 첫 결함 줄까지만 읽을 때 공백 줄 수)."""
    read = 0
    for rank, g in enumerate(groups, 1):
        hits = [i for i, n in enumerate(g["gap_line_numbers"], 1) if (g["path"], n) in defects]
        if hits:
            return rank, read + g["gap_lines"], read + hits[0]
        read += g["gap_lines"]
    raise ValueError("결함이 든 그룹이 없음")


def review_cost(groups: list[dict], defects: set[tuple[str, int]]) -> dict | None:
    """결함 줄이 공백에 있는 커밋에서, 검토 순서대로 볼 때와 소스 순서로 볼 때 첫 결함까지의 비용."""
    if not any((g["path"], n) in defects for g in groups for n in g["gap_line_numbers"]):
        return None
    rank, read, to_line = _first_hit(groups, defects)
    source_rank, source_read, source_to_line = _first_hit(sorted(groups, key=lambda g: (g["path"], g["gap_line_numbers"][0])), defects)
    return {
        "groups": len(groups),
        "gap_lines": sum(g["gap_lines"] for g in groups),
        "rank": rank, "lines_read": read, "lines_to_defect": to_line,
        "source_rank": source_rank, "source_lines_read": source_read, "source_lines_to_defect": source_to_line,
    }


def review_order_metrics(items: list[dict]) -> dict | None:
    """회귀 지표: 구현이 규칙을 그대로 재현하는지 본다. 규칙을 고른 데이터라 일반화 성능이 아니다."""
    if not items:
        return None

    def side(rank: str, read: str, to_defect: str) -> dict:
        lines = [x[read] for x in items]
        to_line = [x[to_defect] for x in items]
        return {
            "top1": sum(x[rank] == 1 for x in items),
            "mrr": round(sum(1 / x[rank] for x in items) / len(items), 2),
            "lines_read_total": sum(lines),
            "lines_read_median": median(lines),
            "share_of_gap_lines": _ratio(sum(lines), sum(x["gap_lines"] for x in items)),
            "lines_to_defect_total": sum(to_line),
            "lines_to_defect_median": median(to_line),
        }

    return {"commits": len(items), "by_gap_size": side("rank", "lines_read", "lines_to_defect"),
            "source_order": side("source_rank", "source_lines_read", "source_lines_to_defect")}


def run_szz(cases_path: Path, ruleset: RuleSet) -> dict:
    repo, raw, python = load_yaml(cases_path)
    fixes = [resolve(repo, str(f)) for f in raw.get("fix_commits", [])]
    origins: list[dict] = []
    for fix in fixes:
        for path, lines in removed_lines(repo, fix, ruleset).items():
            origins += blame_origins(repo, fix, path, lines)

    roots = set(run_git(repo, "rev-list", "--max-parents=0", "HEAD").split())
    by_commit: dict[str, list[dict]] = {}
    for o in origins:
        by_commit.setdefault(o["sha"], []).append(o)

    rows = []
    for sha, items in sorted(by_commit.items(), key=lambda kv: kv[0]):
        subject = run_git(repo, "log", "-1", "--format=%s", sha).strip()
        if sha in roots:
            rows.append({"sha": sha[:7], "subject": subject, "status": "root", "lines": [{**o, "status": "unknown"} for o in items]})
            continue
        result = analyze(repo, f"{sha}~1", sha, ruleset, python=python)
        status_of = {fl["path"]: fl["line_status"] for fl in result["lines"]}
        branch_from = {(fl["path"], a) for fl in result["lines"] for a, _ in fl["branch_gaps"]}
        lines = []
        for o in items:
            st = status_of.get(o["path"], {}).get(o["line"])
            lines.append({
                **o,
                "status": st or ("unknown" if not result["test_run"]["coverage"] else "not_changed"),
                "branch_gap": (o["path"], o["line"]) in branch_from,  # 이 결함 줄에서 나가는 분기 중 실행 안 된 것이 있었나
            })
        rows.append({
            "sha": sha[:7],
            "subject": subject,
            "status": result["test_run"]["status"],
            "decision": result["decision"],
            "rules": _rules(result),
            "lines": lines,
            "review": review_cost(result["gap_groups"], {(o["path"], o["line"]) for o in items}),
        })
    all_lines = [ln for r in rows for ln in r["lines"]]
    counts = _count(ln["status"] for ln in all_lines)
    judged = sum(counts.get(k, 0) for k in ("gap", "covered", "import_only"))
    return {
        "repo": str(repo),
        "fix_commits": [f[:7] for f in fixes],
        "defect_lines": len(all_lines),
        "introducing_commits": len(rows),
        "line_status": counts,
        "gap_ratio": _ratio(counts.get("gap", 0), judged),
        # covered인데 결함이었던 줄 중, 그 줄의 분기 일부가 실행되지 않았던 줄 (분기 coverage로 더 잡을 수 있었나)
        "covered_with_branch_gap": sum(ln["status"] == "covered" and ln.get("branch_gap", False) for ln in all_lines),
        "review_order": review_order_metrics([r["review"] for r in rows if r.get("review")]),
        "rows": rows,
    }


def szz_markdown(ev: dict) -> str:
    c = ev["line_status"]
    lines = [
        "# ReleaseGuard Eval v2 — SZZ (결함 줄이 들어올 때 검증 공백이었나)",
        "",
        f"- 저장소: `{ev['repo']}` · 고친 커밋: {', '.join(f'`{f}`' for f in ev['fix_commits'])}",
        f"- 결함 줄 {ev['defect_lines']}개 (고친 커밋이 지우거나 바꾼 Python 소스 줄, 빈 줄·주석 제외), 들여온 커밋 {ev['introducing_commits']}개",
        "- 들여올 때 상태: " + ", ".join(f"{k} {v}" for k, v in c.items()),
        f"- **공백 비율 {ev['gap_ratio']}** = gap / (gap + covered + import_only)",
        f"- covered 결함 줄 {c.get('covered', 0)}개 중 그 줄의 분기 일부가 실행되지 않았던 줄: {ev.get('covered_with_branch_gap', '-')}개",
        "",
        "| 들여온 커밋 | 제목 | 테스트 | 판정 | 결함 줄 | gap | covered | import_only | 기타 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in ev["rows"]:
        cc = _count(ln["status"] for ln in r["lines"])
        other = sum(v for k, v in cc.items() if k not in ("gap", "covered", "import_only"))
        lines.append(
            f"| `{r['sha']}` | {r['subject']} | {r['status']} | {r.get('decision', '-')} | {len(r['lines'])} | "
            f"{cc.get('gap', 0)} | {cc.get('covered', 0)} | {cc.get('import_only', 0)} | {other} |"
        )
    if ro := ev.get("review_order"):
        a, b = ro["by_gap_size"], ro["source_order"]
        lines += [
            "",
            f"## 검토 순서 (결함 줄이 공백에 있는 커밋 {ro['commits']}개, 회귀 지표)",
            "",
            "| 순서 | 첫 그룹에 결함 | MRR | 결함 그룹 끝까지 읽는 공백 줄 (합계·중앙값) | 첫 결함 줄까지 읽는 공백 줄 (합계·중앙값) |",
            "|---|---|---|---|---|",
            *(
                f"| {label} | {x['top1']}/{ro['commits']} | {x['mrr']} | {x['lines_read_total']} · {x['lines_read_median']} | "
                f"{x['lines_to_defect_total']} · {x['lines_to_defect_median']} |"
                for label, x in (("공백 줄 수", a), ("소스 순서", b))
            ),
            "",
            "규칙을 고른 데이터로 다시 잰 값이다. 구현이 규칙을 재현하는지 보는 지표이고, 일반화 성능이나 결함 예측력을 뜻하지 않는다.",
        ]
    lines += [
        "",
        "상태 설명: gap = 들어올 때 어떤 테스트도 실행하지 않음, covered = 테스트가 실행함(그런데도 결함이 남음), "
        "import_only = 모듈을 불러올 때만 실행, not_changed = blame 결과가 그 커밋의 변경 줄과 맞지 않음, "
        "unknown = coverage 없음(첫 커밋·실행 실패).",
        "",
    ]
    return "\n".join(lines)
