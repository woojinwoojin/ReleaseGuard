"""Stage 2.1 테스트 추가 T3 — 2.0 mutant #26 (568ea41 src/normalization/dart_facts.py:57 period_days, +1 → +2)
명세: MAX_REGULAR_DAYS = 371 '53주 보고기간까지는 정상 연간 범위', is_unusually_long docstring '53주를 넘는 기간'.
53주(371일, 시작·종료일 포함) 기간은 긴 기간이 아니고, 연간이다.
"""
from src.normalization.dart_facts import ANNUAL_REPORT_CODE, is_annual_period, is_unusually_long, period_days


def test_53_week_period_is_regular_and_annual():
    start, end = "2025-01-01", "2026-01-06"  # 시작·종료일 포함 371일 = 53주
    assert period_days(start, end) == 371
    assert not is_unusually_long(start, end)
    assert is_annual_period(start, end, ANNUAL_REPORT_CODE)


def test_calendar_year_has_365_days():
    assert period_days("2025-01-01", "2025-12-31") == 365
