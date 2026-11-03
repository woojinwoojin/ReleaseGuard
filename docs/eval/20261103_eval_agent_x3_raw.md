# ReleaseGuard Eval 결과

- 저장소: `C:\Project_Folder\predict-success` · 커밋 34개 · 분류 규칙 v1 · 에이전트 반복 3회
- 판정 분포 (첫 실행): REVIEW REQUIRED 19, SAFE 15
- 규칙 발동률 (첫 실행): R01 9%, R02 50%, R03 41%, R04 3%, R05 32%, R07 6%
- 관련 테스트 탐색 (규칙, 테스트가 함께 바뀐 커밋 19개): precision 0.705, recall 0.969
- 판정 (수기 정답 15개, 판정 45회): 정확도 0.867, 과잉 경고 6, 과소 경고 0
  - REVIEW REQUIRED → REVIEW REQUIRED: 24
  - SAFE → REVIEW REQUIRED: 6
  - SAFE → SAFE: 15
- 에이전트 (45회, 실패 0): 평균 LLM 3.5회, 도구 11.4회 (최대 20), 입력 토큰 45,126.0 (최대 170,534), 14.4초
  - 근거 확인 비율 0.951
  - 추천 기존 테스트: precision 0.815, recall 0.981
  - 후속 수정 커밋 6개의 verified HIGH: 실행 비율 0.333, 한 번이라도 3개, 매번 1개
  - SAFE 커밋 7개의 verified HIGH: 실행 비율 0.0, 한 번이라도 0개
  - 일관성 (커밋 15개): 판정 같음 15, HIGH 여부 같음 13, 추천 테스트 Jaccard 0.806

## 커밋별

