# ReleaseGuard 보고서 — REVIEW REQUIRED

- 저장소: `C:\Project_Folder\predict-success`
- 비교: `142912b~1...142912b` (merge-base `c9824b0` → head `142912b`)
- 변경: 파일 10개, +289 / -85 (config 1, data 3, docs 1, source 3, test 2)

## 판정 근거

| 규칙 | 판정 | 내용 | 근거 |
|---|---|---|---|
| G01 | REVIEW REQUIRED | 바뀐 줄 중 어떤 테스트도 실행하지 않는 곳이 있습니다. | `src/market/run_market.py:71`<br>`src/market/run_market.py:90`<br>`src/market/run_market.py:265`<br>`src/market/run_market.py:308`<br>`src/market/run_market.py:317-318`<br>`src/market/run_market.py:320`<br>`src/market/run_market.py:368-369`<br>`src/market/run_market.py:376-377`<br>`src/market/run_market.py:379-381`<br>`src/market/run_market.py:417`<br>`src/market/run_market.py:442-444`<br>`src/market/run_market.py:446-448`<br>`src/market/run_market.py:453`<br>`src/market/run_market.py:455`<br>`src/market/run_market.py:465`<br>`src/market/run_market.py:475-476`<br>`src/report/evidence_report.py:201-202` |

참고 (판정에 반영하지 않음):
- N03 설정이 바뀌었습니다 (판정에는 반영하지 않음). `configs/market_v1.yaml`
- N05 데이터가 바뀌었습니다 (판정에는 반영하지 않음). `data/manual/market_links.csv`, `data/manual/stat_guideline_facts.csv`, `data/manual/stat_guideline_judgments.csv`

## 테스트 실행

- 결과: **모두 통과** — 통과 180, 실패 0, 오류 0, 건너뜀 1 (5.5초)

## 바뀐 줄의 검증 상태

| 파일 | 바뀐 실행 줄 | 테스트가 실행 | import 시점만 | 검증 공백 | 실행한 테스트 |
|---|---|---|---|---|---|
| `src/market/run_market.py` | 81 | 47 | 8 | **26** (71, 90, 265, 308, 317-318, 320, 368-369, 376-377, 379-381, 417, 442-444, 446-448, 453, 455, 465, 475-476) | `tests/test_market.py::test_continuity_judgment_flows_to_year_rows_and_spans`<br>`tests/test_market.py::test_full_confirmation_passes_only_for_explicitly_covered_years`<br>`tests/test_market.py::test_guidelines_pass_when_raw_hash_and_evidence_match`<br>`tests/test_market.py::test_guidelines_stop_on_broken_evidence`<br>`tests/test_market.py::test_official_growth_mismatch_is_reported`<br>`tests/test_market.py::test_pinned_raw_stops_when_file_changed_after_collection`<br>`tests/test_market.py::test_pinned_raw_uses_the_named_run_not_the_latest`<br>`tests/test_market.py::test_stats_check_computed_growth_against_official_and_mark_caution_pair`<br>외 1개 |
| `src/metrics/engine.py` | 6 | 5 | 1 | **0** (-) | `tests/test_metrics.py::test_cagr_uses_2022_and_2025_and_refuses_non_positive_start`<br>`tests/test_metrics.py::test_candidate_input_gives_reference_calculation_and_holds_score`<br>`tests/test_metrics.py::test_excluded_company_gets_no_peer_score_not_zero`<br>`tests/test_metrics.py::test_negative_denominator_or_balance_is_held_not_scored`<br>`tests/test_metrics.py::test_negative_numerator_from_losses_stays_an_observation`<br>`tests/test_metrics.py::test_normal_inputs_give_normal_result`<br>`tests/test_metrics.py::test_peer_median_excludes_the_company_itself_and_is_validation_only`<br>`tests/test_metrics.py::test_period_year_must_match_requested_year`<br>외 10개 |
| `src/report/evidence_report.py` | 2 | 0 | 0 | **2** (201-202) | - |

## 검증 공백 설명 (에이전트, 판정에 반영하지 않음)

### `src/market/run_market.py` 379-381줄

