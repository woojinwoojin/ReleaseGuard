# 설계 v2 (Stage 1 MVP)

작성: 2026-11-03 · 문제 정의: `docs/problem.md` (v2) · v1 설계는 이 문서의 git 기록 참고

## 실행

```
python -m releaseguard analyze --repo ../predict-success --base HEAD~1 --head HEAD [--python <경로>] [--no-agent]
→ out/<YYYYMMDD>_<head 7자리>.json  (판정 + 근거)
→ out/<YYYYMMDD>_<head 7자리>.md    (보고서)

python -m releaseguard eval  [--cases eval/cases.yaml] [--repeat N] [--agent]   # 커밋 전체
python -m releaseguard seeds [--seeds eval/seeds_predict_success.yaml]           # 결함을 심은 사례
python -m releaseguard szz   [--cases eval/cases.yaml]                           # 결함 줄 추적
```

`base...head` 비교는 `git merge-base base head`에서 head까지의 변경이다 (PR diff와 같은 기준).

## 처리 흐름

| 단계 | 하는 일 | 방식 | 모듈 |
|---|---|---|---|
| 1. Collect | 변경 파일, 추가·수정된 줄 | git (읽기 전용) | `git_ops.py` |
| 2. Classify | 파일 분류, 비밀값 패턴 | 규칙 (`configs/rules.yaml`) | `classify.py` |
| 3. Run | head를 임시 폴더에 풀고 pytest + coverage 실행, 테스트별로 실행한 줄 기록. 실패한 테스트는 base에서 다시 실행 | 실행 (결정적) | `runner.py` |
| 4. Gaps | 바뀐 실행 가능 줄 중 어떤 테스트도 실행하지 않은 줄 = 검증 공백 | 결정적 | `gaps.py` |
| 5. Decide | 판정 규칙 v3.2 + 검증 범위 | 규칙 | `decide.py`, `changed_tests.py` |
| 6. Explain | 공백마다 "바뀐 동작 + 필요한 테스트" | 에이전트 (좁은 질문, 판정에 안 들어감) | `agent.py`, `agent_tools.py` |
| 7. Report | JSON + Markdown | 템플릿 | `report.py` |

테스트를 돌릴 수 없으면(.venv 없음, 시간 초과) 판정은 E01(REVIEW)이고, 이름 규칙·import로 **추정**한 관련 테스트를 보여준다 (`related_tests.py`, v1의 방식).

## 3단계 Run 상세

