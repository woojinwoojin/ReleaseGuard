# Agent Eval 응답

- 모델 `gpt-5.4-mini-2026-03-17` (응답 모델 ['gpt-5.4-mini-2026-03-17']) · 실행 16/16
- 구조화 출력 성공 16/16 · 근거 참조 오류 0/38 (참조 유효는 인용한 줄이 존재한다는 뜻이지 설명이 맞다는 뜻이 아님)
- 테스트 파일 경로 오류 0 · 새 테스트 파일 제안 0 · 도구 59회 (오류 0) · 가린 비밀값 0
- 요청 47회 (실패 0, 사용량 미확인 0) · 토큰 252,733 / 10,857 · 추정 $0.2384 (캐시 할인 미반영) · 143.8초

## F3 `tools.py:213-213` (`5b31f70`, followup_fix)

규칙 기준선: 함수 `compare_periods`, 조건·반환 줄 1개, 같은 파일의 다른 변경을 실행한 테스트 10개

### 실행 1

- 바뀐 동작: `compare_periods`에서 `category` 인자가 들어왔을 때, 데이터에 존재하지 않는 카테고리면 이후 기간 비교를 하지 않고 즉시 오류 dict를 반환합니다. 즉, 잘못된 카테고리 입력을 초기에 걸러내는 동작이 추가됐습니다.
- 실행 조건: `category`가 `None`이 아니고, `df['category']`의 유효값 목록에 그 값이 없을 때 실행됩니다.
- 제안: `tests/test_tools.py` → `test_compare_periods_unknown_category_returns_error`
  - 준비: 카테고리 컬럼이 있는 DataFrame(예: category가 'A', 'B'만 있는 데이터)에 대해 `compare_periods(df, '2024-01', '2024-01', '2024-02', '2024-02', category='C')`를 호출한다.
  - 확인: 반환값이 `{'error': '없는 카테고리: C', 'available': ['A', 'B']}` 형태인지 확인한다.
- 근거: `file:tools.py:211-214`
- 도구 0회, 요청 1회, 토큰 3,043 / 474, 6.9초

### 실행 2

- 바뀐 동작: `compare_periods(..., category=...)`에서 전달한 카테고리가 데이터에 없으면, 이후 기간 비교 로직을 타지 않고 `check_category`의 오류 dict를 그대로 반환하도록 바뀌었습니다. 즉, 잘못된 카테고리 입력을 조용히 처리하지 않고 가능한 카테고리 목록이 포함된 에러를 돌려줍니다.
- 실행 조건: `category` 인자가 주어졌고, 그 값이 `df['category']`의 기존 값들에 없을 때 실행됩니다.
- 제안: `tests/test_tools.py` → `test_compare_periods_unknown_category`
  - 준비: `df`에서 존재하지 않는 카테고리 `Z`를 넣어 `compare_periods(df, '2024-01', '2024-01', '2024-02', '2024-02', category='Z')`를 호출한다.
  - 확인: `result['available'] == ['A', 'B']` 이고 `result['error'] == '없는 카테고리: Z'` 인지 확인한다.
- 근거: `file:tools.py:211-215`, `file:tests/test_tools.py:96-121`
- 도구 3회, 요청 3회, 토큰 15,900 / 553, 7.8초

## N1 `tools.py:299-301` (`ef7ed86`, need_no)

규칙 기준선: 함수 `dimension_breakdown`, 조건·반환 줄 2개, 같은 파일의 다른 변경을 실행한 테스트 10개

### 실행 1

- 바뀐 동작: `dimension_breakdown()`에서 `category`가 주어졌을 때, 그 카테고리가 실제 데이터에 존재하는지 먼저 검증하고 없으면 차원 집계를 하지 않고 `check_category()`의 에러를 그대로 반환합니다. 즉, 잘못된 카테고리 입력에 대해 `dimension`별 결과 대신 친절한 오류/대안 목록을 돌려주는 동작이 추가되었습니다.
- 실행 조건: `dimension_breakdown(df, dimension, category=...)` 호출 시 `category` 인자가 `None`이 아니고, `df['category']`에 그 값이 없을 때 실행됩니다.
- 제안: `tests/test_tools.py` → `test_dimension_breakdown_unknown_category`
  - 준비: 기본 df에서 존재하지 않는 카테고리 `Z`로 `dimension_breakdown(df, 'region', category='Z')`를 호출한다.
  - 확인: `result['error'] == '없는 카테고리: Z'` 이고 `result['available'] == ['A', 'B']` 이며, `result`에 `rows`가 없다.
