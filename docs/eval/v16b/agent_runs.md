# Agent Eval 응답

- 모델 `gpt-5.4-mini-2026-03-17` (응답 모델 ['gpt-5.4-mini-2026-03-17']) · 실행 16/16
- 구조화 출력 성공 16/16 · 근거 참조 오류 2/41 (참조 유효는 인용한 줄이 존재한다는 뜻이지 설명이 맞다는 뜻이 아님)
- 테스트 파일 경로 오류 0 · 새 테스트 파일 제안 0 · 도구 41회 (오류 0) · 가린 비밀값 0
- skip이 있는 파일에 제안 6 · 응답에 skip 언급 0
- 요청 38회 (실패 0, 사용량 미확인 0) · 토큰 188,940 / 10,405 · 추정 $0.1885 (캐시 할인 미반영) · 128.2초

## F3 `tools.py:213-213` (`5b31f70`, followup_fix)

규칙 기준선: 함수 `compare_periods`, 조건·반환 줄 1개, 같은 파일의 다른 변경을 실행한 테스트 10개

### 실행 1

- 바뀐 동작: `compare_periods(..., category=...)`에 존재하지 않는 카테고리를 넣으면, 이후 기간 비교를 진행하지 않고 즉시 검증용 error dict를 반환합니다. 즉, 잘못된 카테고리 입력을 아래 로직까지 흘려보내지 않게 바뀝니다.
- 실행 조건: `category` 인자가 `None`이 아니고, `df['category']`의 값들 중에 그 카테고리가 없을 때 실행됩니다.
- 제안: `tests/test_tools.py` → `test_compare_periods_unknown_category`
  - 준비: `compare_periods(df, "2024-01", "2024-01", "2024-02", "2024-02", category="Z")`처럼 존재하지 않는 카테고리를 넣는다.
  - 확인: `result["error"] == "없는 카테고리: Z"` 이고 `result["available"] == ["A", "B"]` 이어야 한다.
- 근거: `file:tools.py:213`, `file:tests/test_tools.py:96-105`, `file:tests/test_tools.py:139-143`, `tool:#1`, `tool:#2`, `tool:#3`
- 도구 3회, 요청 4회, 토큰 15,911 / 630, 15.0초

### 실행 2

- 바뀐 동작: `compare_periods()`에 `category`가 들어왔을 때, 그 값이 실제 카테고리 목록에 없으면 이후 기간 비교를 하지 않고 `check_category()`가 만든 오류 dict를 그대로 반환합니다. 즉, 잘못된 카테고리 입력에 대해 하위 카테고리 탐색이나 기간 집계를 시도하지 않도록 바뀝니다.
- 실행 조건: `compare_periods(df, ..., category=...)` 호출 시, 전달된 `category`가 `df['category']`의 유효한 값이 아닐 때 실행됩니다.
- 제안: `tests/test_tools.py` → `test_compare_periods_unknown_category_returns_error`
  - 준비: 기본 fixture 데이터프레임에서 존재하지 않는 category='Z'를 넣어 `compare_periods(df, "2024-01", "2024-01", "2024-02", "2024-02", category="Z")`를 호출한다.
  - 확인: `compare_periods(...)["available"] == ["A", "B"]` 이고 `compare_periods(...)["error"] == "없는 카테고리: Z"` 여야 한다.
- 근거: `file:tools.py:211-213`, `file:tests/test_tools.py:96-121`
- 도구 2회, 요청 2회, 토큰 9,398 / 481, 6.6초

## N1 `tools.py:299-301` (`ef7ed86`, need_no)

규칙 기준선: 함수 `dimension_breakdown`, 조건·반환 줄 2개, 같은 파일의 다른 변경을 실행한 테스트 10개

### 실행 1