- **스냅샷**: `git archive <sha>`를 임시 폴더에 푼다. 대상 저장소의 작업 폴더·`.git`은 바뀌지 않는다. git에 없는 파일(`.env`, 로컬 데이터)은 들어가지 않는다.
- **Python**: 대상 저장소의 `.venv` (또는 `--python`). 대상 환경에는 아무것도 설치하지 않는다.
- **coverage**: ReleaseGuard가 `.rg/tools`에 설치한 coverage 7.17.0을 `PYTHONPATH`로 넣는다. 대상 Python과 버전(3.13)이 달라야 하면 실행하지 않고 사유를 남긴다.
- **테스트별 실행 줄**: coverage `dynamic_context = test_function`. pytest JUnit XML(xunit1)로 context를 node id(`tests/test_x.py::test_f`)에 연결한다.
- **전체 테스트 실행**: 선택 실행은 하지 않는다 (Predict_Success 약 12초). 시간 상한 기본 300초.
- **실패 비교** (v3, `analyze.compare_failures`): head에서 실패한 테스트만 head에서 한 번 더 → 통과하면 FLAKY. 남은 실패의 테스트 **파일**을 base에서 실행 (node id로 돌리면 base에 없는 테스트가 수집 오류로 섞여 구분이 안 됨).

  | 비교 상태 | 조건 | 규칙 |
  |---|---|---|
  | REGRESSION | base에서 통과(또는 건너뜀) | B03 |
  | NEW_TEST_FAILING | base에 그 파일·테스트가 없음 | B03 |
  | PRE_EXISTING | base에서도 실패하고 **같은 실패로 확인됨** (아래 v3.1 조건) | T01 |
  | INCOMPARABLE | base에서도 실패, 하지만 같은 실패로 확인하지 못함 | B03 |
  | UNKNOWN | base 실행이 결과를 못 냄 (수집 오류·시간 초과) | B03 |
  | FLAKY | head 재실행에서 통과 | T02 |

  원래부터 실패했다고 **확인된 경우에만** BLOCK을 REVIEW로 낮춘다.

  **같은 실패 조건 (v3.1, 2026-11-04, `compare.py`)** — 모두 확인돼야 PRE_EXISTING, 하나라도 아니거나 확인 못 하면 INCOMPARABLE:
  1. 같은 node id가 base·head에서 수집되고 실패
  2. 테스트 파일이 안 바뀌었거나, **새 테스트 함수만 추가됨** (기존 테스트·헬퍼·fixture·import가 AST 기준으로 모두 같음. 데코레이터 포함, 줄 번호 제외) — 처음 구현은 이 좁은 경우만
  3. 공유 테스트 맥락 그대로: 의존성, conftest, pytest 설정(`pytest.ini`·`setup.cfg`·`tox.ini`), 테스트 헬퍼 모듈(테스트 폴더의 `test_*.py`가 아닌 파일)
  4. 실패 지문 같음: 정규화한 전체 메시지(임시 경로·메모리 주소만 제거, 숫자는 유지) + 예외가 난 파일·종류 + traceback 프레임(파일·함수, 줄 번호 제외)

  근거는 `failures[].comparison_evidence`에 남는다. v3에서는 테스트 파일이 안 바뀌면 지문 비교 없이 PRE_EXISTING이었다 → v3.1은 그 경우에도 지문이 같아야 한다 (더 엄격).
  계기: Eval #4에서 week3의 옛 결함 하나(`93abf12`)가 같은 파일에 테스트가 추가될 때마다 INCOMPARABLE → BLOCK 5번.
  PRE_EXISTING은 "관찰된 실패가 원래도 있었다"는 뜻이지 이번 커밋에 다른 회귀가 없다는 보증이 아니다.
- **스냅샷 예외**: head 트리에 `.gitmodules`, `.gitattributes`의 `export-ignore`·`filter=lfs`가 있으면 E03.
- **실행 기록**: 명령(임시 폴더는 `<tmp>`), Python 경로·버전, coverage 버전, SHA, timeout, 시도 횟수, 재실행 목록을 `test_run.record`에 남긴다. 임시 폴더는 작업 폴더 보호이지 샌드박스가 아니다.
- **깨끗한 스냅샷 ≠ 격리된 실행 환경**: 스냅샷은 git에 없는 파일(`.env`, gitignore된 데이터)을 빼지만, 호스트 환경 변수는 테스트에 그대로 넘어간다. 그래서 자격 증명류 변수 **이름**(KEY·TOKEN·SECRET·PASSWORD·CREDENTIAL, 값은 저장 안 함)을 `record.host_secret_env`에 남긴다.
- **건너뛴 테스트**: `test_run.skipped`에 node id와 사유. 판정에는 아직 넣지 않는다 — 새로 추가한 테스트가 전부 skip돼도 SAFE가 나올 수 있다 (알려진 한계).
- 문서만 바뀌었으면 실행하지 않는다.

## 4단계 Gaps 상세

바뀐 줄 하나는 넷 중 하나다.

| 상태 | 뜻 |
|---|---|
| covered | 어떤 테스트가 실행함 (테스트 목록이 남는다) |
| import_only | 모듈을 불러올 때만 실행됨 (def·클래스·상수 줄) — 공백으로 보지 않음 |
| gap | 실행 가능한 줄인데 어떤 테스트도 실행하지 않음 → **검증 공백** |
| not_executable | 빈 줄·주석·docstring 등 |

연속된 공백 줄은 사이에 실행 불가 줄만 있으면 하나의 범위로 묶는다. Python 소스(테스트 제외)만 본다.

### 함수별 공백 그룹 (1.4, 판정 미반영)

판정이 끝난 뒤에 줄 단위 공백을 묶는다. `lines`와 G01 근거는 그대로 남고 `gap_groups`가 추가된다.

