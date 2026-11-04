"""SAFE / REVIEW REQUIRED / BLOCK 판정 (5단계 Decide). 결정적 결과(테스트 실행·coverage·규칙)만 쓴다.

규칙 표는 docs/design.md의 "판정 규칙 v3". 에이전트는 판정에 들어가지 않는다.

SAFE는 "코드가 맞다"가 아니라 "ReleaseGuard가 검증할 수 있는 범위에서 검토 사유를 찾지 못했다"는 뜻이다.
그래서 검증하지 못한 변경이 있으면 SAFE를 내지 않고(E02), 검증 범위(scope)를 판정과 따로 남긴다.
"""

import re
from dataclasses import dataclass, field

from .classify import SecretPattern
from .gaps import FileLines

RULES_VERSION = "3.1"  # 3.1 (2026-11-04): 실패 비교에 테스트 정의·공유 맥락·실패 지문 조건 (compare.py)
SAFE, REVIEW, BLOCK, NOTE = "SAFE", "REVIEW REQUIRED", "BLOCK", "NOTE"
SEVERITY = {NOTE: -1, SAFE: 0, REVIEW: 1, BLOCK: 2}

# 검증 범위
COMPLETE, PARTIAL, UNSUPPORTED = "COMPLETE", "PARTIAL", "UNSUPPORTED"
# 테스트 실행이 근거를 만들지 못한 상태 (이때는 소스·테스트 변경도 검증하지 못한 것으로 본다)
RUN_NOT_ESTABLISHED = ("error", "timeout", "not_run")

# head에서 실패한 테스트의 비교 상태 (analyze.compare_failures가 정한다)
REGRESSION = "REGRESSION"  # base에서는 통과
NEW_TEST_FAILING = "NEW_TEST_FAILING"  # base에 없는 테스트
PRE_EXISTING = "PRE_EXISTING"  # base에서도 실패, 같은 실패로 확인됨 (compare.py의 조건)
INCOMPARABLE = "INCOMPARABLE"  # base에서도 실패지만 같은 실패로 확인하지 못함
UNKNOWN = "UNKNOWN"  # base 재실행이 결과를 내지 못함
FLAKY = "FLAKY"  # head에서 다시 돌리니 통과
# 원래부터 실패했다고 확인되지 않은 실패 → B03 (BLOCK)
NOT_CONFIRMED_PRE_EXISTING = (REGRESSION, NEW_TEST_FAILING, INCOMPARABLE, UNKNOWN)

# 판정 근거를 보고서에서 두 묶음으로 나눈다: 검증이 성립하지 않은 것 / 검증해서 찾은 것
NOT_VERIFIED_RULES = ("B04", "E01", "E02", "E03")


@dataclass
class Finding:
    rule_id: str
    decision: str  # NOTE는 판정에 영향 없는 참고 표시
    message: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class Scope:
    status: str  # COMPLETE | PARTIAL | UNSUPPORTED
    unverified: list[dict] = field(default_factory=list)  # {"path", "category", "kind", "reason"}


def run_established(run_status: str, has_coverage: bool) -> bool:
    """테스트 실행이 검증 근거(테스트별 실행 줄)를 만들었는가.

    no_tests는 근거가 있다고 본다: "어떤 테스트도 이 줄을 실행하지 않는다"는 측정 결과이고, G01로 드러난다.
    passed·failed인데 coverage를 못 얻었으면 근거가 없다 (E01).
    """
    if run_status in RUN_NOT_ESTABLISHED:
        return False
    if run_status in ("passed", "failed", "no_tests"):
        return has_coverage
    return True  # skipped (문서만 바뀜): 검증할 소스가 없다


def _unverified(f: dict, established: bool) -> tuple[str, str] | None:
    """이 변경 파일을 검증하지 못하는 (종류, 이유). 검증했거나 검증할 필요가 없으면(문서) None.

    종류: run(테스트 실행이 근거를 못 만듦 → E01·B04) | deps(R04) | outside(검증 범위 밖 → E02)
    """
    category, path = f["category"], f["path"]
    if category == "docs":
        return None
    if category == "test" or (category == "source" and path.endswith(".py")):
        return None if established else ("run", "테스트 실행이 근거(coverage)를 만들지 못함")
    if category == "deps":
        return "deps", "의존성 변경은 테스트 환경에 반영되지 않음"
    reason = {
        "source": "Python이 아닌 소스는 coverage를 재지 않음",
        "config": "설정 파일은 검증하지 않음",
        "data": "데이터 파일은 검증하지 않음",
    }.get(category, "분류 규칙에 없는 파일")
    return "outside", reason