| 커밋 | 제목 | 판정 | 기대 | 규칙 | 실제 테스트 | 예측 테스트 | 에이전트 |
|---|---|---|---|---|---|---|---|
| `0fc36c3` | Write README from the EvidenceFirst proposal | SAFE / SAFE / SAFE ✓ | SAFE | - | - | - | 도구 1, 토큰 9,396, HIGH 0/0<br>도구 1, 토큰 9,389, HIGH 0/0<br>도구 1, 토큰 9,386, HIGH 0/0 |
| `93fd788` | Add roadmap checklist for the 4-week MVP | SAFE | - | - | - | - | - |
| `f962d60` | Record OpenDART key setup and add env example | REVIEW REQUIRED / REVIEW REQUIRED / REVIEW REQUIRED ✗ | SAFE | R03 | - | - | 도구 7, 토큰 9,807, HIGH 0/0<br>도구 9, 토큰 9,949, HIGH 0/0<br>도구 5, 토큰 8,223, HIGH 0/0 |
| `c7878e3` | Define the five questions, trust checks, and why V1 is a score | SAFE | - | - | - | - | - |
| `60dbee2` | Fix the pilot companies and the data-handling rules they surfaced | SAFE | - | - | - | - | - |
| `fc58c0e` | Collect pilot filings and financial API responses as immutable raw data | REVIEW REQUIRED | - | R02, R03, R04 | tests/__init__.py<br>tests/test_dart_collector.py | tests/test_dart_collector.py | - |
| `32c4dc5` | Record the raw storage decision and first collection results | SAFE | - | - | - | - | - |
| `99309f2` | Flatten financial API responses into a per-source observation table | SAFE / SAFE / SAFE ✓ | SAFE | - | tests/test_dart_facts.py | tests/test_dart_facts.py | 도구 12, 토큰 36,153, HIGH 0/0<br>도구 13, 토큰 49,978, HIGH 0/0<br>도구 16, 토큰 53,964, HIGH 0/0 |
| `82e4305` | Map required accounts to internal accounts and build the checklist | REVIEW REQUIRED | - | R02, R03 | tests/test_account_map.py<br>tests/test_dart_facts.py | tests/test_account_map.py<br>tests/test_dart_facts.py | - |
| `568ea41` | Reconcile required-account mismatches and add manual note confirmations | REVIEW REQUIRED | - | R02, R03, R05 | tests/test_account_map.py<br>tests/test_dart_facts.py<br>tests/test_manual.py | tests/test_account_map.py<br>tests/test_dart_facts.py<br>tests/test_manual.py | - |
| `b67e806` | Confirm balance-sheet sections by arithmetic and adjust held-for-sale items | REVIEW REQUIRED / REVIEW REQUIRED / REVIEW REQUIRED ✓ | REVIEW REQUIRED | R02, R03, R05, R07 | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_manual.py | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_dart_facts.py<br>tests/test_manual.py | 도구 18, 토큰 43,472, HIGH 1/1<br>도구 20, 토큰 60,806, HIGH 0/0<br>도구 18, 토큰 51,331, HIGH 1/1 |
| `3db2f31` | Fix the reporting basis per company and compute the first 2025 metrics | REVIEW REQUIRED / REVIEW REQUIRED / REVIEW REQUIRED ✓ | REVIEW REQUIRED | R02, R03, R05, R07 | tests/test_bs_sections.py<br>tests/test_metrics.py | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_dart_facts.py<br>tests/test_metrics.py | 도구 20, 토큰 59,836, HIGH 1/1<br>도구 20, 토큰 86,128, HIGH 1/1<br>도구 16, 토큰 49,323, HIGH 1/1 |
| `9e9c12b` | Fill 2025 note gaps with separated amount, scope, and component checks | REVIEW REQUIRED / REVIEW REQUIRED / REVIEW REQUIRED ✓ | REVIEW REQUIRED | R01, R02, R05 | tests/test_manual.py | tests/test_manual.py<br>tests/test_metrics.py | 도구 17, 토큰 38,137, HIGH 0/0<br>도구 16, 토큰 38,745, HIGH 0/0<br>도구 15, 토큰 31,226, HIGH 0/0 |
| `c7733b3` | Close paths that promoted unconfirmed values, per code review | REVIEW REQUIRED / REVIEW REQUIRED / REVIEW REQUIRED ✗ | SAFE | R02, R03 | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_dart_facts.py<br>tests/test_manual.py<br>tests/test_metrics.py | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_dart_facts.py<br>tests/test_manual.py<br>tests/test_metrics.py | 도구 16, 토큰 46,050, HIGH 0/0<br>도구 19, 토큰 73,552, HIGH 0/0<br>도구 20, 토큰 57,264, HIGH 0/0 |
| `99c3179` | Add run manifests, proposed scoring rules, and coverage without redistribution | REVIEW REQUIRED | - | R02, R03 | tests/test_dart_facts.py<br>tests/test_scoring.py | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_dart_facts.py<br>tests/test_scoring.py | - |
| `b515f78` | Adopt scoring rules v2 as unvalidated project policy and keep v1 | REVIEW REQUIRED / REVIEW REQUIRED / REVIEW REQUIRED ✓ | REVIEW REQUIRED | R02, R03 | tests/test_scoring.py | tests/test_scoring.py | 도구 12, 토큰 38,420, HIGH 0/0<br>도구 10, 토큰 25,210, HIGH 0/0<br>도구 15, 토큰 44,497, HIGH 0/0 |
| `a75285f` | Mark where to resume next session | SAFE | - | - | - | - | - |
| `24faf5b` | Add 2022-2025 retrospective trend with comparability flags | REVIEW REQUIRED | - | R02, R03, R05 | tests/test_trend.py | tests/test_manual.py<br>tests/test_metrics.py<br>tests/test_trend.py | - |
| `da30a78` | Split working-capital checks, add comparison spans, and evidence report | REVIEW REQUIRED / REVIEW REQUIRED / REVIEW REQUIRED ✓ | REVIEW REQUIRED | R01, R02 | tests/test_trend.py | tests/test_metrics.py<br>tests/test_trend.py | 도구 15, 토큰 128,447, HIGH 0/0<br>도구 16, 토큰 72,967, HIGH 0/0<br>도구 16, 토큰 121,812, HIGH 0/0 |
| `075e30c` | Add Cosmecca Korea evidence report sample | SAFE / SAFE / SAFE ✓ | SAFE | - | - | - | 도구 1, 토큰 8,971, HIGH 0/0<br>도구 1, 토큰 8,971, HIGH 0/0<br>도구 3, 토큰 34,719, HIGH 0/0 |
| `c2fe0d1` | Check activity classification in cash-flow identity and narrow report claims | REVIEW REQUIRED | - | R01, R02, R05 | tests/test_trend.py | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_metrics.py<br>tests/test_trend.py | - |
| `b326bd1` | Update Cosmecca Korea evidence report sample | SAFE | - | - | - | - | - |
| `fa03441` | Match same-period rows across renamed accounts and split unverified reasons | REVIEW REQUIRED | - | R02 | tests/test_trend.py | tests/test_trend.py | - |
| `59e0fb4` | Update Cosmecca Korea evidence report sample | SAFE | - | - | - | - | - |
| `f2d690e` | Link domestic cosmetics production statistics to pilot companies | REVIEW REQUIRED / REVIEW REQUIRED / REVIEW REQUIRED ✓ | REVIEW REQUIRED | R02, R03, R05 | tests/test_market.py | tests/test_market.py | 도구 12, 토큰 42,703, HIGH 0/0<br>도구 16, 토큰 51,253, HIGH 0/0<br>도구 18, 토큰 59,205, HIGH 0/0 |
| `694de2e` | Add market statistics sample and refresh evidence report sample | SAFE | - | - | - | - | - |
| `f57b432` | Link cosmetics production by product type to pilot companies | REVIEW REQUIRED | - | R02, R03, R05 | tests/test_market.py | tests/test_market.py | - |
| `0b57374` | Refresh market statistics and evidence report samples | SAFE | - | - | - | - | - |
| `adb2f5b` | Check M01/M02 guidelines: price basis, reporting scope, continuity (D20) | REVIEW REQUIRED / REVIEW REQUIRED / REVIEW REQUIRED ✓ | REVIEW REQUIRED | R02, R03, R05 | tests/test_market.py | tests/test_market.py | 도구 10, 토큰 36,243, HIGH 0/0<br>도구 19, 토큰 170,534, HIGH 0/0<br>도구 17, 토큰 76,989, HIGH 1/1 |
| `c9824b0` | Sync weekly checklist with actual progress; reorder next steps after check-in | SAFE / SAFE / SAFE ✓ | SAFE | - | - | - | 도구 2, 토큰 13,250, HIGH 0/0<br>도구 2, 토큰 13,237, HIGH 0/0<br>도구 2, 토큰 13,202, HIGH 0/0 |
| `142912b` | Close verification gaps from external review (D21) | REVIEW REQUIRED / REVIEW REQUIRED / REVIEW REQUIRED ✓ | REVIEW REQUIRED | R02, R03, R05 | tests/test_market.py<br>tests/test_metrics.py | tests/test_market.py<br>tests/test_metrics.py<br>tests/test_trend.py | 도구 10, 토큰 34,948, HIGH 0/0<br>도구 14, 토큰 62,699, HIGH 0/0<br>도구 16, 토큰 85,535, HIGH 0/0 |
| `388da2a` | Compare 2020-2025 reporting guidelines and close market research (D22) | REVIEW REQUIRED | - | R05 | tests/test_market.py | tests/test_market.py | - |
| `a5465f0` | Update README status, pilot industry and samples to current implementation | SAFE / SAFE / SAFE ✓ | SAFE | - | - | - | 도구 1, 토큰 9,566, HIGH 0/0<br>도구 1, 토큰 9,563, HIGH 0/0<br>도구 5, 토큰 35,616, HIGH 0/0 |
| `895dbe4` | Set next session start: minimal lookup screen | SAFE | - | - | - | - | - |