- 바뀐 동작: `dimension_breakdown()`에 `category`가 들어오면, 먼저 `check_category()`로 유효성을 검증한 뒤 그 카테고리 데이터만 남겨 차원별 집계를 다시 계산합니다. 즉, 전체 데이터가 아니라 선택한 카테고리 범위의 `total`과 `rows`가 반환되도록 바뀝니다.
- 실행 조건: `dimension_breakdown(df, dimension, category=...)`처럼 `category` 인자가 `None`이 아니고, 동시에 `dimension`이 데이터에 존재할 때 실행됩니다.
- 제안: `tests/test_tools.py` → `test_dimension_breakdown_filters_category`
  - 준비: `df`에서 `dimension_breakdown(df, "region", category="A")`를 호출한다.
  - 확인: `result["category"] == "A"`이고 `result["total"]["sales"] == 400`, `[(r["name"], r["sales"]) for r in result["rows"]] == [("East", 200), ("West", 200)]` 이어야 한다.
- 근거: `file:tools.py:295-301`, `file:tests/test_tools.py:189-199`
- 도구 3회, 요청 3회, 토큰 16,332 / 703, 10.1초

### 실행 2

- 바뀐 동작: `dimension_breakdown()`에서 `category`가 주어졌을 때, 먼저 그 카테고리가 실제 데이터에 존재하는지 검증하고, 유효하면 그 카테고리 데이터만 남겨 차원별 집계를 수행합니다. 유효하지 않은 카테고리라면 이후 집계로 진행하지 않고 `check_category()`가 반환한 오류/힌트 정보를 그대로 돌려줍니다.
- 실행 조건: `dimension_breakdown(df, dimension, category=...)`처럼 카테고리 필터가 들어온 경우에 실행됩니다. 특히 요청한 `category`가 데이터의 `category` 컬럼 값 목록에 없을 때 이 분기에서 즉시 종료됩니다.
- 제안: `tests/test_tools.py` → `test_dimension_breakdown_unknown_category`
  - 준비: 카테고리 A/B만 있는 df에 대해 `dimension_breakdown(df, "region", category="Z")`를 호출한다.
  - 확인: `result["error"] == "없는 카테고리: Z"` 이고 `result["available"] == ["A", "B"]` 이다.
- 근거: `file:tools.py:299-301`, `file:tools.py:52-62`, `file:tests/test_tools.py:189-199`
- 도구 4회, 요청 4회, 토큰 22,955 / 564, 9.3초

## F1 `src/market/run_market.py:27-30` (`f2d690e`, followup_fix)

규칙 기준선: 함수 `latest_raw`, 조건·반환 줄 3개, 같은 파일의 다른 변경을 실행한 테스트 4개

### 실행 1

- 바뀐 동작: `latest_raw(source)`는 `ROOT/source` 아래에서 `metadata.json`이 있는 수집본 디렉터리만 모아 정렬한 뒤 가장 վերջին 디렉터리를 반환합니다. 해당 조건을 만족하는 수집본이 하나도 없으면 `FileNotFoundError`를 발생시켜, 원본 수집 데이터가 없다는 실패를 명확히 드러냅니다.
- 실행 조건: `ROOT/<source>` 경로에 디렉터리는 있지만 그중 `metadata.json`이 있는 수집본이 없을 때 실행됩니다. 또는 여러 수집본이 있을 때 최신 디렉터리를 고르는 경로를 탈 때 실행됩니다.
- 제안: `tests/test_market.py` → `test_latest_raw_returns_latest_run_with_metadata_and_errors_when_missing`
  - 준비: 임시 `ROOT/source` 디렉터리에 `run1`, `run2` 두 하위 디렉터리를 만들고 둘 다 `metadata.json`을 두되, `run1`과 `run2`의 수정순서가 아니라 이름 정렬 기준으로 `run2`가 최신이 되도록 구성한 뒤, 별도 케이스로 `metadata.json`이 없는 빈 source 디렉터리도 준비한다.
  - 확인: `run_market.latest_raw(source)`가 `metadata.json`이 있는 디렉터리 중 마지막 경로(`.../run2`)를 반환하고, 빈 source에 대해서는 `FileNotFoundError`를 발생시킨다.