- 근거: `file:tools.py:299-301`, `file:tools.py:52-62`, `file:tests/test_tools.py:189-199`
- 도구 4회, 요청 3회, 토큰 17,686 / 591, 11.1초

### 실행 2

- 바뀐 동작: `dimension_breakdown()`에서 `category`가 주어지면, 먼저 그 카테고리가 실제 데이터에 존재하는지 검사하고, 존재할 때만 해당 카테고리로 데이터를 제한합니다. 즉, 잘못된 카테고리 입력은 차원 집계로 들어가기 전에 에러 응답으로 반환됩니다.
- 실행 조건: `dimension_breakdown(df, dimension, category=...)` 호출 시 `category` 인자가 전달되었고, 그 값이 `df['category']`에 없는 경우에 이 분기가 실행됩니다.
- 제안: `tests/test_tools.py` → `test_dimension_breakdown_invalid_category`
  - 준비: `df`에 존재하지 않는 `category='Z'`와 `dimension='region'`으로 `dimension_breakdown(df, "region", category="Z")`를 호출한다.
  - 확인: `result['error'] == '없는 카테고리: Z'` 이고 `result['available'] == ['A', 'B']` 이다.
- 근거: `file:tools.py:288-301`, `file:tools.py:52-62`, `file:tests/test_tools.py:189-199`
- 도구 5회, 요청 4회, 토큰 26,124 / 647, 9.6초

## F1 `src/market/run_market.py:27-30` (`f2d690e`, followup_fix)

규칙 기준선: 함수 `latest_raw`, 조건·반환 줄 3개, 같은 파일의 다른 변경을 실행한 테스트 4개

### 실행 1

- 바뀐 동작: `latest_raw(source)`는 `ROOT/source` 아래에서 `metadata.json`이 있는 실행 디렉터리만 골라 정렬한 뒤, 가장 마지막(가장 최신으로 간주되는) 디렉터리를 반환합니다. 해당 조건을 만족하는 실행본이 하나도 없으면 `FileNotFoundError`를 발생시킵니다.
- 실행 조건: `ROOT/<source>` 아래에 `metadata.json`이 있는 하위 디렉터리가 존재할 때는 그중 마지막 경로를 반환하고, 하나도 없을 때는 예외를 던집니다.
- 제안: `tests/test_market.py` → `test_latest_raw_returns_latest_run_or_raises_when_missing`
  - 준비: 임시 `ROOT/<source>` 디렉터리에 `run_a/metadata.json`, `run_b/metadata.json`를 만들고(정렬상 `run_b`가 마지막), 같은 경로에서 `metadata.json`이 없는 디렉터리는 제외되도록 한 뒤 `latest_raw(source)`를 호출한다. 별도 케이스로 빈 `ROOT/<source>` 디렉터리도 준비해 호출한다.
  - 확인: `latest_raw(source)`가 `Path(ROOT / source / 'run_b')`를 반환하고, 실행본이 없을 때는 `with pytest.raises(FileNotFoundError): latest_raw(source)`가 성립한다.
- 근거: `file:src/market/run_market.py:26-30`
- 도구 0회, 요청 1회, 토큰 3,112 / 414, 4.4초

### 실행 2

- 바뀐 동작: `latest_raw()`는 지정한 수집 원본 디렉터리에서 `metadata.json`이 있는 하위 실행 폴더만 골라 정렬한 뒤, 가장 최근 실행본을 반환합니다. 실행본이 하나도 없으면 `FileNotFoundError`를 발생시켜 이후 처리로 진행하지 않습니다.
- 실행 조건: `main()`이 `config["base_statistic"]["raw_source"]`에 해당하는 원본 디렉터리를 읽을 때, 그 아래에 `metadata.json`이 있는 실행 폴더가 0개이거나 여러 개일 때 실행됩니다. 특히 최근 실행본이 아닌 오래된 실행본이 더 많아도 정렬 후 마지막 항목을 선택하는지 확인이 필요합니다.
- 제안: `tests/test_market.py` → `test_latest_raw_returns_most_recent_run_and_errors_when_missing`
  - 준비: 임시 `ROOT/<source>` 아래에 `old/metadata.json`, `new/metadata.json` 두 실행 폴더를 만들고, 둘의 이름 순서를 바꿔도 마지막으로 정렬되는 폴더가 선택되도록 한다. 이어서 빈 `<source>` 디렉터리도 만들어 실행본이 없을 때의 동작을 확인한다.
  - 확인: `run_market.latest_raw(source)`가 `Path(...)/'new'`를 반환하고, 실행본이 없는 경우 `FileNotFoundError`를 발생시킨다.