## 에이전트 위험 (HIGH·MEDIUM)

### `f962d60` Record OpenDART key setup and add env example (기대 SAFE)

- 실행 3 · MEDIUM: 환경변수명 불일치 여부 확인 필요

### `99309f2` Flatten financial API responses into a per-source observation table (기대 SAFE)

- 실행 1 · MEDIUM: 기간 추출 실패 시 행이 review_needed로 남음
- 실행 1 · MEDIUM: 동일 기간 비교에서 오탐/누락 가능성
- 실행 1 · MEDIUM: 최신 유효 정정본 선택 기준의 데이터 의존성
- 실행 2 · MEDIUM: 정규화된 중간 산출물의 기간/값 분류가 실제 데이터에 맞는지 검증 필요
- 실행 2 · MEDIUM: 최신 유효 정정본 선택 규칙이 분석용 표(B)의 결과를 바꿀 수 있음
- 실행 3 · MEDIUM: 관측값 생성 로직이 다운스트림 분석 입력을 바꿀 수 있음
- 실행 3 · MEDIUM: 기간 추출 실패 시 값이 보류 처리됨

### `b67e806` Confirm balance-sheet sections by arithmetic and adjust held-for-sale items (기대 REVIEW REQUIRED · 후속 수정 c7733b3)

- 실행 1 · HIGH: 점검표 생성 로직은 변경됐지만 전용 테스트가 없음
- 실행 1 · MEDIUM: 구간 미확인 행이 비교/집계에서 제외됨
- 실행 1 · MEDIUM: 수기 확인표 CSV 스키마가 확장됨
- 실행 2 · MEDIUM: build_account_check 출력 형식/집계 기준 변경
- 실행 2 · MEDIUM: 구간 미확인 행이 비교에서 제외되어 불일치 탐지가 달라질 수 있음
- 실행 2 · MEDIUM (근거 미확인): 수기 확인값이 mapped가 아니라 candidate로 남을 수 있음
- 실행 3 · HIGH: 비교 키에서 구간 미확인 행이 제외되어 기존 불일치/집계 결과가 바뀔 수 있음
- 실행 3 · MEDIUM: 매각예정항목 포함/미포함 판정이 보고서별 행 순서와 소계 일치에 의존함
- 실행 3 · MEDIUM: 수기 확인표 스키마 확장으로 기존 파일/생성 파이프라인 호환성 점검 필요
- 실행 3 · MEDIUM: `build_account_check`는 관련 테스트가 명시적으로 없다고 판정됨

