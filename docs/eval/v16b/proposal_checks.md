# 제안 확인 재실행 — agent_cases_v2.yaml · docs/eval/v16b

저장된 에이전트 응답에 Test Suggestion Validator만 다시 돌린 결과 (API 호출 0회). 규칙을 이 사례들을 보고 만들었으므로 회귀 확인이지 일반화 평가가 아니다.

- 응답 16개 · PASS 10 · WARN 6 · UNKNOWN 0
- S01 6개 (기존 자동 지표 `suggested_in_file_with_skips`와 일치 16/16) · S03 확정 2개

| 사례 | 실행 | 제안 | 상태 | 경고 | 파일의 skip | skip 원인 |
|---|---|---|---|---|---|---|
| F3 | 1 | `tests/test_tools.py` → `test_compare_periods_unknown_category` | PASS | - | - | - |
| N1 | 1 | `tests/test_tools.py` → `test_dimension_breakdown_filters_category` | PASS | - | - | - |
| F1 | 1 | `tests/test_market.py` → `test_latest_raw_returns_latest_run_with_metadata_and_errors_when_missing` | PASS | - | - | - |
| F2 | 1 | `tests/test_market.py` → `test_guideline_section_formats_tables_and_notes` | WARN | S01 | 1/20 | CAUSE_CORRELATED |
| N2 | 1 | `tests/test_dart_facts.py` → `test_load_published_filings_collects_only_parseable_annual_reports` | PASS | - | - | - |
| N3 | 1 | `tests/test_app.py` → `test_unverified_evidence_is_marked` | WARN | S01, S03 | 7/7 | CAUSE_CORRELATED |
| B1 | 1 | `tests/test_app.py` → `test_selecting_new_conversation_clears_loaded_turns` | WARN | S01 | 5/5 | CAUSE_CORRELATED |
| B2 | 1 | `tests/test_api.py` → `test_chat_stream_unexpected_error_becomes_generic_error_event` | PASS | - | - | - |
| F3 | 2 | `tests/test_tools.py` → `test_compare_periods_unknown_category_returns_error` | PASS | - | - | - |
| N1 | 2 | `tests/test_tools.py` → `test_dimension_breakdown_unknown_category` | PASS | - | - | - |
| F1 | 2 | `tests/test_market.py` → `test_latest_raw_raises_when_no_collected_runs_exist` | PASS | - | - | - |
| F2 | 2 | `tests/test_market.py` → `test_report_includes_guideline_section_when_guidelines_are_present` | WARN | S01 | 1/20 | CAUSE_CORRELATED |
| N2 | 2 | `tests/test_dart_facts.py` → `test_load_published_filings_collects_only_parsable_annual_reports` | PASS | - | - | - |
| N3 | 2 | `tests/test_app.py` → `test_unverified_evidence_is_marked` | WARN | S01, S03 | 7/7 | CAUSE_CORRELATED |
| B1 | 2 | `tests/test_app.py` → `test_conversation_selectbox_uses_local_time_label` | WARN | S01 | 5/5 | CAUSE_CORRELATED |
| B2 | 2 | `tests/test_api.py` → `test_chat_stream_unexpected_exception_becomes_generic_error_event` | PASS | - | - | - |
