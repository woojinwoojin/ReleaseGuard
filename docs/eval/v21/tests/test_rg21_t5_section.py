"""Stage 2.1 테스트 추가 T5 — 평가 B D2 첫 mutant (b67e806 src/normalization/bs_sections.py:51, hfs != 0 → hfs != 1)
명세: 모듈 docstring '항목 합이 소계와 원 단위까지 같을 때만 확인' — 매각예정 행을 더해 소계와 같으면 확인이다 (금액과 관계없이).
이 mutant는 매각예정 금액이 정확히 1원일 때만 동작이 달라진다.
"""
from src.normalization.bs_sections import annotate_sections
from tests.test_bs_sections import bs  # 기존 헬퍼 재사용


def test_section_confirmed_when_held_for_sale_of_one_won_closes_the_sum():
    rows = [
        bs(1, "ifrs-full_CurrentAssets", "유동자산", "101"),
        bs(2, "ifrs-full_Inventories", "재고자산", "100"),
        bs(3, "ifrs-full_NoncurrentAssetsOrDisposalGroupsClassifiedAsHeldForSale", "매각예정자산", "1"),
        bs(4, "ifrs-full_NoncurrentAssets", "비유동자산", "0"),
    ]
    annotate_sections(rows)
    assert rows[1]["bs_section_confirmed"] is True
