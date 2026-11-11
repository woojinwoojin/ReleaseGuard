# Stage 1.7 Reliability Gate — 설계

- 작성: 2026-11-11 · Claude 초안 → **외부 리뷰 조건부 승인 반영, Q1~Q5 확정** (같은 날)
- 근거: [보고서 #11](eval/20261111_eval_report_11.md) 3~5장
- 규칙 버전: v3.1 → **v3.2** (T03·N07 추가, N06 메시지 보강). 나머지 규칙은 그대로다.

## 1. 목적과 범위

**목적**: 바뀐 테스트가 실제로 실행되지 않았는데 SAFE가 나오는 경우를 드러낸다. 실행 근거(coverage 버전·위치, node id)도 재현할 수 있게 남긴다.
**원칙**: 검증하지 못한 것을 검증했다고 말하지 않는다. 판단할 수 없는 경우에는 판단을 보류했다는 사실을 남긴다.

| 포함 | 제외 |
|---|---|
| T03 (원인 코드 4개), N07 (수집 설정 미지원으로 검사 보류) | G01 완화, 판정 구분력 개선 (Decision Utility로 따로 추적) |
| 소스 삭제 N06 반례, 메시지에 "삭제 영향 미검증" 명시 | 삭제 영향 분석 |
| coverage·pytest-cov 실제 버전과 import 위치 확인 | 실행 격리 (2.0 이후) |
| parametrize를 포함한 원본 node id 보존 | scope 의미 재설계 |
| 회귀: 58커밋 + 심은 사례 + 새 반례 | 테스트 추가 실행 (base의 skip 상태 확인 등), 에이전트 변경 |

## 2. T03 — 바뀐 테스트가 실행되지 않음 (REVIEW)

### 2.1 공통 정의

**수집 대상 테스트 파일**: 바뀐 파일이 아래를 모두 만족해야 한다.
- 분류가 `test`다.
- 파일 이름이 pytest 기본 패턴(`test_*.py`, `*_test.py`)에 맞는다.
- pytest 설정에 `testpaths`가 있으면 그 경로 아래에 있다. 시험장 6개 저장소는 모두 `testpaths = tests`를 쓰므로 지원한다.

`conftest.py`, `tests/fakes.py` 같은 파일은 수집 대상이 아니다.

**테스트 함수 (AST)**: pytest 기본 규칙으로 찾는다.
- 모듈 수준의 `test*` 함수
- `Test*` 클래스(중첩 포함) 안의 `test*` 메서드
- 범위는 데코레이터 줄부터 함수 끝까지다.

**바뀐 테스트 함수**: diff에서 추가된 줄이 범위에 걸치는 테스트 함수다. 새 파일이면 모든 테스트 함수가 해당한다.

**평가 조건**: 둘 다 만족할 때만 T03을 본다.
- 이번 실행이 **전체 실행**이다 (node id 지정 없음). `analyze`의 첫 실행은 항상 전체 실행이고, 이 사실을 `test_change_checks.full_run`에 기록한다.
- 실행 상태가 `passed`·`failed`·`no_tests`다. `error`·`timeout`·`not_run`이면 B04·E01이 이미 근거가 없다고 말하므로 T03을 보지 않는다.

**관찰한 사실만 말한다**: JUnit에 결과가 없다는 것을 "pytest가 수집하지 않았다"로 단정하지 않는다. 원인 코드 이름도 관찰한 사실로 짓는다.

### 2.2 원인 코드

| 코드 | 조건 (모두 만족) | 근거 |
|---|---|---|
| `NO_TEST_RESULTS` | ① 수집 대상 테스트 파일이 추가(A)·수정(M)됨, 또는 내용이 바뀐 채 이름이 바뀜(R) ② head 파일에 테스트 함수가 1개 이상 정의됨 (AST) ③ 이번 실행의 JUnit에 그 파일 결과가 0개 | 파일, 변경 상태, 정의된 테스트 함수 수, 결과 0 |
| `CHANGED_TESTS_ALL_SKIPPED` | ① 바뀐 테스트 함수 중 결과가 있는 것이 1개 이상 ② 그 함수들의 **모든 결과**(parametrize 값마다)가 skip | 파일, 바뀐 함수 n개, 결과 k개 중 skip k개, skip 사유, 결과가 없는 바뀐 함수 |
| `MODULE_SKIPPED` | ① 그 파일에 모듈 수준 skip 기록이 있음 ② 바뀐 테스트 함수가 1개 이상 | 파일, skip 메시지, 바뀐 함수 이름 |
| `TEST_SUITE_REMOVED` | ① 실행 상태가 `no_tests` ② 수집 대상 테스트 파일이 1개 이상 삭제(D)됨 | 삭제된 테스트 파일 |

- **모듈 수준 skip**: `pytest.skip(allow_module_level=True)`이나 `pytest.importorskip`는 JUnit(xunit1, pytest 9.1.1에서 확인)에 함수별 결과 없이 `classname=""`, `name=<모듈 경로>` 한 줄로 남는다 (메시지 "collection skipped"). 이것을 함수별 skip으로 추정하지 않고 `MODULE_SKIPPED`로 분리한다. `pytestmark = pytest.mark.skipif(...)`는 함수마다 skip 결과를 남기므로 `CHANGED_TESTS_ALL_SKIPPED`로 간다.
- **parametrize**: 한 함수의 결과 중 하나라도 skip이 아니면 "전부 skip"이 아니다.
- **결과가 없는 바뀐 함수**: 같은 파일의 다른 함수에는 결과가 있는데 바뀐 함수에만 결과가 없는 경우다. 원인 코드를 따로 두지 않는다. `CHANGED_TESTS_ALL_SKIPPED`가 발동하면 그 근거에 함께 적고, 발동하지 않으면 `test_change_checks`에 기록만 한다.
- 원인 코드는 커밋당 여러 개 나올 수 있다. T03 finding은 하나만 만들고, 근거 줄은 원인 코드로 시작한다. 구조화된 상세는 `test_change_checks.reasons`에 넣는다.
- 메시지는 실행되지 않았다는 사실만 말한다. 테스트가 틀렸다고 단정하지 않는다.

### 2.3 pytest 수집 설정 — 지원하지 않으면 보류 (N07)

head 스냅샷 루트의 `pytest.ini`, `pyproject.toml`(`[tool.pytest.ini_options]`), `tox.ini`(`[pytest]`), `setup.cfg`(`[tool:pytest]`)와 모든 `conftest.py`를 읽는다.

| 설정 | 처리 |
|---|---|
| `testpaths` (glob 없음) | 지원: 수집 대상 판정에 반영 |
| `testpaths`에 glob, `python_files`·`python_classes`·`python_functions`, `norecursedirs` | **미지원** |
| `addopts`에 수집을 바꾸는 옵션 (`--ignore`, `--ignore-glob`, `--deselect`, `-k`, `-m`, `--pyargs`, 위치 인자) | **미지원** |
| `conftest.py`의 `collect_ignore`, `collect_ignore_glob`, `pytest_collection_modifyitems`, `pytest_ignore_collect`, `pytest_collect_file`, `pytest_pycollect_makeitem` | **미지원** |
| `pythonpath` 등 수집과 관계없는 설정 | 무시 |

미지원 설정이 있으면:
- `NO_TEST_RESULTS`, `CHANGED_TESTS_ALL_SKIPPED`, `MODULE_SKIPPED` 판단을 **보류**한다. 기본 규칙으로 판단하면 틀린 경고가 날 수 있어서다.
- 바뀐 수집 대상 테스트 파일이 있을 때만 **N07 NOTE**를 내고, 발견한 설정과 보류한 검사를 근거로 남긴다. 바뀐 테스트 파일이 없으면 보류할 검사가 없으므로 내지 않는다.
- `test_change_checks.status = "held"`로 기록하고, 보고서에 "이 검사는 수행하지 않았다"고 적는다. 보류는 SAFE를 보증하지 않는다.
- `TEST_SUITE_REMOVED`는 계속 본다. "테스트 결과가 0개이고 테스트 파일이 삭제됨"은 설정과 관계없이 관찰한 사실이기 때문이다.

### 2.4 판정·scope와의 관계

- **판정**: T03은 REVIEW다. BLOCK이 있으면 그대로 BLOCK이다.
- **scope는 바꾸지 않는다.** scope는 "검증할 수 있는 종류의 파일인가"이고, T03은 "바뀐 테스트가 실제로 실행됐는가"다. 그래서 `scope=COMPLETE`와 T03 REVIEW가 함께 나올 수 있고, 보고서에 이 차이를 한 줄로 적는다.
- **G01과의 관계**: 소스만 추가했고 `no_tests`이면 지금처럼 G01만 낸다. 삭제된 테스트 파일이 없으므로 T03 조건에 걸리지 않는다.
- T03은 보고서에서 "검증이 성립하지 않은 것" 묶음(`NOT_VERIFIED_RULES`)에 들어간다.

## 3. 반례

| # | 사례 | 기대 | 이유 |
|---|---|---|---|
| X1 | 테스트 파일의 헬퍼 함수만 바뀌고, 그 파일의 테스트는 실행됨 | T03 없음 | 결과 > 0, 바뀐 테스트 함수 없음 |
| X2 | `tests/fakes.py`만 바뀜 | T03 없음 | 수집 대상 아님 |
| X3 | `conftest.py`의 fixture만 바뀜 | T03 없음 | 수집 대상 아님. 영향은 기존 실행 결과로 드러남 |
| X4 | 새 테스트 2개 중 1개만 skip | T03 없음 | 전부가 아님 (skip 표에는 나옴) |
| X4p | parametrize 2개 값 중 1개만 skip | T03 없음 | 함수의 결과가 전부 skip이 아님 |
| X5 | 문서만 바뀜 | T03 없음, SAFE | 테스트를 실행하지 않음 |
| X6 | 소스 추가 + 저장소에 테스트 0개 (`no_tests`) | G01만 | 삭제된 테스트 파일 없음 |
| X7 | 테스트 파일 이름만 바뀜 (R100) | T03 없음 | 추가된 줄 없음 |
| X8 | 테스트 파일 하나를 지웠지만 다른 테스트는 실행됨 | T03 없음 | `no_tests`가 아님 |
| X9 | 이미 전부 skip이던 파일(`pytestmark` skipif)의 테스트 함수 수정 | **T03 `CHANGED_TESTS_ALL_SKIPPED`** | Q2. base 상태는 확인하지 않았다고 근거에 적음 |
| X10 | 바뀐 테스트 파일에서 수집 오류 | B04만 | 실행 상태 `error` → T03을 보지 않음 |
| X11 | `tests/test_helpers.py`(테스트 함수 없음)의 헬퍼만 추가·수정 | T03 없음 | 테스트 함수가 정의되지 않음. 파일 이름만으로 테스트 의도를 단정하지 않음 |
| X12 | `addopts = -k ...` 등 미지원 설정 + 바뀐 테스트 파일 | T03 보류, N07 | 2.3 |

**T03이 나와야 하는 사례**:

| 사례 | 기대 원인 코드 |
|---|---|
| `__init__`이 있는 `Test*` 클래스의 테스트 추가 (pytest가 수집하지 않음) | `NO_TEST_RESULTS` |
| 추가한 테스트 함수가 전부 skip | `CHANGED_TESTS_ALL_SKIPPED` |
| 모듈 수준 `importorskip` 파일에 테스트 추가 | `MODULE_SKIPPED` |
| 유일한 테스트 파일 삭제 → `no_tests` | `TEST_SUITE_REMOVED` |

**경계 사례 C1의 처리**: `boundary_cases.sh`의 C1은 test_ 함수가 없는 테스트 파일이다. 이것은 X11과 같으므로 T03을 내지 않는다. "수집 0개" 사례는 위 표의 `__init__` 클래스로 바꿔 고정한다.

## 4. N06 소스 삭제 — 판정은 그대로, 반례와 메시지만

| # | 사례 | 기대 (v3.2) |
|---|---|---|
| D1 | 참조 없는 모듈 삭제, 남은 테스트 통과 | SAFE + N06 |
| D2 | 남은 코드가 import하는 모듈 삭제 | B04 (수집 오류) |
| D3 | 함수 안에서만 import하는데 테스트가 그 경로를 실행하지 않음 | SAFE + N06 — **알려진 한계** |

N06 메시지에 "테스트가 지나가지 않는 경로의 참조는 확인하지 않음(삭제 영향 미검증)"을 명시한다. 그래야 D3의 SAFE가 미검증 상태라는 것이 보고서에 드러난다.

## 5. 실행 근거 보강

### 5.1 coverage·pytest-cov 실제 버전과 위치

1. 테스트를 돌리기 전에 대상 Python + `.rg/tools` 환경에서 `coverage`·`pytest_cov`를 import해 `__version__`과 `__file__`을 읽는다.
2. 정상 조건: 버전이 요구 버전과 같고, 파일이 `.rg/tools` 아래에 있다. 다른 버전이나 다른 위치(호스트 패키지)에서 import되면 정상이 아니다.
3. 정상이 아니면 `--force-reinstall`로 한 번 다시 설치하고 다시 확인한다.
4. 그래도 정상이 아니거나 읽지 못하면 테스트를 돌리지 않고 `not_run` → **E01**로 처리한다. 잘못된 coverage는 쓰지 않는다.
5. `record.coverage_runtime`에 요구 버전, 실제 버전, 위치 확인 결과, 재설치 여부를 남긴다.

### 5.2 원본 node id

- 줄별 실행 테스트(`lines`)와 보고서는 지금처럼 함수 단위로 둔다.
- `test_run.nodeid_map` = `{함수 단위 id: [원본 node id ...]}`를 coverage context에서 만든다.
- Stage 2의 테스트 선택 재실행에 쓰되, 이 표만으로 충분하다고 보지 않는다. 선택 실행과 전체 실행 결과를 비교해 확인한다 (2.1).

## 6. 결정 (확정)

| # | 질문 | 결정 | 조건 |
|---|---|---|---|
| Q1 | `CHANGED_TESTS_ALL_SKIPPED`의 단위 | 바뀐 테스트 함수 단위 | parametrize 값마다 결과를 모두 확인 |
| Q2 | 이미 skip이던 테스트를 수정한 경우 | 발동 | 근거에 "base 상태 확인 안 함" 명시 |
| Q3 | pytest 수집 설정 | 기본 패턴 + `testpaths` 지원 | 미지원 설정에서는 관련 T03 검사 보류 + N07 |
| Q4 | coverage 버전 불일치 | 재설치 1회 후에도 다르면 E01 | 버전과 import 위치를 모두 확인 |
| Q5 | `TEST_SUITE_REMOVED` 범위 | `no_tests` + 테스트 파일 삭제일 때만 | — |

## 7. 회귀·완료 기준

| 항목 | 기준 |
|---|---|
| T03 사례 4개 (3장) | 각각 기대 원인 코드로 REVIEW |
| 반례 X1~X12, D1~D3 | 위 표의 기대와 일치 (통합 테스트·심은 사례) |
| JUnit 결과와 실제 수집 구분 | 결과 0건을 "수집 안 됨"으로 단정하는 표현이 없음 |
| 모듈 수준 skip | 함수별 skip과 구별되고 근거(메시지)가 남음 |
| 헬퍼 전용 테스트 패턴 파일 (X11) | 불필요한 T03 없음 |
| 미지원 pytest 수집 설정 (X12) | T03 오판 없이 보류, 보고서에 수행하지 않은 검사 표시 |
| 기존 심은 사례 | Predict 19/19, 4주차 6/6 그대로 |
| 58커밋 | 판정이 바뀐 커밋과 T03·N07이 새로 나온 커밋을 **모두 목록으로** 보고하고 이유를 적음. 판정 변화 0이 성공 조건은 아님 (실제 버그 수정이라 의도된 변화가 있을 수 있음) |
| 부작용 관찰 | `need: no` 코드 변경 11/12가 바뀌었는지, T03 때문에 새로 경고된 `need: no` 커밋 수를 따로 보고. **성공 지표가 아니라 관찰 지표** |
| coverage 버전 | 정상·버전 불일치·다른 위치·읽기 실패 단위 테스트 |
| node id | parametrize 값이 다른 결과가 `nodeid_map`에서 구분됨 |
| 결정성 | 같은 입력 → 같은 T03 근거 |
| 비용 | API 호출 0, 추가 테스트 실행 0 (coverage 확인용 Python 호출 1회) |

보고서 #12에서는 두 가지를 나눠서 보여준다.
1. 이전에 SAFE였던 미검증 변경이 REVIEW로 바뀌었는지
2. 그 대가로 새 과잉 경고가 얼마나 생겼는지

## 8. 구현 위치

| 파일 | 변경 |
|---|---|
| `releaseguard/test_changes.py` (신규) | pytest 설정 읽기, 수집 대상 판정, 테스트 함수 찾기(AST), 원인 코드 계산. 순수 함수 |
| `analyze.py` | `test_change_checks` 계산·저장, coverage 도구 확인, `nodeid_map` |
| `decide.py` | T03·N07, N06 메시지, `RULES_VERSION = "3.2"`, `NOT_VERIFIED_RULES`에 T03 |
| `runner.py` | `check_coverage_tools`, coverage context의 원본 node id |
| `report.py` | T03 검사 상태, scope와 T03의 차이, coverage 실제 버전 |
| `evaluate.py` | 행에 T03 원인 코드·검사 상태 |
| `eval/seeds_predict_success.yaml`, `tests/` | T03 사례·반례 |
| `docs/design.md`, `usage.md` | 규칙 표 갱신 |
