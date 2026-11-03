"""1~7단계를 순서대로 실행하고 결과를 dict로 만든다 (JSON으로 그대로 저장)."""

from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .agent_tools import RepoView
from .classify import RuleSet, classify
from .decide import RULES_VERSION, decide
from .gaps import FileLines, compute
from .git_ops import collect, list_files, read_file
from .related_tests import coverage_status, find_related
from .runner import DEFAULT_TIMEOUT, RunResult, check_python, find_python, run_tests

# (RepoView, 공백이 있는 파일들) → {"items": 공백별 설명, "meta": 합계}
ExplainRunner = Callable[[RepoView, list[FileLines]], dict]


def _base_status(outcome: str | None) -> str:
    if outcome is None:
        return "absent"  # base에 없는 테스트 (이번 변경에서 추가됨)
    return "failed" if outcome in ("failed", "error") else "passed"


def _estimate_tests(change, files: list[dict], ruleset: RuleSet) -> list[dict]:
    """테스트를 돌릴 수 없을 때만 쓰는 추정 (이름 규칙 + import 검색). 보고서에 '추정'으로 표시한다."""
    tests = {
        p: read_file(change.repo, change.head_sha, p) if p.endswith(".py") else ""
        for p in list_files(change.repo, change.head_sha)
        if classify(p, ruleset)[0] == "test"
    }
    changed_tests = {f["path"] for f in files if f["category"] == "test" and f["status"] != "D"}
    out = []
    for f in files:
        if f["category"] == "source" and f["status"] != "D":
            related = find_related(f["path"], tests)
            out.append({"source": f["path"], "status": coverage_status(related, changed_tests, set()), "tests": [asdict(t) for t in related]})
    return out


def analyze(
    repo: Path,
    base: str,
    head: str,
    ruleset: RuleSet,
    *,
    python: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    explain: ExplainRunner | None = None,
) -> dict:
    change = collect(repo, base, head)

    files = []
    for f in change.files:
        category, rule_id = classify(f.path, ruleset)
        files.append({**asdict(f), "category": category, "evidence": f"rule:{rule_id}" if rule_id else None})

    # 3단계 Run: 문서만 바뀌었으면 돌리지 않는다.
    py = None
    if all(f["category"] == "docs" for f in files):
        run = RunResult("skipped", "문서만 바뀜")
    else:
        py = find_python(change.repo, python)
        problem = "대상 저장소에 .venv가 없음 (--python으로 지정)" if py is None else check_python(py)
        run = RunResult("not_run", problem) if problem else run_tests(change.repo, change.head_sha, py, timeout=timeout)

    # 실패한 테스트는 base에서 다시 돌려 "이번 변경이 깨뜨림"과 "원래 깨짐"을 나눈다.
    # 수집 오류(status=error)는 테스트 실패가 아니라 B04로만 다룬다.
    failed = [t for t in run.tests if t.outcome in ("failed", "error")] if run.status == "failed" else []
    base_outcomes: dict[str, str] = {}
    if failed:
        base_run = run_tests(change.repo, change.merge_base, py, with_coverage=False, nodeids=[t.nodeid for t in failed], timeout=timeout)
        base_outcomes = {t.nodeid: t.outcome for t in base_run.tests}
    test_run = {
        "status": run.status,
        "reason": run.reason,
        "seconds": run.seconds,
        "attempts": run.attempts,
        "python": run.python,
        "counts": run.counts(),
        "coverage": run.coverage is not None,
        "failures": [
            {"nodeid": t.nodeid, "message": t.message, "base_status": _base_status(base_outcomes.get(t.nodeid))} for t in failed
        ],
    }

    # 4단계 Gaps
    lines = compute(files, change.added_lines, run.coverage) if run.coverage is not None else []
    decision, findings = decide(files, test_run, lines, change.added_lines, ruleset.secrets)

    by_category: dict[str, int] = {}
    for f in files:
        by_category[f["category"]] = by_category.get(f["category"], 0) + 1
    result = {
        "tool": "releaseguard",
        "version": __version__,
        "classify_version": ruleset.version,
        "rules_version": RULES_VERSION,
        "repo": str(change.repo),
        "base": base,
        "head": head,
        "merge_base": change.merge_base,
        "head_sha": change.head_sha,
        "summary": {
            "files": len(files),
            "added": sum(f["added"] or 0 for f in files),
            "deleted": sum(f["deleted"] or 0 for f in files),
            "by_category": dict(sorted(by_category.items())),
        },
        "changed_files": files,
        "test_run": test_run,
        "lines": [asdict(fl) for fl in lines],
        "estimated_tests": _estimate_tests(change, files, ruleset) if run.status in ("not_run", "timeout") else None,
        "decision": decision,
        "findings": [asdict(f) for f in findings],
        "explanations": None,
        "agent": None,
        "agent_error": None,
    }

    # 6단계 Explain: 공백이 있을 때만. 실패해도 판정과 결과는 그대로 남긴다.
    if explain is not None and any(fl.gaps for fl in lines):
        try:
            out = explain(RepoView(change.repo, change.merge_base, change.head_sha), lines)
            result["explanations"], result["agent"] = out["items"], out["meta"]
        except Exception as e:
            result["agent_error"] = f"{type(e).__name__}: {e}"
    return result
