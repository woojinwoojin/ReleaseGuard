"""Stage 2.1 테스트 추가 T4 — 2.0 mutant #37 (b67e806 src/normalization/bs_sections.py:23 is_held_for_sale, or → and)
명세: held_for_sale_adjustment는 표준 ID(HFS_*_IDS) 행과 이름이 '매각예정자산'·'매각예정부채'인 행을 모두 매각예정으로 본다
(같은 파일의 hfs_rows 조건). 표준 ID나 이름 중 하나면 매각예정 행이다.
"""
from src.normalization.bs_sections import is_held_for_sale
from tests.test_bs_sections import NONSTD, bs  # 기존 헬퍼 재사용


def test_held_for_sale_by_standard_id_or_by_name():
    by_id = bs(1, "ifrs-full_NoncurrentAssetsOrDisposalGroupsClassifiedAsHeldForSale", "처분자산집단", "10")
    by_name = bs(2, NONSTD, "매각예정자산", "10")
    assert is_held_for_sale(by_id)
    assert is_held_for_sale(by_name)
