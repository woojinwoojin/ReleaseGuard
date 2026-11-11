# Stage 1.7 Reliability Gate — 설계안

- 작성: 2026-11-11 · **Claude 초안, 사용자 확인 전** · 근거: [보고서 #11](eval/20261111_eval_report_11.md) 3~5장
- 대상 규칙 버전: v3.1 → **v3.2** (T03 추가). 나머지 규칙은 그대로다.

## 1. 목적과 범위

**목적**: 판정이 SAFE인데 실제로는 바뀐 테스트가 실행되지 않은 경우를 드러내고, 실행 근거(coverage 버전, node id)를 재현할 수 있게 남긴다.

| 포함 | 제외 |
|---|---|
| T03 (원인 코드 3개) | G01 완화, 판정 구분력 개선 (Decision Utility로 따로 추적) |
| 소스 삭제 N06 반례 (판정은 그대로) | 삭제 영향 분석 |
| coverage·pytest-cov 실제 버전 확인 | 실행 격리 (2.0 이후) |
| parametrize를 포함한 원본 node id 보존 | scope 의미 재설계 |
| 회귀: 58커밋 + 심은 사례 + 새 반례 | base에서 skip 상태를 알기 위한 추가 실행 |

## 2. T03 — 바뀐 테스트가 실행되지 않음 (REVIEW)

### 2.1 공통 정의

**수집 대상 테스트 파일**: 바뀐 파일 중 분류가 `test`이고, 파일 이름이 pytest 기본 수집 패턴(`test_*.py`, `*_test.py`)에 맞는 파일이다.
- `conftest.py`와 `tests/fakes.py` 같은 헬퍼는 수집 대상이 아니므로 T03의 근거가 되지 않는다.
- 대상 저장소가 pytest 설정의 `python_files`를 바꿨다면 이 정의가 틀릴 수 있다 (6장 Q3).

**평가 조건**: 테스트 실행 상태가 `passed`·`failed`·`no_tests`일 때만 T03을 본다.
- `error`·`timeout`·`not_run`이면 이미 B04·E01이 실행 근거가 없다고 말하므로 T03을 내지 않는다 (중복 방지).

### 2.2 원인 코드

| 코드 | 조건 (모두 만족) | 근거 (`evidence`) |
|---|---|---|
| `COLLECTION_EMPTY` | ① 수집 대상 테스트 파일이 추가(A)·수정(M)됐거나, 내용이 바뀐 채 이름이 바뀜(R) ② head 실행에서 그 파일의 결과가 0개 (`tests_by_file`) | 파일 경로, 변경 상태, 수집 수 0 |
| `CHANGED_TESTS_ALL_SKIPPED` | ① 수집 대상 테스트 파일에서 **추가·수정된 테스트 함수**가 1개 이상 있음 (6장 Q1) ② 그 함수들의 결과가 **전부** skip | 파일 경로, 바뀐 테스트 n개 중 skip n개, skip 사유 |
| `TEST_SUITE_REMOVED` | ① 실행 상태가 `no_tests` ② 수집 대상 테스트 파일이 1개 이상 삭제(D)됨 | 삭제된 테스트 파일 목록 |

- 원인 코드는 커밋당 여러 개가 나올 수 있다. T03 finding은 하나만 만들고 원인 코드마다 근거 줄을 붙인다.
- `COLLECTION_EMPTY`와 `CHANGED_TESTS_ALL_SKIPPED`는 같은 파일에 함께 나오지 않는다. 수집이 0개면 skip도 없기 때문이다.
- 메시지는 "실행되지 않았다"는 사실만 말한다. 테스트가 틀렸다고 단정하지 않는다.
  - 예: "바뀐 테스트 파일 `tests/test_new.py`에서 수집된 테스트가 0개입니다. 테스트 이름이 pytest 수집 규칙에 맞는지 확인하세요."

### 2.3 바뀐 테스트 함수 찾기 (`CHANGED_TESTS_ALL_SKIPPED`)

1. head의 테스트 파일을 AST로 읽고, 모듈 수준 `test*` 함수와 `Test*` 클래스 안의 `test*` 메서드를 찾는다. 범위에는 데코레이터 줄을 포함한다.
2. diff에서 추가·수정된 줄이 그 범위에 걸치는 함수를 "바뀐 테스트 함수"로 본다.
3. 함수와 실행 결과를 node id로 맞춘다. 함수 `파일::[클래스::]이름`에 `[...]` 파라미터가 붙은 결과도 모두 같은 함수로 본다.
4. 모듈 수준 skip(`pytest.skip(..., allow_module_level=True)`, `pytestmark`)이 JUnit에 어떤 node id로 기록되는지는 구현할 때 심은 사례로 확인한다. 함수별 결과 없이 파일 단위 skip만 있으면 그 파일의 바뀐 함수는 모두 skip으로 본다.

`gap_groups.py`와 `suggestion_checks.py`의 AST 처리를 재사용한다.

### 2.4 판정·scope와의 관계

- **판정**: T03은 REVIEW다. BLOCK이 있으면 그대로 BLOCK이다.
- **scope**: 바꾸지 않는다. `scope`는 "검증할 수 있는 종류의 파일인가"이고, T03은 "바뀐 테스트가 실제로 실행됐는가"다. 그래서 **`scope=COMPLETE`와 T03 REVIEW가 함께 나올 수 있다.** 보고서에 이 차이를 한 줄로 적는다.
- **G01과의 관계**: 소스만 추가했고 `no_tests`이면 지금처럼 G01만 낸다. 삭제된 테스트 파일이 없으므로 T03 조건에 걸리지 않는다.
- NOT_VERIFIED_RULES(보고서에서 "검증이 성립하지 않은 것" 묶음)에 T03을 넣는다.

## 3. 반례 — T03이 나오면 안 되는 경우와 경계

| # | 사례 | 기대 | 이유 |
|---|---|---|---|
| X1 | 테스트 파일의 헬퍼 함수만 바뀌고, 그 파일의 테스트는 실행됨 | T03 없음 | 수집 > 0, 바뀐 테스트 함수 없음 |
| X2 | `tests/fakes.py`(수집 대상 아님)만 바뀜 | T03 없음 | 수집 패턴 밖 |
| X3 | `conftest.py`의 fixture만 바뀜 | T03 없음 | 수집 패턴 밖. 영향은 기존 실행 결과로 드러남 |
| X4 | 새 테스트 2개 중 1개만 skip | T03 없음 | "전부"가 아님. skip 표에는 나옴 |
| X5 | 문서만 바뀜 | T03 없음, SAFE | 테스트를 실행하지 않음 (`skipped` 상태) |
| X6 | 소스 추가 + 저장소에 테스트 0개 (`no_tests`) | G01만 | 삭제된 테스트 파일 없음 |
| X7 | 테스트 파일 이름만 바뀜 (내용 같음, R100) | T03 없음 | 내용 변경 없음. 수집되면 문제없음 |
| X8 | 테스트 파일 하나를 지웠지만 다른 테스트는 실행됨 | T03 없음 | `no_tests`가 아님. 소스를 같이 바꿨으면 G01이 잡음 (심은 사례 S07) |
| X9 | 이미 전부 skip이던 파일의 테스트 함수를 수정 (week3 `test_app.py` 같은 경우) | **T03 (`CHANGED_TESTS_ALL_SKIPPED`)** | 6장 Q2 |
| X10 | 바뀐 테스트 파일에서 수집 오류 | B04만 | 실행 상태 `error` → T03 평가 안 함 |

경계 사례(T03이 나와야 함)는 `docs/eval/20261111_explore/boundary_cases.sh`의 C1·C2·C4다. C3(소스 삭제)는 4장에서 다룬다.

## 4. N06 소스 삭제 — 판정 그대로, 반례만 추가

| # | 사례 | 기대 (v3.2) |
|---|---|---|
| D1 | 참조 없는 모듈 삭제, 남은 테스트 통과 | SAFE + N06 |
| D2 | 남은 코드가 import하는 모듈 삭제 | B04 (수집 오류) 또는 B03 |
| D3 | 함수 안에서만 import하고, 테스트가 그 경로를 실행하지 않음 | SAFE + N06 — **알려진 한계**로 기록 (삭제 영향을 보지 않음) |

D3은 "SAFE가 틀릴 수 있는 경우"를 고정해 두는 사례다. 판정을 바꾸지 않고, 바꾸려면 Decision Utility에서 비용과 함께 다시 정한다.

## 5. 실행 근거 보강

### 5.1 coverage·pytest-cov 실제 버전

- 테스트를 돌리기 전에 대상 Python으로 `.rg/tools`의 `coverage.__version__`, `pytest_cov.__version__`을 읽는다.
- 요구 버전과 다르면 한 번 다시 설치하고 다시 읽는다.
- 그래도 다르거나 읽지 못하면 그 실행의 coverage를 근거로 쓰지 않는다 → E01 (6장 Q4).
- `record`에 요구 버전과 실제 버전을 둘 다 남긴다.

### 5.2 원본 node id

- 줄별 실행 테스트(`lines`)와 보고서는 지금처럼 함수 단위로 둔다.
- `test_run.nodeid_map` = `{함수 단위 id: [원본 node id ...]}`를 추가한다. parametrize 값이 다른 두 결과가 하나로 합쳐지지 않는지 단위 테스트로 확인한다.
- Stage 2.0의 mutation에서 테스트만 골라 다시 돌릴 때 이 표를 쓴다.

## 6. 결정이 필요한 것 (추천 포함)

| # | 질문 | 선택지 | 추천 |
|---|---|---|---|
| Q1 | `CHANGED_TESTS_ALL_SKIPPED`의 단위 | (a) **바뀐 테스트 함수 단위** (b) 바뀐 파일 전체 단위 | **(a)**. (b)는 헬퍼만 바꿔도 파일 전체가 skip이면 발동해 X1과 충돌한다 |
| Q2 | 이미 skip이던 테스트를 수정한 경우 (X9) | (a) **발동** (b) base에서도 skip이면 발동 안 함 | **(a)**. 바뀐 테스트가 검증에 쓰이지 않는다는 사실은 같다. (b)는 base를 매번 다시 돌려야 해서 비용이 크다. 근거에 "이전에도 skip이었는지 확인 안 함"을 적는다 |
| Q3 | pytest 수집 패턴 | (a) **기본 패턴만 + 설정 감지 시 NOTE** (b) `pytest.ini`·`pyproject.toml`·`setup.cfg`·`tox.ini`의 `python_files`를 읽음 | **(a)**. 시험장 5개 저장소(Predict, week1~4)는 이력 전체에 `python_files`·`python_classes`·`python_functions` 설정이 없다 (`git log --all -S`로 확인). `python_files` 설정이 있으면 "T03 판단이 정확하지 않을 수 있음" NOTE(N07)만 낸다 |
| Q4 | coverage 버전 불일치 처리 | (a) **재설치 1회 후에도 다르면 E01** (b) 기록만 | **(a)**. 버전이 다르면 줄 공백 계산의 전제가 깨진다. 지금은 불일치가 일어난 적이 없어 판정 변화는 없을 것으로 예상한다 |
| Q5 | `TEST_SUITE_REMOVED` 범위 | (a) **`no_tests` + 테스트 파일 삭제만** (b) 테스트 파일 삭제 전반에 NOTE 추가 | **(a)**. 일반 삭제(X8)는 G01·심은 사례 S07로 이미 드러난다. 새 신호를 늘리지 않는다 |

## 7. 회귀·완료 기준

| 항목 | 기준 |
|---|---|
| 경계 사례 C1·C2·C4 | T03 REVIEW, 원인 코드 각각 `COLLECTION_EMPTY`·`CHANGED_TESTS_ALL_SKIPPED`·`TEST_SUITE_REMOVED` |
| 반례 X1~X10, D1~D3 | 위 표의 기대와 일치 (심은 사례 또는 단위 테스트) |
| 기존 심은 사례 | Predict 19/19, 4주차 6/6 그대로 |
| 58커밋 | 판정이 바뀐 커밋과 T03이 새로 나온 커밋을 **모두 목록으로** 보고하고 이유를 적는다. 예상: week3에서 전부 skip인 `tests/test_app.py`의 테스트 함수를 바꾼 커밋에 T03이 붙음. 이 커밋들은 이미 G01로 REVIEW라 판정은 그대로일 것 |
| 과잉 경고 | `need: no` 코드 변경 11/12가 늘었는지 따로 보고 (T03 때문에 새로 경고된 `need: no` 커밋 수) |
| coverage 버전 | 정상·불일치·읽기 실패 단위 테스트 |
| node id | parametrize 값이 다른 결과가 `nodeid_map`에서 구분됨 |
| 결정성 | 같은 입력 → 같은 T03 근거 (2회 실행) |
| 비용 | API 호출 0, 추가 테스트 실행 0 (coverage 버전 확인용 Python 호출 1회만) |

결과는 보고서 #12로 쓴다.

## 8. 구현 위치

| 파일 | 변경 |
|---|---|
| `releaseguard/test_changes.py` (신규) | 수집 대상 판정, 바뀐 테스트 함수 찾기(AST), T03 원인 계산. 순수 함수 |
| `analyze.py` | `test_changes` 결과를 `decide`에 전달, `nodeid_map`, `record`에 실제 버전 |
| `decide.py` | T03 규칙, `RULES_VERSION = "3.2"`, NOT_VERIFIED_RULES에 T03 |
| `runner.py` | `ensure_coverage` 버전 확인, 원본 node id 보존 |
| `report.py` | T03 근거, scope와 T03 차이 한 줄 |
| `eval/seeds_*.yaml`, `tests/` | 경계 사례·반례 |
| `docs/design.md`, `usage.md` | 규칙 표 갱신 |