- 근거: `file:src/market/run_market.py:27-30`, `file:tests/test_market.py:1-86`
- 도구 3회, 요청 2회, 토큰 8,586 / 576, 6.6초

### 실행 2

- 바뀐 동작: `latest_raw(source)`는 `ROOT/source` 아래에서 `metadata.json`이 있는 수집본 디렉터리만 골라 정렬한 뒤 가장 최신 폴더를 반환합니다. 만약 그런 수집본이 하나도 없으면, 수집 데이터를 먼저 만들어야 한다는 안내와 함께 `FileNotFoundError`를 발생시킵니다.
- 실행 조건: `src/market/run_market.py`에서 특정 원천 데이터 소스의 최신 수집본 경로가 필요할 때 실행됩니다. 해당 소스 디렉터리에 `metadata.json`이 있는 하위 폴더가 전혀 없거나, 존재하더라도 찾을 수 없는 경우에 예외 경로가 발동됩니다.
- 제안: `tests/test_market.py` → `test_latest_raw_raises_when_no_collected_runs_exist`
  - 준비: 임시 테스트 환경에서 `ROOT / source` 아래에 하위 수집본 디렉터리를 만들지 않고 `latest_raw('stats')`를 호출한다.
  - 확인: `latest_raw('stats')`가 `FileNotFoundError`를 발생시키고, 예외 메시지에 `stats에 수집본 없음`이 포함된다.
- 근거: `file:src/market/run_market.py:26-30`
- 도구 0회, 요청 1회, 토큰 3,144 / 395, 3.5초

## F2 `src/market/run_market.py:238-254` (`adb2f5b`, followup_fix)

규칙 기준선: 함수 `guideline_section`, 조건·반환 줄 2개, 같은 파일의 다른 변경을 실행한 테스트 3개

### 실행 1

- 바뀐 동작: `guideline_section()`가 작성지침(D20) 섹션을 마크다운으로 출력합니다. 질문/상태/근거를 표로 나열하고, 마지막에 근거 수준과 게시판 공지 해석에 대한 안내 문구를 덧붙입니다.
- 실행 조건: `report()`가 작성지침 데이터를 함께 받아 이 섹션을 생성할 때, 즉 `guideline_section(w, facts, judgments)`가 호출될 때 실행됩니다. `facts`와 `judgments`에 적어둔 행이 있을 때 각각의 표 행과 하단 주석이 출력됩니다.
- 제안: `tests/test_market.py` → `test_guideline_section_formats_tables_and_notes`
  - 준비: `guideline_section`에 `judgments` 1행(예: judgment_id='J1', question='Q3 연속성 확인', applies_years='2021~2025', status='연속성 확인', confirmed='...', remaining_uncertainty='...', consequence='...', evidence='F1;F2')`와 `facts` 1행(예: fact_id='F1', question='Q1 가격 확인', topic='가격', applies_years='2021~2025', evidence_level='명시적 확인', doc_id='D1', doc_version='1판', location='p.1', interpretation='...')`를 넣고, 출력 문자열을 수집한다.
  - 확인: `guideline_section`의 출력에 `| J1 | Q3 연속성 확인 | 2021~2025 | **연속성 확인** |`와 `| F1 | Q1 가격 확인 | 가격 | 2021~2025 | 명시적 확인 | D1 (1판; p.1) |`가 포함되고, `evidence='F1;F2'`가 `F1, F2`로 치환되어 나타나며, 하단에 `근거 수준:` 및 `게시판 공지는 같은 주소에서 본문이 갱신된다` 문구가 포함되는지 확인한다.
- 근거: `file:src/market/run_market.py:237-254`, `file:src/market/run_market.py:238-253`, `file:src/market/run_market.py:244-250`
- 도구 0회, 요청 1회, 토큰 4,038 / 697, 4.8초

### 실행 2

