# 제안 확인 재실행 — agent_cases.yaml · docs/eval/v16

저장된 에이전트 응답에 Test Suggestion Validator만 다시 돌린 결과 (API 호출 0회). 규칙을 이 사례들을 보고 만들었으므로 회귀 확인이지 일반화 평가가 아니다.

- 응답 16개 · PASS 10 · WARN 6 · UNKNOWN 0
- S01 6개 (기존 자동 지표 `suggested_in_file_with_skips`와 일치 — 이 실행에는 그 지표가 없음) · S03 확정 0개

| 사례 | 실행 | 제안 | 상태 | 경고 | 파일의 skip | skip 원인 |
|---|---|---|---|---|---|---|
| F3 | 1 | `tests/test_tools.py` → `test_compare_periods_unknown_category_returns_error` | PASS | - | - | - |
| N1 | 1 | `tests/test_tools.py` → `test_dimension_breakdown_unknown_category` | PASS | - | - | - |
| F1 | 1 | `tests/test_market.py` → `test_latest_raw_returns_latest_run_or_raises_when_missing` | PASS | - | - | - |
| F2 | 1 | `tests/test_market.py` → `test_report_includes_guideline_section_and_does_not_change_score_output` | WARN | S01 | 1/20 | CAUSE_CORRELATED |
| N2 | 1 | `tests/test_dart_collector.py` → `test_load_published_filings_collects_only_annual_reports_from_response_json` | PASS | - | - | - |
| N3 | 1 | `tests/test_app.py` → `test_unverified_evidence_adds_warning_note` | WARN | S01 | 7/7 | CAUSE_CORRELATED |
| B1 | 1 | `tests/test_app.py` → `test_selecting_new_conversation_clears_current_turns` | WARN | S01 | 5/5 | CAUSE_CORRELATED |
| B2 | 1 | `tests/test_api.py` → `test_chat_stream_unexpected_exception_is_generic_error_event` | PASS | - | - | - |
| F3 | 2 | `tests/test_tools.py` → `test_compare_periods_unknown_category` | PASS | - | - | - |
| N1 | 2 | `tests/test_tools.py` → `test_dimension_breakdown_invalid_category` | PASS | - | - | - |
| F1 | 2 | `tests/test_market.py` → `test_latest_raw_returns_most_recent_run_and_errors_when_missing` | PASS | - | - | - |
| F2 | 2 | `tests/test_market.py` → `test_report_includes_guideline_section_with_facts_and_judgments` | WARN | S01 | 1/20 | CAUSE_CORRELATED |
| N2 | 2 | `tests/test_dart_facts.py` → `test_load_published_filings_collects_only_annual_reports_from_response_json` | PASS | - | - | - |
| N3 | 2 | `tests/test_app.py` → `test_unverified_evidence_adds_warning_note` | WARN | S01 | 7/7 | CAUSE_CORRELATED |
| B1 | 2 | `tests/test_app.py` → `test_pick_conversation_loads_selected_history_and_resets_on_new_conversation` | WARN | S01 | 5/5 | CAUSE_CORRELATED |
| B2 | 2 | `tests/test_api.py` → `test_chat_stream_unexpected_exception_is_generic_error_event` | PASS | - | - | - |