- 그룹: 가장 안쪽 함수. 함수 밖은 `class_body`·`module`, 파싱 실패는 `unmapped`. 줄 범위가 함수 경계를 넘으면 나뉜다.
- 순서: `review_priority`(NORMAL → LOW), 공백 줄 수 내림차순, 파일 경로, 시작 줄, 이름. 결함 위험 순서가 아니다.
- LOW: `configs/rules.yaml`의 `review_priority.low`에 선언한 경로만. 폴더 이름으로 추측하지 않는다. "안전하다"가 아니라 "뒤에 보여준다"는 뜻이고, 실험 코드를 서비스가 호출한다면 목록에서 뺀다.
- 넣지 않은 것: AST 위험도, 커밋 전체 등급, 작은 공백 자동 하향 (근거: [보고서 #7](eval/20261107_eval_report_7.md)).

## 판정 규칙 v3 (2026-11-04) · v3.2 (2026-11-11)

**SAFE는 "코드가 맞다"가 아니라 "정의된 검증 절차에서 검토 사유를 찾지 못했다"는 뜻.** 검증하지 못한 변경이 있으면 SAFE를 내지 않는다 (외부 설계 리뷰 반영, 방식 A).

가장 심각한 규칙의 판정이 최종 판정. 아무 규칙도 발동하지 않으면 SAFE. NOTE는 판정에 영향 없음.

| id | 판정 | 조건 | 묶음 |
|---|---|---|---|
| B01 | BLOCK | 추가된 줄에 비밀값 패턴 | 찾은 것 |
| B03 | BLOCK | head에서 실패, 원래부터 실패했다고 확인되지 않음 (REGRESSION·NEW_TEST_FAILING·INCOMPARABLE·UNKNOWN) | 찾은 것 |
| B04 | BLOCK | head에서 테스트 수집·실행 오류 (import 실패 등) | 검증 불성립 |
| G01 | REVIEW REQUIRED | 검증 공백이 1줄 이상 | 찾은 것 |
| T01 | REVIEW REQUIRED | 같은 조건으로 base에서도 실패 (PRE_EXISTING) | 찾은 것 |
| T02 | REVIEW REQUIRED | 다시 돌리면 통과 (FLAKY) | 찾은 것 |
| R04 | REVIEW REQUIRED | 의존성 변경 (테스트 환경이 실제와 다를 수 있음) | 찾은 것 |
| E01 | REVIEW REQUIRED | 테스트 미실행·시간 초과·coverage 없음 | 검증 불성립 |
| E02 | REVIEW REQUIRED | 검증 범위 밖 변경: 설정·데이터·분류 규칙에 없는 파일·Python이 아닌 소스 | 검증 불성립 |
| E03 | REVIEW REQUIRED | 스냅샷이 저장소와 다를 수 있음 (서브모듈·export-ignore·LFS) | 검증 불성립 |
| T03 | REVIEW REQUIRED | 바뀐 테스트가 이번 실행에서 실행되지 않음: NO_TEST_RESULTS · CHANGED_TESTS_ALL_SKIPPED · MODULE_SKIPPED · TEST_SUITE_REMOVED (v3.2, [design_stage1_7.md](design_stage1_7.md)) | 검증 불성립 |
| N06 | NOTE | 소스 삭제. 테스트 실행 중 참조는 B03·B04로 드러나지만, 테스트가 지나가지 않는 경로의 참조는 확인하지 않음 (삭제 영향 미검증) | 참고 |
| N07 | NOTE | pytest 수집 설정(python_files·addopts -k 등)을 지원하지 않아 T03 일부 검사를 보류함 (v3.2) | 참고 |

보고서는 "검증이 성립하지 않은 것"과 "검증해서 찾은 것"을 나눠 보여준다.

### 검증 범위 (`scope`)

판정과 따로 기록한다. 파일마다 검증함 / 해당 없음(문서) / 검증 못 함(이유와 함께).

| 상태 | 뜻 |
|---|---|
| COMPLETE | 문서를 뺀 모든 변경을 검증함 (문서만 바뀐 경우 포함) |
| PARTIAL | 일부 변경을 검증하지 못함 |
| UNSUPPORTED | 문서를 뺀 모든 변경을 검증하지 못함 (테스트 실행이 근거를 못 만들면 소스·테스트도 검증 못 한 것으로 봄) |

`scope`는 바뀐 파일의 종류 기준이다. 바뀐 테스트가 실제로 실행됐는지는 T03이 따로 보므로 `COMPLETE`와 T03이 함께 나올 수 있다.

v3.1 → v3.2 변경 (2026-11-11): T03·N07 추가, N06 메시지에 삭제 영향 미검증 명시, coverage 도구의 실제 버전·위치 확인(불일치 시 not_run → E01), 원본 node id(`nodeid_map`). 설계: [design_stage1_7.md](design_stage1_7.md).
v3 → v3.1 변경 (2026-11-04): 같은 실패 조건(위 3단계 상세), skip 목록, 호스트 자격 증명 변수 이름.
v2 → v3 변경: N03·N05(설정·데이터 NOTE) → E02, base 비교 상태 6개로 분리(T02 추가, UNKNOWN·INCOMPARABLE은 낮추지 않음), E03 추가, `scope` 추가.
v1에서 없어진 것: R01·R02(이름·import 추측), R03·R05(설정·데이터), R06(소스 삭제 → NOTE), R07(에이전트 HIGH), B02(테스트 삭제 → G01·B03으로 드러남).

## 6단계 Explain 상세

- 공백이 있을 때만, 큰 공백부터 최대 5개. 공백 하나에 tool calling 루프 하나 (LLM 최대 4회, 도구 최대 6회).
- 입력: 공백 위치, 앞뒤 15줄(줄 번호 포함), 그 파일의 diff, 같은 파일의 다른 변경을 실행하는 테스트 목록.
- 출력: `behavior`(바뀐 동작), `trigger`(실행 조건), `suggested_test`(file·name·scenario·assertion), `evidence`.
- "코드가 맞는지"는 판단하지 않는다. 무엇이 검증되지 않았는지만 다룬다.
- 검증: `references_valid`는 인용한 `file:경로:줄`·`tool:#n`이 존재한다는 뜻이고 **설명이 맞다는 뜻이 아니다**. `test_path_valid`는 제안 파일이 테스트 분류 경로인지. 새 파일인지도 표시.
- 모델 입력과 도구 결과에서 비밀값 패턴을 가린다. 실패한 요청도 요청 수·토큰에 들어가고, 사용량을 모르면 `unknown_usage`로 남긴다.
- 실패해도 판정·결과는 그대로 남는다.

도구는 v1과 같은 읽기 전용 4개 (`git_diff`, `read_file`, `search_code`, `list_files`), head 커밋 기준.

## Eval v2

| 평가 | 무엇을 재나 | 정답 |
|---|---|---|
| `eval` | 커밋 전체의 판정 분포, 공백, 실행 시간, 결정성(반복 실행 결과가 완전히 같은가) | 수기 판정 15개(참고), 같은 커밋에서 바뀐 테스트 |
| `seeds` | 결함을 심은 사례에서 기대 판정·규칙이 나오는가 | `eval/seeds_*.yaml`의 expected·expect_rules |
| `szz` | 나중에 고쳐진 결함 줄이 들어올 때 검증 공백이었는가 | 고친 커밋(`fix_commits`)이 지우거나 바꾼 줄을 `git blame`으로 추적 |

SZZ의 공백 비율이 낮으면 "테스트가 실행은 했지만 결함을 못 잡았다"는 뜻이다. coverage만으로는 결함을 잡지 못한다는 한계를 숫자로 보여준다.

## 보안·안전

- 대상 저장소는 읽기만 한다. 테스트는 임시 폴더의 스냅샷에서 돌린다.
- 결함 심기(`seeds`)는 임시 clone에서만 한다.
- 대상 저장소의 테스트 코드를 실행하므로, **신뢰하는 저장소에만** 쓴다 (샌드박스는 이후 단계).
- 비밀값은 위치만 남기고 값은 저장하지 않는다.
