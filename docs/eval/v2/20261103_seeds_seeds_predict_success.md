# ReleaseGuard Eval v2 — 결함을 심은 사례 (10/10 통과)

- 저장소: `C:\Project_Folder\predict-success` (임시 clone에서 실행) · base `895dbe4`

| id | 심은 변경 | 기대 | 결과 | 기대 규칙 | 발동 규칙 | 근거 | 통과 |
|---|---|---|---|---|---|---|---|
| S01 | 테스트가 지나가지 않는 새 분기 추가 (engine.combine) | REVIEW REQUIRED | REVIEW REQUIRED | G01 | G01 | src/metrics/engine.py:97-97 | ✓ |
| S02 | 테스트된 줄을 같은 동작으로 리팩터 (engine.combine) | SAFE | SAFE | - | - | - | ✓ |
| S03 | 기간 연도 비교를 깨뜨림 (engine.Input.period_problem) | BLOCK | BLOCK | B03 | B03 | tests/test_dart_collector.py::test_filing_is_stored_with_published_and_collected_dates (passed)<br>tests/test_metrics.py::test_normal_inputs_give_normal_result (passed)<br>tests/test_metrics.py::test_candidate_input_gives_reference_calculation_and_holds_score (passed)<br>tests/test_metrics.py::test_zero_current_liabilities_is_never_infinite (passed)<br>tests/test_metrics.py::test_reported_current_ratio_is_view_only_and_hfs_ratio_is_the_scoring_one (passed)<br>tests/test_metrics.py::test_cagr_uses_2022_and_2025_and_refuses_non_positive_start (passed)<br>tests/test_metrics.py::test_three_year_decline_is_not_called_stable (passed)<br>tests/test_metrics.py::test_peer_median_excludes_the_company_itself_and_is_validation_only (passed)<br>tests/test_metrics.py::test_short_fiscal_period_does_not_enter_cagr (passed)<br>tests/test_metrics.py::test_negative_denominator_or_balance_is_held_not_scored[interest_coverage-values0] (passed)<br>tests/test_metrics.py::test_negative_denominator_or_balance_is_held_not_scored[<lambda>-values1] (passed)<br>tests/test_metrics.py::test_negative_denominator_or_balance_is_held_not_scored[<lambda>-values2] (passed)<br>tests/test_metrics.py::test_negative_denominator_or_balance_is_held_not_scored[cash_to_short_term_debt-values3] (passed)<br>tests/test_metrics.py::test_negative_denominator_or_balance_is_held_not_scored[cash_to_short_term_debt-values4] (passed)<br>tests/test_metrics.py::test_negative_denominator_or_balance_is_held_not_scored[revenue_cagr_3y-values5] (passed)<br>tests/test_metrics.py::test_negative_numerator_from_losses_stays_an_observation (passed)<br>tests/test_trend.py::test_past_year_uses_prior_year_balances (passed)<br>tests/test_trend.py::test_revenue_yoy_growth (passed) | ✓ |
| S04 | 없는 이름을 import (수집 오류) | BLOCK | BLOCK | B04 | B04 | - | ✓ |
| S05 | 소스에 API 키를 넣음 | BLOCK | BLOCK | B01 | B01 | - | ✓ |
| S06 | README만 수정 | SAFE | SAFE | - | - | - | ✓ |
| S07 | 점수 테스트 파일을 지우고 보간 계산을 같은 동작으로 바꿈 | REVIEW REQUIRED | REVIEW REQUIRED | G01 | G01 | src/scoring/score.py:25-25 | ✓ |
| S08 | 의존성 추가 | REVIEW REQUIRED | REVIEW REQUIRED | R04 | R04 | - | ✓ |
| S09 | 어디서도 불리지 않는 새 모듈 추가 | REVIEW REQUIRED | REVIEW REQUIRED | G01 | G01 | src/metrics/extra.py:1-4 | ✓ |
| S10 | 설정 파일 주석만 수정 | SAFE | SAFE | - | - | - | ✓ |