def compute_scope(files: list[dict], run_status: str, has_coverage: bool = True) -> Scope:
    established = run_established(run_status, has_coverage)
    relevant = [f for f in files if f["category"] != "docs"]
    unverified = [
        {"path": f["path"], "category": f["category"], "kind": u[0], "reason": u[1]}
        for f in relevant
        if (u := _unverified(f, established))
    ]
    if not unverified:
        return Scope(COMPLETE)
    return Scope(UNSUPPORTED if len(unverified) == len(relevant) else PARTIAL, unverified)


def _secret_hits(added_lines: dict[str, list[tuple[int, str]]], secrets: tuple[SecretPattern, ...]) -> list[str]:
    compiled = [(s.id, re.compile(s.pattern)) for s in secrets]
    hits = []
    for path, lines in sorted(added_lines.items()):
        for lineno, text in lines:
            for sid, pat in compiled:
                if pat.search(text):
                    hits.append(f"{path}:{lineno} ({sid})")  # 값 자체는 남기지 않는다
    return hits


def decide(
    files: list[dict],
    run: dict,
    lines: list[FileLines],
    added_lines: dict[str, list[tuple[int, str]]],
    secrets: tuple[SecretPattern, ...],
) -> tuple[str, list[Finding], Scope]:
    """files: {"path", "status", "category"} 목록. run: analyze가 만든 test_run 요약.

    run["failures"][i]["comparison"]: 위의 비교 상태 중 하나
    run["snapshot_warnings"]: 스냅샷이 저장소와 다를 수 있는 이유
    """
    findings: list[Finding] = []
    scope = compute_scope(files, run["status"], bool(run["coverage"]))

    def by(category: str, deleted: bool | None = None) -> list[str]:
        return [f["path"] for f in files if f["category"] == category and (deleted is None or (f["status"] == "D") == deleted)]

    def failed(*states: str) -> list[str]:
        return [f"{f['nodeid']} ({f['comparison']})" for f in run["failures"] if f["comparison"] in states]

    if hits := _secret_hits(added_lines, secrets):
        findings.append(Finding("B01", BLOCK, "추가된 줄에 비밀값 패턴이 있습니다.", hits))
    if broken := failed(*NOT_CONFIRMED_PRE_EXISTING):
        findings.append(Finding("B03", BLOCK, "head에서 실패하는 테스트가 있고, 원래부터 실패했다고 확인되지 않았습니다.", broken))
    if run["status"] == "error":
        findings.append(Finding("B04", BLOCK, "테스트를 수집·실행하지 못했습니다 (import 오류 등).", [run["reason"] or ""]))
    if gaps := [f"{fl.path}:{s}-{e}" if s != e else f"{fl.path}:{s}" for fl in lines for s, e in fl.gaps]:
        findings.append(Finding("G01", REVIEW, "바뀐 줄 중 어떤 테스트도 실행하지 않는 곳이 있습니다.", gaps))
    if old := failed(PRE_EXISTING):
        findings.append(Finding("T01", REVIEW, "base에서도 같은 조건으로 실패하던 테스트가 있습니다.", old))
    if flaky := failed(FLAKY):
        findings.append(Finding("T02", REVIEW, "실패했다가 다시 돌리면 통과하는 테스트가 있습니다 (결과가 불안정).", flaky))
    if paths := by("deps"):
        findings.append(Finding("R04", REVIEW, "의존성이 바뀌었습니다. 테스트 실행 환경이 실제와 다를 수 있습니다.", paths))
    no_coverage = run["status"] in ("passed", "failed", "no_tests") and not run["coverage"]
    if run["status"] in ("timeout", "not_run") or no_coverage:
        findings.append(Finding("E01", REVIEW, "테스트를 실행하지 못했거나 coverage를 얻지 못해 검증하지 못했습니다.", [run["reason"] or run["status"]]))
    if outside := [f"{u['path']} ({u['reason']})" for u in scope.unverified if u["kind"] == "outside"]:
        findings.append(Finding("E02", REVIEW, "ReleaseGuard가 검증하지 못하는 변경이 있습니다 (검증 범위 밖).", outside))
    if warnings := run.get("snapshot_warnings"):
        findings.append(Finding("E03", REVIEW, "테스트를 돌린 스냅샷이 저장소의 실제 파일과 다를 수 있습니다.", warnings))

    if paths := by("source", deleted=True):
        findings.append(Finding("N06", NOTE, "소스가 삭제되었습니다. 남은 코드가 참조하면 테스트 실패(B03·B04)로 드러납니다.", paths))

    decision = max((f.decision for f in findings), key=SEVERITY.get, default=SAFE)
    return (SAFE if decision == NOTE else decision), findings, scope