- 바뀐 동작: 연평균 성장률 요약 표의 각 구간 행에 `cagr_span_roles`에서 가져온 용도와 `definition_continuity`, `caution`을 함께 출력하도록 바뀌었습니다. 또 바로 아래 설명 문구에서 ‘대조’와 ‘정의 연속성’, ‘직접 비교 가능’의 의미를 분리해 안내합니다.
- 실행 조건: `summary` 데이터프레임을 렌더링해 `| 기간 | 용도 | 연평균 성장률 | 정의 연속성 (Q3) | 주의 |` 표를 쓰는 경로에서, 특히 `config['cagr_span_roles']`에 해당 구간 역할이 있고 `summary.itertuples()`가 한 줄 이상 돌 때 실행됩니다.
- 제안 테스트: `tests/test_market.py` → `test_summary_table_includes_role_continuity_and_caution`
  - 준비: `build_stats()`가 `summary`를 만든 뒤, `run_market`의 마크다운 렌더링 경로를 한 번 실행하도록 `config['cagr_span_roles']`에 `2022→2025` 역할을 넣고, `continuity`에 인접 연도 판정 1개를 제공한 입력으로 보고서를 생성한다.
  - 확인: 생성된 출력에 `| 2022→2025 (3년) |` 행이 있고, 같은 행의 용도 칸에 `config['cagr_span_roles']['2022→2025']` 값이 들어가며, `정의 연속성 (Q3)` 칸과 `주의` 칸이 함께 렌더링되는 것을 확인한다. 또한 설명 문구로 `- '대조'는 계산 증감률과 공식 증감률의 산술 일치일 뿐이다.`가 포함되는지 확인한다.