### `3db2f31` Fix the reporting basis per company and compute the first 2025 metrics (기대 REVIEW REQUIRED · 후속 수정 c7733b3, 142912b)

- 실행 1 · HIGH: 점검표 상태 변경이 지표 계산 결과를 바꿀 수 있음
- 실행 1 · MEDIUM: 계정 매핑 규칙 재배치로 사채·차입금 매핑 결과가 달라질 수 있음
- 실행 1 · MEDIUM: 신규 지표 엔진은 테스트는 있으나 실행 결과 검증이 필요함
- 실행 2 · HIGH: `build_account_check`의 상태 변경이 후속 지표 입력을 바꿀 수 있음
- 실행 2 · MEDIUM: 구간 판정 플래그 교체로 매핑 결과가 달라질 수 있음
- 실행 2 · MEDIUM: 지표 엔진은 새 코드 경로라 회귀 확인 필요
- 실행 3 · HIGH: 단기 부채 계정의 점검 상태가 바뀌어 downstream 계산 결과가 달라질 수 있음
- 실행 3 · MEDIUM: 새로 추가된 지표 엔진은 테스트가 있으나 실행 경로 전체 검증은 필요
- 실행 3 · MEDIUM: 비교군 기준이 파일럿 3개사에 의존

### `9e9c12b` Fill 2025 note gaps with separated amount, scope, and component checks (기대 REVIEW REQUIRED · 후속 수정 c7733b3)

- 실행 1 · MEDIUM: 단기 이자부채가 후보값으로 남는 케이스 검증 필요
- 실행 1 · MEDIUM: API 값과 다른 수기 값의 대체 조건이 좁지만 새로 생김
- 실행 2 · MEDIUM: 수기 확인표 로딩 실패 가능성
- 실행 3 · MEDIUM: 수기 확인표 스키마 변경으로 인한 적재 실패 가능성
- 실행 3 · MEDIUM: 단기 이자부채의 수기 대체 조건이 강화됨

### `c7733b3` Close paths that promoted unconfirmed values, per code review (기대 SAFE)

- 실행 1 · MEDIUM: 점검표/지표 출력이 보류로 늘어날 수 있음
- 실행 1 · MEDIUM: 중복 입력이 있으면 실행 중 예외 발생
- 실행 2 · MEDIUM: 분석 입력 선택 실패 시 전체 점검표가 보류될 수 있음
- 실행 2 · MEDIUM: 구성 항목 계정이 candidate로 내려가면서 점수 반영 범위가 줄 수 있음
- 실행 2 · MEDIUM: 기간 불일치가 있으면 계산 입력이 not_computed로 바뀜
- 실행 3 · MEDIUM: 선택된 보고서가 원문 미저장인 경우 전체 입력이 보류될 수 있음
- 실행 3 · MEDIUM: 기간 정보가 비어 있거나 규칙과 다르면 계산 결과가 not_computed로 바뀜
- 실행 3 · MEDIUM: 합계 계정이 candidate로 내려가면서 downstream 점수 반영이 달라질 수 있음

### `b515f78` Adopt scoring rules v2 as unvalidated project policy and keep v1 (기대 REVIEW REQUIRED)

