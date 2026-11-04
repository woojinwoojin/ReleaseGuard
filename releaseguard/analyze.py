"""1~7단계를 순서대로 실행하고 결과를 dict로 만든다 (JSON으로 그대로 저장)."""

from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .agent_tools import RepoView
from .classify import RuleSet, classify
from .compare import shared_test_context_changes, file_change_evidence
from .decide import (
    FLAKY, INCOMPARABLE, NEW_TEST_FAILING, PRE_EXISTING, REGRESSION, RULES_VERSION, UNKNOWN, decide,
)
from .gaps import FileLines, compute
from .git_ops import Change, collect, list_files, read_file
from .related_tests import coverage_status, find_related
from .runner import (
    COVERAGE_VERSION, DEFAULT_TIMEOUT, PYTEST_COV_VERSION, RunResult, TestCase, check_python, find_python, host_secret_names, python_version, run_tests,
    snapshot_warnings,
)

# (RepoView, 공백이 있는 파일들) → {"items": 공백별 설명, "meta": 합계}
ExplainRunner = Callable[[RepoView, list[FileLines]], dict]


def _test_file(nodeid: str) -> str:
    return nodeid.split("::", 1)[0]


def compare_failures(change: Change, files: list[dict], failed: list[TestCase], python: Path, timeout: int) -> tuple[list[dict], list[dict]]:
    """head에서 실패한 테스트마다 비교 상태를 정한다. (실패 목록, 재실행 기록)

    1. head에서 실패한 테스트만 한 번 더 → 통과하면 FLAKY (통과로 치지 않는다)
    2. 남은 실패의 테스트 파일을 base에서 실행 (node id가 아니라 파일 단위: base에 없는 테스트는 '수집 안 됨'으로 드러난다)
       - base에 파일이 없거나 그 테스트가 수집되지 않음 → NEW_TEST_FAILING
       - base 실행이 결과를 내지 못함 (수집 오류·시간 초과) → UNKNOWN
       - base에서 통과(또는 건너뜀) → REGRESSION
       - base에서도 실패 → compare.py의 조건(테스트 정의·공유 맥락·실패 지문)이 모두 확인되면 PRE_EXISTING,
         하나라도 아니거나 확인하지 못하면 INCOMPARABLE. 근거는 comparison_evidence에 남긴다.
    head와 base는 같은 .venv로 돌린다. 그래서 의존성이 바뀐 커밋은 비교 조건이 같다고 볼 수 없다.
    PRE_EXISTING은 "관찰된 실패가 원래도 있었다"는 뜻이지, 이번 커밋에 다른 회귀가 없다는 보증이 아니다.
    """
    reruns = []
    ids = [t.nodeid for t in failed]
    again = run_tests(change.repo, change.head_sha, python, with_coverage=False, nodeids=ids, timeout=timeout)
    reruns.append(_rerun_record("head 재실행 (불안정 확인)", change.head_sha, again))
    again_out = {t.nodeid: t.outcome for t in again.tests} if again.status in ("passed", "failed") else {}
    flaky = {n for n in ids if again_out.get(n) == "passed"}

    base_files = set(list_files(change.repo, change.merge_base))
    to_run = sorted({_test_file(n) for n in ids if n not in flaky and _test_file(n) in base_files})
    base_out: dict[str, TestCase] | None = {}
    if to_run:
        base = run_tests(change.repo, change.merge_base, python, with_coverage=False, nodeids=to_run, timeout=timeout)
        reruns.append(_rerun_record("base 실행 (이번 변경 전에도 실패했는지)", change.merge_base, base))
        base_out = {t.nodeid: t for t in base.tests} if base.status in ("passed", "failed") else None

    changed_tests = {f["path"] for f in files if f["category"] == "test"}
    shared = shared_test_context_changes(files)
    out = []
    for t in failed:
        file = _test_file(t.nodeid)
        evidence = None
        if t.nodeid in flaky:
            comparison, base_status = FLAKY, None
        elif file not in base_files:
            comparison, base_status = NEW_TEST_FAILING, "absent"
        elif base_out is None:
            comparison, base_status = UNKNOWN, "unknown"
        elif (base_t := base_out.get(t.nodeid)) is None:
            comparison, base_status = NEW_TEST_FAILING, "absent"
        elif base_t.outcome in ("passed", "skipped"):
            comparison, base_status = REGRESSION, base_t.outcome
        else:
            evidence = _same_failure_evidence(change, file, file in changed_tests, t, base_t, shared)
            comparison = PRE_EXISTING if evidence["method"] else INCOMPARABLE
            base_status = "failed"
        out.append({
            "nodeid": t.nodeid, "message": t.message, "base_status": base_status, "comparison": comparison,
            "comparison_evidence": evidence,
        })
    return out, reruns