- 근거: `file:src/market/run_market.py:378-382`, `tool:#1` — **근거 미확인** (tool:#1)

### `src/market/run_market.py` 442-444줄

- 바뀐 동작: `main()`이 설정 파일의 `base_statistic`를 읽은 뒤, `runs`로 전달된 실행 ID가 있으면 그 값을 우선해 `pinned_raw()`에 넘기고, 없으면 설정의 `raw_run`을 쓰도록 선택합니다. 즉, 같은 후보 ID라도 명령행/호출 인자로 넘긴 수집본이 설정값보다 우선합니다.
- 실행 조건: `main(as_of, runs)` 호출 시 `runs` 딕셔너리에 `base_statistic.candidate_id`에 해당하는 run_id가 들어 있고, 동시에 설정의 `base_statistic.raw_run`도 존재하는 경우입니다.
- 제안 테스트: `tests/test_market.py` → `test_main_prefers_explicit_runs_over_config_raw_run`
  - 준비: `yaml.safe_load`는 `base_statistic.candidate_id='M01'`, `base_statistic.raw_run='config-run'`인 설정을 반환하게 하고, `runs={'M01': 'explicit-run'}`으로 `main()`을 호출한다. `pinned_raw()`는 전달받은 run_id를 기록만 하게, `parse_table`/`build_stats`/`build_types`/`build_links`는 더미 반환으로 패치해 실행을 끝낸다.
  - 확인: `run_market.pinned_raw(base['raw_source'], 'explicit-run')`가 호출되고 `run_market.pinned_raw(base['raw_source'], 'config-run')`는 호출되지 않으며, `main()`이 최종적으로 `pinned_raw`에 넘긴 run_id가 `runs.get(base['candidate_id'])`였음을 확인한다.
- 근거: `file:src/market/run_market.py:439-445`, `file:tests/test_market.py:241-250` — 근거 확인됨

### `src/market/run_market.py` 446-448줄

- 바뀐 동작: `main()`이 작성지침 판단 결과(`build_guidelines`)에서 연속성 판정을 뽑아(`continuity_by_pair`) 이를 `build_stats(..., continuity)`로 넘기도록 바뀌었습니다. 즉, 연속성 판단이 연도별 통계 행과 기간 요약의 비교 가능성 계산에 반영되는 흐름을 추가했습니다.
- 실행 조건: `src/market/run_market.py`의 `main(as_of, runs)`를 실행할 때, 특히 `build_guidelines()`가 Q3 연속성 판정을 포함한 판단표를 반환하는 경우에 동작합니다.
- 제안 테스트: `tests/test_market.py` → `test_main_passes_guideline_continuity_into_build_stats`
  - 준비: `build_guidelines()`는 Q3 연속성 판정이 들어있는 더미 judgment DataFrame을 반환하고, `build_stats()`는 전달받은 `continuity` 인자를 캡처만 하도록 monkeypatch한 뒤 `main()`을 호출합니다. `pinned_raw()`, `parse_table()`, `build_types()`, `build_links()`도 더미로 바꿔 파일 I/O 없이 실행합니다.
  - 확인: `run_market.main('2026-01-01', runs={'M01': 'r1', 'M02': 'r2'})` 실행 후 `captured_continuity == {(2021, 2022): '연속성 확인 (J1)'}` 이고, `build_stats()`가 실제로 같은 dict를 네 번째 인자로 받았는지 확인합니다.
- 근거: `file:src/market/run_market.py:446-448`, `file:tests/test_market.py:60-72` — 근거 확인됨

### `src/market/run_market.py` 317-318줄

- 바뀐 동작: `guideline_section()`가 작성지침 확인 섹션의 표 머리글을 두 줄로 출력합니다. 첫 번째 표는 판단 항목(질문/적용 연도/상태/근거 등)을, 두 번째 표는 사실 항목(주제/근거 수준/문서/해석 등)을 구분해 보여 주도록 문서 구조를 고정합니다.
- 실행 조건: `report()`가 `guidelines`를 받아 작성지침 확인 섹션을 렌더링할 때 실행됩니다. 즉, 지침 사실/판정 데이터가 존재하여 `guideline_section()`이 호출되는 경우에 이 두 줄이 출력됩니다.
- 제안 테스트: `tests/test_market.py` → `test_guideline_section_renders_both_table_headers`
  - 준비: `guideline_tables(tmp_path)`로 만든 사실/판정 테이블을 `run_guidelines()`로 준비한 뒤, `run_market.report(...)`를 호출해 생성된 마크다운 문자열을 확인한다. `guidelines` 인자로 `(facts, judgments)`를 넘기고, 나머지 인자에는 기존 테스트에서 쓰는 `stats`, `summary`, `links`, `meta`, `table`, `types`, `type_summary`를 넣는다.
  - 확인: `report_text`에 `| ID | 질문 | 적용 연도 | 상태 | 확인한 것 | 남은 불확실성 | 결과 | 확인 근거 | 미해결 쟁점 근거 |`와 `| ID | 질문 | 주제 | 적용 연도 | 근거 수준 | 문서 (판·위치) | 해석 |`가 모두 포함되는지 `assert ... in report_text`로 확인한다.
- 근거: `file:tests/test_market.py:152-200`, `file:src/market/run_market.py:312-326` — 근거 확인됨

### `src/market/run_market.py` 368-369줄

- 바뀐 동작: 국내 화장품 생산금액 추세 표의 헤더에 새 열인 `정의 연속성 (Q3)`와 `비교`가 포함되고, 각 연도 행이 그에 맞는 값으로 렌더링되도록 바뀝니다. 기존의 `전년 대비/공식 증감률/대조`만 있는 표가 아니라, 정의 연속성 판정과 직접 비교 가능 여부를 함께 노출합니다.
- 실행 조건: `build_stats()`로 생성된 `stats`를 이용해 `src/market/run_market.py`의 보고서 본문을 출력할 때, 특히 `stats.columns`에 `context_` 열이 있거나 `continuity` 판정이 전달된 경우에 실행됩니다.
- 제안 테스트: `tests/test_market.py` → `test_market_report_includes_definition_continuity_and_comparability_columns`
  - 준비: `build_stats()`로 만든 `stats`와 `summary`를 바탕으로, `stats.columns`에 `context_업체수`가 있고 Q3 판정이 포함된 `cont`를 넣은 뒤 보고서 표 헤더 문자열을 직접 조립한다.
  - 확인: `header == '| 연도 | 생산금액 (백만원) | 전년 대비 | 공식 증감률 | 대조 | 보고 업체수 | 정의 연속성 (Q3) | 비교 |'`
- 근거: `file:src/market/run_market.py:367-369`, `file:src/market/run_market.py:372-373`, `file:tests/test_market.py:46-57` — 근거 확인됨

_실행 기록: gpt-5.4-mini, 공백 5개, LLM 15회, 도구 22회, 토큰 116,642 / 3,987, 51.0초_

## 변경 파일

| 파일 | 상태 | 분류 | +/- |
|---|---|---|---|
| `configs/market_v1.yaml` | 수정 | config | +2 / -0 |
| `data/manual/market_links.csv` | 수정 | data | +10 / -10 |
| `data/manual/stat_guideline_facts.csv` | 수정 | data | +28 / -27 |
| `data/manual/stat_guideline_judgments.csv` | 수정 | data | +7 / -6 |
| `docs/decisions.md` | 수정 | docs | +12 / -0 |
| `src/market/run_market.py` | 수정 | source | +120 / -35 |
| `src/metrics/engine.py` | 수정 | source | +9 / -0 |
| `src/report/evidence_report.py` | 수정 | source | +5 / -2 |
| `tests/test_market.py` | 수정 | test | +69 / -5 |
| `tests/test_metrics.py` | 수정 | test | +27 / -0 |