- 근거: `file:src/market/run_market.py:26-30`, `file:src/market/run_market.py:189`
- 도구 5회, 요청 4회, 토큰 23,047 / 680, 9.9초

## F2 `src/market/run_market.py:238-254` (`adb2f5b`, followup_fix)

규칙 기준선: 함수 `guideline_section`, 조건·반환 줄 2개, 같은 파일의 다른 변경을 실행한 테스트 3개

### 실행 1

- 바뀐 동작: `guidelines`가 전달된 경우 보고서 본문에 작성지침 확인 섹션을 추가하고, 그 안에 질문별 판정 표와 사실 표, 그리고 근거 수준/공지 현재본 사용 금지에 대한 주석을 출력합니다. 이 변경은 점수 계산 로직이 아니라 문서화 출력만 바꿉니다.
- 실행 조건: `report(..., guidelines=...)`로 호출되어 작성지침 데이터가 함께 들어올 때 실행됩니다. 특히 `build_guidelines()`를 통과한 사실·판정 데이터가 있을 때 238~254줄의 문구와 표가 렌더링됩니다.
- 제안: `tests/test_market.py` → `test_report_includes_guideline_section_and_does_not_change_score_output`
  - 준비: 최소한의 stats/summary/links/meta/table 더미와, `guideline_tables(tmp_path)`로 만든 facts/judgments를 `run_market.report(..., guidelines=(facts, judgments))`에 넣어 보고서를 생성한다.
  - 확인: `report(...)` 결과 문자열에 `"## 1-1. 작성지침 확인 — 가격·보고 범위·연속성 (D20)"`, `"| ID | 질문 | 적용 연도 | 상태 | 확인한 것 | 남은 불확실성 | 결과 | 근거 |"`, `"- 근거 수준: 명시적 확인(해당 연도 문서에 적혀 있음) / 간접 근거(다른 연도 문서·게시판 현재본·구조에서 추론) / 미확인(문서 미확보 또는 찾지 못함)."`이 포함되고, `guidelines=None`일 때는 이 섹션이 포함되지 않는다.
- 근거: `file:src/market/run_market.py:238-254`, `tool:#6`
- 도구 6회, 요청 4회, 토큰 31,327 / 884, 16.2초

### 실행 2

- 바뀐 동작: `guideline_section`이 작성지침(D20) 섹션을 보고서에 추가합니다. 제목, 설명 문구, 판정 표, 사실 표, 그리고 근거 수준/게시판 공지 해석 안내 문장을 순서대로 출력합니다.
- 실행 조건: `report(..., guidelines=(facts, judgments))`가 호출되어 작성지침 데이터가 함께 전달될 때 실행됩니다. 이때 D20 섹션이 보고서 본문에 삽입됩니다.
- 제안: `tests/test_market.py` → `test_report_includes_guideline_section_with_facts_and_judgments`
  - 준비: `guideline_tables(tmp_path)`로 만든 사실·판정 데이터를 `run_guidelines`로 준비한 뒤, `run_market.report(as_of='2026-10-20', config=CONFIG, stats=빈 DataFrame, summary=빈 DataFrame, links=빈 DataFrame, meta={}, table={}, guidelines=(facts, judgments))`를 호출해 문자열 보고서를 생성한다.
  - 확인: 생성된 report 문자열에 `"## 1-1. 작성지침 확인 — 가격·보고 범위·연속성 (D20)"`, `"| J1 | Q1 가격 기준 |"`, `"| S1 |"`, 그리고 `"- 게시판 공지는 같은 주소에서 본문이 갱신된다"`가 모두 포함되어야 한다.
- 근거: `file:src/market/run_market.py:237-254`, `tool:#2`, `tool:#3`
- 도구 5회, 요청 3회, 토큰 21,838 / 661, 8.7초

## N2 `src/normalization/selection.py:16-24` (`c7733b3`, need_no)

규칙 기준선: 함수 `load_published_filings`, 조건·반환 줄 4개, 같은 파일의 다른 변경을 실행한 테스트 4개

### 실행 1