- 바뀐 동작: `guideline_section()`가 작성지침 D20을 마크다운 섹션으로 출력합니다. 판단 표와 사실 표를 나란히 보여 주고, 근거 수준/공지 해석에 대한 주석까지 붙여서 보고서 본문에 포함시키는 동작입니다.
- 실행 조건: `report(..., guidelines=...)`를 호출하고 `guidelines`가 `None`이 아닐 때 실행됩니다. 즉, `build_guidelines()`로 읽은 사실·판정 데이터가 전달된 경우에만 이 섹션이 출력됩니다.
- 제안: `tests/test_market.py` → `test_report_includes_guideline_section_when_guidelines_are_present`
  - 준비: `guideline_tables(tmp_path)`로 만든 사실·판정 테이블을 `run_guidelines()`로 읽은 뒤, `run_market.report()`에 `guidelines=(facts, judgments)`를 전달하고 결과 문자열을 만든다.
  - 확인: `report(..., guidelines=(facts, judgments))`의 반환값에 `"## 1-1. 작성지침 확인 — 가격·보고 범위·연속성 (D20)"`, `"| J1 | Q1 가격 기준 |"`, `"| S1 |"`, `"- 근거 수준: 명시적 확인(해당 연도 문서에 적혀 있음) / 간접 근거(다른 연도 문서·게시판 현재본·구조에서 추론) / 미확인(문서 미확보 또는 찾지 못함)."`가 모두 포함된다.
- 근거: `file:src/market/run_market.py:237-254`, `file:src/market/run_market.py:287-288`, `file:tests/test_market.py:161-180`
- 도구 6회, 요청 3회, 토큰 24,809 / 914, 12.4초

## N2 `src/normalization/selection.py:16-24` (`c7733b3`, need_no)

규칙 기준선: 함수 `load_published_filings`, 조건·반환 줄 4개, 같은 파일의 다른 변경을 실행한 테스트 4개

### 실행 1

- 바뀐 동작: 저장된 공시검색 응답(response.json)들에서 사업보고서로 파싱 가능한 항목만 모아 접수번호(rcept_no)를 키로 한 dict로 반환합니다. 각 항목에는 원본 필드(rcept_no, corp_code, rcept_dt, report_nm)와 연간보고서 파싱 결과가 함께 들어갑니다.
- 실행 조건: raw_root 아래의 `*/api/list/A001/*/*/*/response.json` 파일들을 읽을 때, 각 파일의 `list` 안에 있는 항목 중 `report_nm`이 `parse_annual_report_name()`으로 해석되는 사업보고서만 처리됩니다. 같은 `rcept_no`가 여러 번 나오면 나중 항목이 덮어씁니다.
- 제안: `tests/test_dart_facts.py` → `test_load_published_filings_collects_only_parseable_annual_reports`
  - 준비: tmp_path 아래에 `x/api/list/A001/2024/11011/CFS/response.json` 파일을 만들고, `list`에 `report_nm`이 사업보고서로 파싱되는 항목 1개와 파싱되지 않는 항목 1개를 함께 넣는다. 두 번째 `response.json`에는 같은 `rcept_no`의 다른 항목을 넣어 덮어쓰기 동작도 확인한다.
  - 확인: `load_published_filings(tmp_path)`가 파싱 가능한 `rcept_no`만 포함한 `dict`를 반환하고, 결과에서 해당 접수번호의 `corp_code`, `rcept_dt`, `report_nm`과 파싱된 `bsns_year`/`correction` 값이 기대값과 같으며, 파싱 불가 항목은 포함되지 않는다.
- 근거: `file:src/normalization/selection.py:16-24`, `file:src/normalization/build_facts.py:37-43`
- 도구 6회, 요청 4회, 토큰 29,749 / 917, 10.8초

### 실행 2

