"""Stage 2.1 테스트 추가 T2 — 2.0 mutant #23 (82e4305 src/normalization/account_map.py:40 evidence, or → and)
명세: docs/decisions.md D6 — 계정 매핑 규칙은 표준코드 규칙과 '근거(why)를 적은 완전 일치 이름 규칙' 두 종류다.
증거 기록은 어느 규칙으로 매핑됐는지 남겨야 한다 (표준코드 규칙은 그 코드, 이름 규칙은 name:이름).
"""
from src.normalization.account_map import evidence
from tests.test_account_map import NONSTD, row  # 기존 헬퍼 재사용


def test_evidence_names_the_rule_that_matched():
    r1 = row("BS", "ifrs-full_Inventories", "재고자산")
    r2 = row("BS", NONSTD, "단기차입금")
    ev = evidence([(r1, {"account_id": "ifrs-full_Inventories"}), (r2, {"nonstandard_name": "단기차입금", "why": "원문 확인"})], "matched")
    assert [e["rule"] for e in ev] == ["ifrs-full_Inventories", "name:단기차입금"]