- 바뀐 동작: `raw_root` 아래의 공시검색 응답 파일들을 훑어, `list` 안의 항목 중 사업보고서로 파싱되는 것만 모아 `rcept_no` 키로 저장하는 동작을 추가합니다. 이때 각 항목의 원본 필드와 `parse_annual_report_name()`에서 뽑은 사업연도/정정정보를 합쳐 보관합니다.
- 실행 조건: `raw_root`에 `*/api/list/A001/*/*/*/response.json` 경로의 JSON이 있고, 그 안의 `list` 항목 중 `report_nm`이 사업보고서 형식으로 파싱되는 공시가 있을 때 실행됩니다.
- 제안: `tests/test_dart_collector.py` → `test_load_published_filings_collects_only_annual_reports_from_response_json`
  - 준비: 임시 디렉터리에 `01009789/api/list/A001/x/y/z/response.json`를 만들고, `list`에 `사업보고서 (2025.12)` 1건과 `반기보고서 (2025.06)` 1건을 함께 넣는다.
  - 확인: `load_published_filings(tmp_path)` 결과에 대해서 `set(published) == {"20260318000694"}` 이고, `published["20260318000694"]["bsns_year"] == 2025` 및 `published["20260318000694"]["correction"] is None` 이다.
- 근거: `file:src/normalization/selection.py:16-24`, `file:src/normalization/selection.py:17-23`, `file:tests/test_dart_collector.py:76-89`
- 도구 6회, 요청 4회, 토큰 23,614 / 1,151, 11.5초

### 실행 2

- 바뀐 동작: `load_published_filings`는 저장된 공시검색 응답들에서 사업보고서만 골라 `rcept_no` 기준으로 모으고, `parse_annual_report_name`이 해석한 사업연도·정정정보까지 합쳐서 반환합니다. 즉, 공시 원문 저장 여부와 무관하게 공개된 사업보고서 목록을 재구성하는 동작입니다.
- 실행 조건: `raw_root` 아래에 `*/api/list/A001/*/*/*/response.json` 형태의 응답 파일이 있고, 각 파일의 `list` 항목에 `report_nm`이 사업보고서 형식으로 들어 있을 때 실행됩니다. 비사업보고서 항목은 무시되고, 같은 `rcept_no`는 나중에 읽힌 값으로 덮어써집니다.
- 제안: `tests/test_dart_facts.py` → `test_load_published_filings_collects_only_annual_reports_from_response_json`
  - 준비: `tmp_path` 아래에 `01009789/api/list/A001/x/y/z/response.json` 파일을 만들고, `list`에 `사업보고서 (2025.12)`와 `반기보고서 (2025.06)`를 함께 넣는다. 추가로 다른 경로의 `response.json` 하나에 같은 `rcept_no`의 `사업보고서`를 넣어 덮어쓰기 동작도 만든다.
  - 확인: `load_published_filings(tmp_path)`가 사업보고서 항목만 `rcept_no` 키로 포함하고, 각 값에 `rcept_no`, `corp_code`, `rcept_dt`, `report_nm`, `bsns_year`, `correction`가 들어 있으며, 비사업보고서 항목은 결과에 없고 중복 `rcept_no`는 마지막 파일의 값으로 남는다.
- 근거: `file:src/normalization/selection.py:14-24`, `file:tests/test_dart_facts.py:8-12`, `file:tests/test_dart_facts.py:160-171`
- 도구 5회, 요청 4회, 토큰 25,957 / 813, 10.9초

## N3 `app.py:171-177` (`2e652ab`, need_no)

규칙 기준선: 함수 `show_answer`, 조건·반환 줄 2개, 같은 파일의 다른 변경을 실행한 테스트 0개

### 실행 1

- 바뀐 동작: `show_answer()`가 답변의 근거 목록을 그릴 때, `unverified_evidence`에 포함된 항목만 ⚠️로 표시하고, 검증되지 않은 근거가 있으면 경고 문구를 `notes`에 추가해 함께 보여줍니다. 또한 `notes`는 일반 참고는 ℹ️로, 경고성 문구는 그대로 표시하도록 바뀝니다.
- 실행 조건: 답변 객체에 `findings[*].evidence`가 있고, 그중 일부 문자열이 `answer['unverified_evidence']`에 포함되어 있거나 `unverified_evidence`가 비어 있지 않을 때 실행됩니다. 이때 `answer['notes']`가 비어 있지 않으면 기존 참고와 추가 경고가 함께 렌더링됩니다.
- 제안: `tests/test_app.py` → `test_unverified_evidence_adds_warning_note`
  - 준비: `FINAL`을 기반으로 `findings[0].evidence`에 검증되지 않은 문자열 하나를 넣고, `notes`는 기존 참고 1개를 유지한 뒤 채팅을 전송한다.
  - 확인: `at.caption`에서 `"⚠️ 총매출 99,999,999달러"`가 보이고, `"⚠️ 표시한 근거의 숫자는 분석 도구 결과에서 찾지 못했습니다."`가 추가되며, 기존 note는 `"ℹ️"` 접두사로 렌더링된다.
