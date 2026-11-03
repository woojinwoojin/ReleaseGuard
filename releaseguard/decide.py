"""SAFE / REVIEW REQUIRED / BLOCK 판정 (5단계 Decide). 결정적 결과(테스트 실행·coverage·규칙)만 쓴다.

규칙 표는 docs/design.md의 "판정 규칙 v2". 에이전트는 판정에 들어가지 않는다.
"""

import re
from dataclasses import dataclass, field

from .classify import SecretPattern
from .gaps import FileLines

RULES_VERSION = 2
SAFE, REVIEW, BLOCK, NOTE = "SAFE", "REVIEW REQUIRED", "BLOCK", "NOTE"
SEVERITY = {NOTE: -1, SAFE: 0, REVIEW: 1, BLOCK: 2}


@dataclass
class Finding:
    rule_id: str
    decision: str  # NOTE는 판정에 영향 없는 참고 표시
    message: str
    evidence: list[str] = field(default_factory=list)


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
) -> tuple[str, list[Finding]]:
    """files: {"path", "status", "category"} 목록. run: analyze가 만든 test_run 요약.

    run["failures"]의 base_status: passed(이번 변경이 깨뜨림) | failed(원래 깨짐) | absent(새 테스트)
    """
    findings: list[Finding] = []

    def by(category: str, deleted: bool | None = None) -> list[str]:
        return [f["path"] for f in files if f["category"] == category and (deleted is None or (f["status"] == "D") == deleted)]

    if hits := _secret_hits(added_lines, secrets):
        findings.append(Finding("B01", BLOCK, "추가된 줄에 비밀값 패턴이 있습니다.", hits))
    if broken := [f["nodeid"] for f in run["failures"] if f["base_status"] != "failed"]:
        findings.append(Finding("B03", BLOCK, "이번 변경으로 실패하는 테스트가 있습니다.", broken))
    if run["status"] == "error":
        findings.append(Finding("B04", BLOCK, "테스트를 수집·실행하지 못했습니다 (import 오류 등).", [run["reason"] or ""]))
    if gaps := [f"{fl.path}:{s}-{e}" if s != e else f"{fl.path}:{s}" for fl in lines for s, e in fl.gaps]:
        findings.append(Finding("G01", REVIEW, "바뀐 줄 중 어떤 테스트도 실행하지 않는 곳이 있습니다.", gaps))
    if old := [f["nodeid"] for f in run["failures"] if f["base_status"] == "failed"]:
        findings.append(Finding("T01", REVIEW, "base에서도 실패하던 테스트가 있습니다.", old))
    if paths := by("deps"):
        findings.append(Finding("R04", REVIEW, "의존성이 바뀌었습니다. 테스트 실행 환경이 실제와 다를 수 있습니다.", paths))
    no_coverage = run["status"] in ("passed", "failed", "no_tests") and not run["coverage"]
    if run["status"] in ("timeout", "not_run") or no_coverage:
        findings.append(Finding("E01", REVIEW, "테스트를 실행하지 못했거나 coverage를 얻지 못해 검증하지 못했습니다.", [run["reason"] or run["status"]]))

    if paths := by("config"):
        findings.append(Finding("N03", NOTE, "설정이 바뀌었습니다 (판정에는 반영하지 않음).", paths))
    if paths := by("data"):
        findings.append(Finding("N05", NOTE, "데이터가 바뀌었습니다 (판정에는 반영하지 않음).", paths))
    if paths := by("source", deleted=True):
        findings.append(Finding("N06", NOTE, "소스가 삭제되었습니다. 남은 코드가 참조하면 테스트 실패(B03·B04)로 드러납니다.", paths))

    decision = max((f.decision for f in findings), key=SEVERITY.get, default=SAFE)
    return (SAFE if decision == NOTE else decision), findings