- 바뀐 동작: `response.json`들에서 공개된 사업보고서 목록을 읽어, `report_nm`을 사업보고서명으로 파싱한 항목만 `rcept_no` 기준으로 모아 `published` 사전으로 만든다. 즉, 공개 공시 응답이 여러 개여도 유효한 사업보고서만 누적하고, 각 항목의 `corp_code`, `rcept_dt`, `report_nm`, 파싱 결과가 보존되는 동작을 추가한다.
- 실행 조건: `raw_root` 아래에 `*/api/list/A001/*/*/*/response.json` 경로의 파일이 존재하고, 그 안의 `list` 배열에 `report_nm`이 사업보고서로 파싱되는 항목이 있을 때 실행된다.
- 제안: `tests/test_dart_facts.py` → `test_load_published_filings_collects_only_parsable_annual_reports`
  - 준비: 임시 디렉터리 아래에 `.../api/list/A001/.../response.json` 파일을 만들고, `list`에 파싱 가능한 사업보고서 1건과 파싱 불가 항목 1건을 함께 넣은 뒤 `load_published_filings(tmp_path)`를 호출한다.
  - 확인: `load_published_filings(tmp_path)`가 `rcept_no`가 사업보고서인 항목만 포함한 dict를 반환하고, 예를 들어 `result['20260318000694']['corp_code'] == '01009789'` 및 `result`에 파싱 불가 항목의 `rcept_no`는 없다.
- 근거: `file:src/normalization/selection.py:16-24`, `file:tests/test_dart_facts.py:160-171`
- 도구 5회, 요청 4회, 토큰 20,407 / 721, 11.1초

## N3 `app.py:171-177` (`2e652ab`, need_no)

규칙 기준선: 함수 `show_answer`, 조건·반환 줄 2개, 같은 파일의 다른 변경을 실행한 테스트 0개

### 실행 1

- 바뀐 동작: `show_answer()`가 `unverified_evidence`에 포함된 근거를 ⚠️ 표시해 출력하고, 그런 미검증 근거가 하나라도 있으면 경고 안내 문구를 notes에 추가해 함께 렌더링합니다. 기존에는 `notes`만 그대로 표시했지만, 이제 미검증 근거 여부에 따라 보조 경고가 더 붙습니다.
- 실행 조건: `answer`에 `unverified_evidence`가 비어 있지 않거나, 각 finding의 `evidence` 항목 중 일부가 `unverified_evidence`에 포함될 때 실행됩니다. 또한 `answer['notes']`가 비어 있지 않거나, 미검증 근거로 인해 경고 문구가 추가될 때 캡션 출력이 발생합니다.
- 제안: `tests/test_app.py` → `test_unverified_evidence_is_marked`
  - 준비: `show_answer()`에 `summary`, `findings=[{"title":"매출 증가","detail":"...","evidence":["2024년 1월 매출 100"]}]`, `notes=["주의할 점"]`, `suggested_actions=[]`, `unverified_evidence=["2024년 1월 매출 100"]`를 가진 답변 dict를 넣고, `st.markdown`/`st.caption`을 목(mock)으로 대체해 렌더링한다.
  - 확인: `st.caption` 호출 인자에 `⚠️ 2024년 1월 매출 100`이 포함되고, 추가 경고 문구 `⚠️ 표시한 근거의 숫자는 분석 도구 결과에서 찾지 못했습니다. LLM이 직접 계산했거나 잘못 옮겼을 수 있습니다.`가 함께 전달되는지 확인한다.
- 근거: `file:app.py:167-177`, `file:app.py:163-184`, `file:tests/test_app.py:1-200` — 참조 오류 ['file:tests/test_app.py:1-200']
- 도구 0회, 요청 1회, 토큰 1,750 / 499, 4.6초

### 실행 2