- 근거: `file:app.py:167-177`, `file:tests/test_app.py:132-142`
- 도구 4회, 요청 3회, 토큰 8,967 / 869, 10.0초

### 실행 2

- 바뀐 동작: `show_answer()`가 `unverified_evidence`에 포함된 근거는 ⚠️로 표시하고, 그런 근거가 하나라도 있으면 하단 참고(notes) 영역에 추가 경고 문구를 덧붙입니다. 또한 notes 전체를 한 번에 렌더링하면서 일반 메모는 ℹ️, 경고 메모는 ⚠️ 형식으로 구분해 보여줍니다.
- 실행 조건: 답변 객체에 `unverified_evidence`가 비어 있지 않고, 각 finding의 `evidence` 또는 `notes`가 존재해 `show_answer()`가 캡션을 그릴 때 실행됩니다.
- 제안: `tests/test_app.py` → `test_unverified_evidence_adds_warning_note`
  - 준비: `FINAL`을 기반으로 `unverified_evidence`를 `['총매출 99,999,999달러']`로 넣고, `notes`는 `['기간은 전체로 해석']`만 둔 답변을 FakeClient가 반환하게 한 뒤 대화 질문을 보낸다.
  - 확인: `at.caption`에 `⚠️ 표시한 근거의 숫자는 분석 도구 결과에서 찾지 못했습니다. LLM이 직접 계산했거나 잘못 옮겼을 수 있습니다.`가 포함되고, 기존 note는 `ℹ️ 기간은 전체로 해석` 형태로 함께 렌더링된다.
- 근거: `file:app.py:171-177`, `file:tests/test_app.py:132-142`
- 도구 4회, 요청 3회, 토큰 7,654 / 740, 8.9초

## B1 `app.py:181-206` (`12b9eb3`, boundary_skip)

규칙 기준선: 함수 `pick_conversation`, 조건·반환 줄 5개, 같은 파일의 다른 변경을 실행한 테스트 0개

### 실행 1

- 바뀐 동작: 사이드바의 대화 선택 UI가 버튼에서 선택 상자로 바뀌어, 이전 대화를 고르면 해당 대화의 turn 목록을 다시 불러오고, ‘새 대화’를 고르면 현재 conversation_id와 turn 목록을 초기화합니다. 또한 기존 대화 목록 라벨에 updated_at을 로컬 시간 문자열로 표시합니다.
- 실행 조건: show_chat()가 렌더링될 때마다 pick_conversation(dataset)이 실행되고, 사용자가 사이드바 selectbox에서 현재 선택값과 다른 항목(특히 기존 대화 또는 새 대화)을 선택할 때 동작합니다.
- 제안: `tests/test_app.py` → `test_selecting_new_conversation_clears_current_turns`
  - 준비: 먼저 질문을 한 번 보내 conversation_id와 turns가 채워진 상태를 만든 뒤, 사이드바의 ‘대화’ selectbox에서 value가 'new'인 항목을 선택한다.
  - 확인: assert at.session_state.conversation_id is None and at.session_state.turns == []
- 근거: `file:app.py:181-206`, `file:tests/test_app.py:62-81`
- 도구 5회, 요청 3회, 토큰 9,941 / 781, 8.5초

### 실행 2