- 실행 1 · MEDIUM: 변동성 점수 산정 기준이 바뀜
- 실행 1 · MEDIUM: 파이프라인 결과 열 이름 변경으로 후속 소비 코드 영향 가능
- 실행 2 · MEDIUM: 새 규칙 파일은 채택됐지만 아직 검증되지 않음
- 실행 2 · MEDIUM: 파일럿 실행 경로는 기존 테스트 커버리지 밖일 수 있음
- 실행 3 · MEDIUM: CAGR 상한 적용 조건이 새로 추가되어 일부 점수 결과가 달라질 수 있음
- 실행 3 · MEDIUM: 파이프라인이 v2 설정 파일에 직접 의존함
- 실행 3 · MEDIUM: 출력 스키마 변경으로 후속 소비 코드 점검 필요

### `da30a78` Split working-capital checks, add comparison spans, and evidence report (기대 REVIEW REQUIRED · 후속 수정 c2fe0d1)

- 실행 1 · MEDIUM: 추세 산출물 형식 변경에 따른 하위 소비자 영향
- 실행 1 · MEDIUM: 운전자본 경고 의미 변경
- 실행 1 · MEDIUM: 증거 보고서용 파일 의존성 추가
- 실행 2 · MEDIUM: 새 증거 보고서에 대한 자동 테스트 부재
- 실행 2 · MEDIUM: 추세 비교 표의 새 분기 로직 검증 필요
- 실행 3 · MEDIUM: 새 증거 보고서 모듈은 테스트가 없습니다
- 실행 3 · MEDIUM: 추세 출력 스키마 변화로 하위 소비자 영향 가능

### `075e30c` Add Cosmecca Korea evidence report sample (기대 SAFE)


### `f2d690e` Link domestic cosmetics production statistics to pilot companies (기대 REVIEW REQUIRED · 후속 수정 142912b)

- 실행 1 · MEDIUM: 시장 통계 단계가 파이프라인 실패 지점이 될 수 있음
- 실행 1 · MEDIUM: 증거 리포트가 시장 결과 파일의 컬럼 구조에 의존
- 실행 2 · MEDIUM: 시장 통계 단계는 파이프라인에 연결되었지만 파이프라인 자체 테스트는 없음
- 실행 2 · MEDIUM: 새 리포트 경로가 결과 파일 존재를 전제로 동작
- 실행 3 · MEDIUM: 새 시장 통계 실행 단계는 외부 원본 수집본에 의존
- 실행 3 · MEDIUM: 증거 보고서의 시장 답변은 생성 산출물 유무에 따라 보류될 수 있음

### `adb2f5b` Check M01/M02 guidelines: price basis, reporting scope, continuity (D20) (기대 REVIEW REQUIRED · 후속 수정 142912b)

- 실행 1 · MEDIUM: 작성지침 검증 실패 시 시장 보고서 생성 중단 가능
- 실행 1 · MEDIUM: 설정 해석 변경으로 보고서 문구/검증 기준이 바뀜
- 실행 2 · MEDIUM: 작성지침 원본/해시 불일치 시 시장 실행 중단 가능
- 실행 2 · MEDIUM: 새 작성지침 파일 누락 시 파이프라인 입력 집합 불완전
- 실행 3 · HIGH: 작성지침 검증 실패 시 시장 리포트 전체가 중단될 수 있음
- 실행 3 · MEDIUM: 새 설정 키 누락 시 리포트 문구가 달라질 수 있음
- 실행 3 · MEDIUM: 수집기 CLI 추가로 외부 의존성 실패 경로가 생김

### `c9824b0` Sync weekly checklist with actual progress; reorder next steps after check-in (기대 SAFE)


### `142912b` Close verification gaps from external review (D21) (기대 REVIEW REQUIRED)

- 실행 1 · MEDIUM: 고정된 raw_run 미존재 또는 해시 불일치로 실행 중단 가능
- 실행 1 · MEDIUM: 정의 연속성 기준 변경으로 비교 가능 판정이 달라짐
- 실행 1 · MEDIUM (근거 미확인): 음수 입력의 계산 보류 범위 확대
- 실행 2 · MEDIUM: 보고서 문구 변경이 최종 산출물에 직접 반영됨
- 실행 2 · MEDIUM: raw_run 미지정 또는 수집본 변경 시 실행 중단 가능
- 실행 3 · MEDIUM: 고정된 수집본/해시 검증으로 파이프라인 중단 가능
- 실행 3 · MEDIUM: 음수 입력 처리 강화로 기존에 계산되던 지표가 보류될 수 있음

### `a5465f0` Update README status, pilot industry and samples to current implementation (기대 SAFE)