- 바뀐 동작: `show_answer()`가 답변의 `unverified_evidence` 목록을 따로 읽어, 해당 근거 항목만 ⚠️ 표시로 강조하고, 검증되지 않은 근거가 하나라도 있으면 안내 문구를 `notes`에 추가해 함께 출력합니다. 기존에는 `findings`의 근거와 `notes`를 그대로 표시했지만, 이제는 근거별 검증 상태에 따라 표시 방식이 달라집니다.
- 실행 조건: `answer`에 `unverified_evidence`가 포함되어 있고, 그 값이 `findings[*].evidence` 중 일부와 일치할 때 실행됩니다. 또한 `notes`가 비어 있어도 `unverified_evidence`가 있으면 경고 안내 문구가 추가됩니다.
- 제안: `tests/test_app.py` → `test_unverified_evidence_is_marked`
  - 준비: `show_answer()`에 `summary`, `findings`(evidence에 `['A', 'B']` 포함), `notes`는 비어 있고 `unverified_evidence`는 `['B']`인 더미 답변을 넣고, `st.markdown`/`st.caption` 호출을 모킹해 렌더링 결과를 수집한다.
  - 확인: `st.caption`에 `A · ⚠️ B`가 출력되고, `st.caption`에 `⚠️ 표시한 근거의 숫자는 분석 도구 결과에서 찾지 못했습니다. LLM이 직접 계산했거나 잘못 옮겼을 수 있습니다.`가 포함되며, `B`만 경고 처리되고 `A`는 경고 없이 표시되는 것을 확인한다.
- 근거: `file:app.py:167-177`, `file:app.py:171-175`, `tool:#1` — 참조 오류 ['tool:#1']
- 도구 0회, 요청 1회, 토큰 1,750 / 459, 4.3초

## B1 `app.py:181-206` (`12b9eb3`, boundary_skip)

규칙 기준선: 함수 `pick_conversation`, 조건·반환 줄 5개, 같은 파일의 다른 변경을 실행한 테스트 0개

### 실행 1

- 바뀐 동작: 사이드바의 대화 선택 상자에서 이전 대화를 고르면 해당 대화의 턴을 다시 불러오고, '＋ 새 대화'를 고르면 현재 대화 상태를 초기화합니다. 또한 목록 라벨은 마지막 수정 시각과 제목, 턴 수를 합쳐 보여주도록 바뀝니다.
- 실행 조건: 사용자가 `st.sidebar.selectbox`에서 현재 선택값과 다른 항목을 고를 때 실행됩니다. 특히 `NEW_CONVERSATION` 값(`new`)을 선택하면 `st.session_state.conversation_id`와 `st.session_state.turns`를 비우는 분기가 타깃입니다.
- 제안: `tests/test_app.py` → `test_selecting_new_conversation_clears_loaded_turns`
  - 준비: 기존 대화를 한 번 생성한 뒤 새 세션에서 그 대화를 selectbox로 다시 불러오고, 이어서 대화 선택 상자 값을 `new`로 바꾼다.
  - 확인: `st.session_state.conversation_id is None` 이고 `st.session_state.turns == []` 이어야 하며, `conversation_box(at).value == "new"`로 돌아와야 한다.
- 근거: `file:app.py:181-206`, `file:tests/test_app.py:62-80`
- 도구 3회, 요청 2회, 토큰 6,752 / 930, 8.4초

### 실행 2

- 바뀐 동작: 사이드바의 대화 선택 UI가 버튼에서 선택박스로 바뀌고, 기존 대화 목록을 시간·제목·턴 수 형태로 표시한 뒤 선택된 대화를 즉시 불러오거나 ‘새 대화’로 초기화합니다. 이 과정에서 UTC로 저장된 `updated_at`을 화면 표시용 로컬 시간 문자열로 변환하는 동작도 추가됩니다.
- 실행 조건: 채팅 화면을 그릴 때 `list_conversations(dataset_id)`로 이전 대화가 하나 이상 조회되는 경우 실행됩니다. 사용자가 선택박스에서 기존 대화 ID를 고르거나 `new`를 고르면 각각 해당 대화 로드/새 대화 초기화가 일어납니다.
- 제안: `tests/test_app.py` → `test_conversation_selectbox_uses_local_time_label`
  - 준비: `list_conversations`가 `updated_at='2024-01-01T00:00:00+00:00'`, `title='Furniture 이익률이 왜 낮아?'`, `turn_count=1`인 대화를 반환하도록 설정한 뒤 앱을 실행하고, 사이드바의 ‘대화’ selectbox 옵션을 확인한다.
  - 확인: `conversation_box(at).options[1]`가 현재 실행 환경의 로컬 시간 기준 `local_time('2024-01-01T00:00:00+00:00')`로 시작하고, `'· Furniture 이익률이 왜 낮아? (1)'`를 포함한다.
