"""SAFE / REVIEW REQUIRED / BLOCK 판정 (5단계 Decide). 규칙만 쓰고 LLM은 쓰지 않는다.

규칙 표는 docs/design.md의 "판정 규칙 v1".
"""

import re
from dataclasses import dataclass, field

from .classify import SecretPattern
from .related_tests import Coverage

SAFE, REVIEW, BLOCK = "SAFE", "REVIEW REQUIRED", "BLOCK"
SEVERITY = {SAFE: 0, REVIEW: 1, BLOCK: 2}


@dataclass
class Finding:
    rule_id: str
    decision: str
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
    coverage: list[Coverage],
    added_lines: dict[str, list[tuple[int, str]]],
    secrets: tuple[SecretPattern, ...],
    agent_high_risks: list[dict] = (),
) -> tuple[str, list[Finding]]:
    """files: {"path", "status", "category"} 목록. 발동한 규칙을 모두 돌려준다.

    agent_high_risks: 근거가 확인된(verified) HIGH 위험만 넘긴다.
    """
    findings: list[Finding] = []

    def by(category: str, deleted: bool | None = None) -> list[str]:
        return [
            f["path"]
            for f in files
            if f["category"] == category and (deleted is None or (f["status"] == "D") == deleted)
        ]

    if hits := _secret_hits(added_lines, secrets):
        findings.append(Finding("B01", BLOCK, "추가된 줄에 비밀값 패턴이 있습니다.", hits))
    if srcs := [c.source for c in coverage if c.status == "test_deleted"]:
        findings.append(Finding("B02", BLOCK, "수정된 소스의 관련 테스트가 삭제되었습니다.", srcs))
    if srcs := [c.source for c in coverage if c.status == "test_unchanged"]:
        findings.append(Finding("R01", REVIEW, "관련 테스트가 있으나 함께 수정되지 않았습니다.", srcs))
    if srcs := [c.source for c in coverage if c.status == "no_test"]:
        findings.append(Finding("R02", REVIEW, "관련 테스트를 찾지 못했습니다.", srcs))
    if paths := by("config"):
        findings.append(Finding("R03", REVIEW, "설정이 변경되었습니다.", paths))
    if paths := by("deps"):
        findings.append(Finding("R04", REVIEW, "의존성이 변경되었습니다.", paths))
    if paths := by("data"):
        findings.append(Finding("R05", REVIEW, "데이터가 변경되었습니다.", paths))
    if paths := by("source", deleted=True):
        findings.append(Finding("R06", REVIEW, "소스가 삭제되었습니다.", paths))
    if agent_high_risks:
        evidence = [f"{r['title']} ({', '.join(r['evidence'])})" for r in agent_high_risks]
        findings.append(Finding("R07", REVIEW, "에이전트가 근거와 함께 HIGH 위험을 제시했습니다.", evidence))

    decision = max((f.decision for f in findings), key=SEVERITY.get, default=SAFE)
    return decision, findings