def _same_failure_evidence(change: Change, file: str, file_changed: bool, head: TestCase, base: TestCase, shared: list[str]) -> dict:
    """base·head 모두 실패한 테스트가 같은 실패인지의 근거. method가 None이면 확인되지 않은 것 (INCOMPARABLE)."""
    if file_changed:
        structure = file_change_evidence(read_file(change.repo, change.merge_base, file), read_file(change.repo, change.head_sha, file), head.nodeid)
    else:
        structure = {"test_function_same": True, "only_new_tests_added": None}
    evidence = {
        "test_nodeid_same": True,
        "test_file_changed": file_changed,
        **structure,
        "shared_test_context_unchanged": not shared,
        "shared_test_context_changes": shared,
        "failure_fingerprint_same": bool(head.fingerprint) and head.fingerprint == base.fingerprint,
        "method": None,
    }
    structure_ok = evidence["test_function_same"] is True and (not file_changed or evidence["only_new_tests_added"] is True)
    if structure_ok and evidence["shared_test_context_unchanged"] and evidence["failure_fingerprint_same"]:
        evidence["method"] = "matched_existing_failure_only_new_tests" if file_changed else "matched_existing_failure"
    return evidence


def _rerun_record(purpose: str, sha: str, run: RunResult) -> dict:
    return {"purpose": purpose, "sha": sha, "status": run.status, "seconds": run.seconds, "command": run.command}


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

    # 실패한 테스트는 head에서 한 번, base에서 한 번 더 돌려 비교 상태를 정한다.
    # 수집 오류(status=error)는 테스트 실패가 아니라 B04로만 다룬다.
    failed = [t for t in run.tests if t.outcome in ("failed", "error")] if run.status == "failed" else []
    failures, reruns = compare_failures(change, files, failed, py, timeout) if failed else ([], [])
    ran = run.status not in ("skipped", "not_run")
    test_run = {
        "status": run.status,
        "reason": run.reason,
        "seconds": run.seconds,
        "attempts": run.attempts,
        "python": run.python,
        "counts": run.counts(),
        "coverage": run.coverage is not None,
        "failures": failures,
        # 건너뛴 테스트와 사유. 스냅샷에 없는 파일(gitignore된 데이터 등) 때문에 skip되면 그 테스트가 실행했을 줄은
        # G01 공백으로만 보인다. 판정에는 아직 넣지 않는다 (새 테스트가 전부 skip돼도 SAFE가 나올 수 있음 — 한계).
        "skipped": [{"nodeid": t.nodeid, "reason": t.message} for t in run.tests if t.outcome == "skipped"],
        "snapshot_warnings": snapshot_warnings(change.repo, change.head_sha) if ran else [],
        # 무엇을 어떻게 돌렸는지: 보고서만 보고 같은 실행을 재현할 수 있게
        "record": {
            "head_sha": change.head_sha,
            "merge_base": change.merge_base,
            "command": run.command,
            "python": run.python,
            "python_version": python_version(py) if ran and py else None,
            "coverage_version": COVERAGE_VERSION,
            "pytest_cov_version": PYTEST_COV_VERSION,
            "branch": True,  # 1.5부터 분기도 잰다
            "timeout": timeout,
            "attempts": run.attempts,
            "reruns": reruns,
            # 테스트에 그대로 넘어가는 자격 증명류 호스트 환경 변수 이름 (값은 남기지 않음). 격리된 실행 환경이 아니라는 표시
            "host_secret_env": host_secret_names() if ran else [],
        },
    }

    # 4단계 Gaps
    lines = compute(files, change.added_lines, run.coverage) if run.coverage is not None else []
    decision, findings, scope = decide(files, test_run, lines, change.added_lines, ruleset.secrets)

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
        "scope": asdict(scope),
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