- 근거: `file:app.py:181-206`, `file:tests/test_app.py:62-81`
- 도구 6회, 요청 4회, 토큰 17,113 / 1,094, 12.9초

## B2 `api.py:349-351` (`8c05dc5`, boundary_call)

규칙 기준선: 함수 `chat_stream.work`, 조건·반환 줄 1개, 같은 파일의 다른 변경을 실행한 테스트 7개

### 실행 1

- 바뀐 동작: `/chat/stream` 처리 중 OpenAI 오류나 RuntimeError가 아닌 예외가 나면, 서버는 내부 로그를 남기고 클라이언트에는 일반적인 SSE `error` 이벤트로 "서버 오류로 답변을 만들지 못했습니다."를 보냅니다. 즉, 예기치 않은 실패가 스트림을 끊기지 않게 표준화된 오류 응답으로 마무리하는 동작입니다.
- 실행 조건: `work()` 스레드 안에서 `run_chat_agent()` 또는 이후 저장/후처리 과정이 `Exception` 계열로 실패할 때 실행됩니다. 즉, `openai.OpenAIError`/`RuntimeError`가 아닌 예외가 발생하는 비정상 상황에서만 이 분기가 타야 합니다.
- 제안: `tests/test_api.py` → `test_chat_stream_unexpected_error_becomes_generic_error_event`
  - 준비: `run_chat_agent` 또는 `finish_chat`를 `Exception`을 던지도록 monkeypatch하고, `/chat/stream`에 유효한 `ChatRequest`를 보낸다.
  - 확인: 응답 스트림에 `event: error`가 포함되고, `detail` 값이 `"서버 오류로 답변을 만들지 못했습니다."`이며, 대화 저장 함수(`db.save_turn`)는 호출되지 않는다.
- 근거: `file:api.py:349-351`, `file:api.py:355-360`, `file:api.py:379-380`
- 도구 0회, 요청 1회, 토큰 3,123 / 422, 4.0초

### 실행 2

- 바뀐 동작: `/chat/stream` 처리 중 `openai.OpenAIError`/`RuntimeError`가 아닌 예외가 나면, 서버는 내부 로그를 남기고 스트림으로는 일반화된 `error` SSE 이벤트(`서버 오류로 답변을 만들지 못했습니다.`)를 보냅니다. 즉, LLM 실패와는 별개로 예기치 못한 서버 오류를 클라이언트가 스트리밍 응답으로 받게 됩니다.
- 실행 조건: `work()` 스레드 안에서 `run_chat_agent(...)`, `db.connect(...)`, `finish_chat(...)` 중 하나가 `Exception` 계열의 예외를 던질 때 실행됩니다. 이때는 `openai.OpenAIError`나 `RuntimeError`로 잡히지 않는 모든 예외가 대상입니다.
- 제안: `tests/test_api.py` → `test_chat_stream_unexpected_exception_becomes_generic_error_event`
  - 준비: `run_chat_agent`(또는 `finish_chat`)를 monkeypatch해서 `ValueError("boom")`를 던지게 만든 뒤, `/chat/stream` 엔드포인트로 정상적인 ChatRequest를 보낸다.
  - 확인: 응답 스트림에 `event: error`가 포함되고, `data`는 `{"detail": "서버 오류로 답변을 만들지 못했습니다."}`이며, 이후 `event: done`은 오지 않는다.
- 근거: `file:api.py:349-351`, `file:api.py:353-363`
- 도구 0회, 요청 1회, 토큰 3,123 / 403, 3.8초