- 바뀐 동작: 사이드바의 대화 선택 상자가 이전 대화 목록을 보여주고, 선택한 대화에 따라 `st.session_state.conversation_id`와 `st.session_state.turns`를 갱신합니다. 또한 ‘＋ 새 대화’를 고르면 현재 대화를 해제하고 대화 기록을 비우도록 바뀌었습니다.
- 실행 조건: `show_chat()`가 실행될 때 항상 `pick_conversation(dataset)`가 호출되며, `api().list_conversations(dataset_id)`로 가져온 대화 목록이 있을 때 사용자가 사이드바 selectbox에서 기존 대화 또는 `NEW_CONVERSATION`을 선택하면 실행됩니다.
- 제안: `tests/test_app.py` → `test_pick_conversation_loads_selected_history_and_resets_on_new_conversation`
  - 준비: `api().list_conversations()`가 두 개의 대화를 반환하고, `st.sidebar.selectbox`가 첫 번째 호출에서는 기존 conversation_id를, 두 번째 호출에서는 `NEW_CONVERSATION`을 선택하도록 모의합니다. 초기 `st.session_state.conversation_id`와 `turns`를 비워 둡니다.
  - 확인: `pick_conversation(dataset)` 호출 후 기존 대화 선택 시 `st.session_state.conversation_id == <선택한 conversation_id>`이고 `st.session_state.turns == api().conversation(<선택한 conversation_id>)["turns"]`이며, `NEW_CONVERSATION` 선택 시 `st.session_state.conversation_id is None`이고 `st.session_state.turns == []`이어야 합니다.
- 근거: `file:app.py:181-206`, `file:app.py:209-212`, `file:app.py:186-206`, `file:app.py:33-34`
- 도구 0회, 요청 1회, 토큰 2,199 / 467, 3.9초

## B2 `api.py:349-351` (`8c05dc5`, boundary_call)

규칙 기준선: 함수 `chat_stream.work`, 조건·반환 줄 1개, 같은 파일의 다른 변경을 실행한 테스트 7개

### 실행 1

- 바뀐 동작: `/chat/stream`의 워커 스레드에서 OpenAI/RuntimeError가 아닌 예상 밖 예외가 나면, 내부 에러를 로그로 남기고 클라이언트에는 일반적인 서버 오류 SSE(`error`)를 보내도록 처리합니다. 이 경로는 LLM 실패와 별개로, 스트리밍 중 비정상 예외가 났을 때도 응답을 종료하는 안전장치입니다.
- 실행 조건: `prepare_chat()`는 통과했지만, 백그라운드 스레드의 `work()` 안에서 `run_chat_agent()` 또는 그 이후 저장/후처리 단계가 `Exception` 계열로 실패할 때 실행됩니다.
- 제안: `tests/test_api.py` → `test_chat_stream_unexpected_exception_is_generic_error_event`
  - 준비: `api.run_chat_agent`를 `ValueError('boom')`를 던지도록 monkeypatch 한 뒤, 정상 dataset에 대해 `POST /chat/stream`을 호출한다.
  - 확인: `read_sse(http, {...})`의 이벤트 이름이 `['error']`이고, 마지막 이벤트의 `detail`이 `'서버 오류로 답변을 만들지 못했습니다.'`이며, `db.connect(tmp_path / 'app.db').execute('SELECT COUNT(*) FROM conversations').fetchone()[0] == 0`
- 근거: `file:api.py:349-351`, `file:api.py:355-363`, `file:tests/test_api.py:249-257`
- 도구 3회, 요청 3회, 토큰 16,009 / 604, 8.0초

### 실행 2

- 바뀐 동작: `/chat/stream` 처리 중 `openai.OpenAIError`/`RuntimeError`가 아닌 예외가 나도 스트리밍을 끊지 않고 `error` SSE 이벤트로 마무리합니다. 이때 사용자에게는 내부 예외 메시지 대신 고정된 일반 오류 문구를 내려보냅니다.
- 실행 조건: 스트리밍 워커 스레드에서 `run_chat_agent()` 또는 그 이후 저장 단계가 예상하지 못한 예외를 던질 때 실행됩니다. 즉, LLM 실패가 아니라 코드/런타임의 비정상 예외가 발생한 경우입니다.
- 제안: `tests/test_api.py` → `test_chat_stream_unexpected_exception_is_generic_error_event`
  - 준비: `api.run_chat_agent`를 `ValueError('boom')`를 던지도록 monkeypatch한 뒤, `/chat/stream`에 유효한 `dataset_id`와 `question`으로 요청한다.
  - 확인: `read_sse(...)`의 이벤트 순서가 `['error']`이고, 마지막 이벤트의 `detail`이 `'서버 오류로 답변을 만들지 못했습니다.'`와 같아야 한다.
- 근거: `file:api.py:349-351`, `file:tests/test_api.py:249-257`
- 도구 4회, 요청 3회, 토큰 16,315 / 528, 7.5초
