# ReleaseGuard 사용법

기준: 2026-11-11 · 버전 0.2.0 · 판정 규칙 v3.1

ReleaseGuard는 `base...head` 변경에서 **어떤 테스트도 실행하지 않은 바뀐 줄(검증 공백)**을 찾는다. 대상 커밋의 테스트를 실제로 돌린 뒤 SAFE / REVIEW REQUIRED / BLOCK으로 판정한다. 판정은 규칙으로만 하고, LLM은 공백을 설명할 때만 쓴다(선택).

> **주의**: 대상 저장소의 테스트 코드를 그대로 실행하고, 샌드박스는 없다. 신뢰하는 저장소에만 쓴다.
> 호스트 환경 변수(예: `OPENAI_API_KEY`)도 테스트에 그대로 넘어간다. 보고서에는 그 이름만 기록된다.

## 1. 준비

### ReleaseGuard

```powershell
cd release-guard
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### 대상 저장소

| 조건 | 내용 |
|---|---|
| 언어·테스트 | Python + pytest |
| 실행 환경 | 대상 저장소의 `.venv`. 다른 Python을 쓰려면 `--python`으로 지정 |
| Python 버전 | 대상 `.venv`가 **3.13**이어야 한다 (`.rg/tools`에 설치하는 coverage·pytest-cov 버전에 맞춤) |
| coverage | 따로 설치하지 않아도 된다. 처음 실행할 때 `.rg/tools`에 설치되고, 대상 `.venv`는 건드리지 않는다 |

### 공백 설명 에이전트 (선택)

`.env.example`을 `.env`로 복사하고 `OPENAI_API_KEY`를 넣는다. 모델은 `OPENAI_MODEL`로 바꿀 수 있다 (기본 `gpt-5.4-mini`).
`--no-agent`로 실행하면 키가 없어도 되고 API도 호출하지 않는다.

## 2. 분석 — `analyze`

```powershell
# 규칙만 (API 호출 없음)
.\.venv\Scripts\python -m releaseguard analyze --repo ..\predict-success --base main --head my-branch --no-agent

# 공백 설명 포함
.\.venv\Scripts\python -m releaseguard analyze --repo ..\predict-success --base HEAD~1 --head HEAD
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--repo` | (필수) | 대상 git 저장소 |
| `--base` | (필수) | 비교 기준. 실제 비교는 `merge-base(base, head)...head` |
| `--head` | `HEAD` | 분석할 커밋 |
| `--python` | 대상 `.venv` | 테스트를 돌릴 Python |
| `--timeout` | 300 | 테스트 실행 시간 상한(초) |
| `--rules` | `configs/rules.yaml` | 분류·비밀값·검토 순서 규칙 |
| `--out` | `out` | 결과 폴더 |
| `--no-agent` | 꺼짐 | 공백 설명 없이 실행 |

### 실행 순서

1. **Collect**: `git diff`로 바뀐 파일과 줄을 모은다.
2. **Classify**: 파일을 source·test·config·docs·data·deps 등으로 나누고 비밀값을 검사한다.
3. **Run**: head 커밋을 `git archive`로 임시 폴더에 꺼내 pytest + coverage를 돌린다. 사용자 작업 폴더는 건드리지 않는다. 테스트가 실패하면 head에서 한 번 더 돌리고, base에서도 돌려 실패 원인을 비교한다.
4. **Gaps**: 바뀐 실행 가능 줄 중 어떤 테스트도 실행하지 않은 줄을 찾는다.
5. **Decide**: 판정 규칙 v3.1로 판정한다 (결정적).
6. **Explain** (선택): 공백마다 에이전트가 바뀐 동작과 추가할 테스트를 제안한다. 제안은 결정적 규칙(S01~S03)으로 한 번 더 검사한다. 판정에는 들어가지 않는다.
7. **Report**: JSON과 Markdown을 저장한다.

### 결과

콘솔에 한 줄이 나온다.

```text
REVIEW REQUIRED  (테스트: passed, 공백 12줄)
→ out\20261111_142912b.json
→ out\20261111_142912b.md
```

파일 이름은 `out/<오늘 날짜>_<head SHA 7자리>.{json,md}`이다. 예: [samples/report_142912b.md](samples/report_142912b.md)

## 3. 보고서 읽는 법

### 판정

| 판정 | 규칙 | 뜻 |
|---|---|---|
| **BLOCK** | B01 | 바뀐 줄에 비밀값 패턴이 있다 |
| | B03 | 테스트가 실패했고, 원래부터 실패했다고 확인되지 않았다 |
| | B04 | 테스트 수집 오류(import 실패 등)가 있다 |
| **REVIEW REQUIRED** | G01 | 검증 공백: 바뀐 줄 중 어떤 테스트도 실행하지 않은 줄이 있다 |
| | T01 | 원래부터 깨진 테스트가 있다 (base에서도 같은 방식으로 실패) |
| | T02 | 불안정한 테스트가 있다 (재실행하면 통과) |
| | R04 | 의존성 파일이 바뀌었다 |
| | E01 | 테스트를 돌리지 못했다 |
| | E02 | 검증 범위 밖의 변경이 있다 (설정·데이터·Docker·CI·Python이 아닌 소스) |
| | E03 | 스냅샷 예외가 있다 (export-ignore·서브모듈·LFS) |
| **SAFE** | — | ReleaseGuard의 검증 절차에서 검토 사유를 찾지 못했다. **코드가 맞다는 보증이 아니다** |

### 검증 범위 (`scope`)

판정과 따로 기록한다. 문서는 범위 계산에서 뺀다.

| 값 | 뜻 |
|---|---|
| COMPLETE | 바뀐 파일이 모두 Python 소스·테스트다. 모든 경로가 검증됐다는 뜻은 아니다 (경로는 G01이 본다) |
| PARTIAL | 일부가 설정·데이터·비Python 파일이다 |
| UNSUPPORTED | 전부 그런 파일이다 |

### 줄 상태

| 상태 | 뜻 |
|---|---|
| covered | 어떤 테스트가 실행했다. fixture(setup·teardown)에서만 실행된 줄은 `fixture_only`로 따로 센다 |
| import_only | 모듈을 불러올 때만 실행됐다 (함수 정의 줄 등) |
| gap | 어떤 테스트도 실행하지 않았다 → G01 |
| not_executable | 주석·빈 줄 등 |

**분기 공백**은 실행된 조건문 줄에서 한 번도 가지 않은 분기다. 보고서에 참고로만 나오고 판정에는 들어가지 않는다.

### 실패 비교 상태

테스트가 실패하면 head에서 다시 돌리고 base에서도 돌려서 상태를 나눈다.

| 상태 | 판정 |
|---|---|
| FLAKY (재실행하면 통과) | T02 REVIEW |
| PRE_EXISTING (원래 깨짐) | T01 REVIEW |
| REGRESSION · NEW_TEST_FAILING (이번 변경 뒤 실패) | B03 BLOCK |
| INCOMPARABLE (조건이 달라 비교 못 함) · UNKNOWN | B03 BLOCK |

PRE_EXISTING으로 인정하려면 네 조건을 모두 만족해야 한다 (v3.1). 근거는 `comparison_evidence`에 남는다.

1. 같은 node id다.
2. 테스트 파일이 그대로이거나, 새 테스트 함수만 추가됐다.
3. 공유 맥락(의존성·conftest·pytest 설정·테스트 헬퍼)이 그대로다.
4. 실패 지문(메시지·예외 위치·traceback)이 같다.

### 공백 목록 순서

공백은 함수·클래스 본문·모듈 단위로 묶어 **공백 줄이 많은 그룹부터** 보여준다. 결함 위험 순서가 아니다.
`rules.yaml`의 `review_priority.low`에 선언한 경로(지금은 `experiments/**`)는 LOW로 뒤에 보여준다. LOW가 안전하다는 뜻은 아니다.

### skip된 테스트

목록과 사유가 보고서에 나오지만 판정에는 들어가지 않는다. 새로 추가한 테스트가 전부 skip돼도 SAFE가 나올 수 있으니 skip 표를 확인한다.

### 테스트 제안 검사 (에이전트를 썼을 때)

| 코드 | 뜻 |
|---|---|
| S01 | 제안한 파일에서 이번 실행에 skip된 테스트가 있다 ("n개 중 k개"로만 쓰고, 새 테스트가 실행되지 않는다고 단정하지 않음) |
| S02 | 그 skip의 원인을 스냅샷에서 확인하지 못했다 |
| S03 | 같은 범위에 같은 이름의 테스트 함수가 있다 (AST로 확인. 범위가 불확실하면 후보로 표시) |

`PASS`는 이 검사에서 경고가 없다는 뜻이지 제안한 테스트가 유효하다는 뜻이 아니다. 내용이 중복되는지는 사람이 봐야 한다.

## 4. 평가 명령

| 명령 | 하는 일 | API |
|---|---|---|
| `eval` | 사례 파일의 커밋 전체를 `sha~1...sha`로 분석하고 라벨과 대조한다 | `--agent`일 때만 |
| `seeds` | 임시 clone에 결함을 심고 기대 판정과 대조한다 | 없음 |
| `szz` | 후속 수정 커밋에서 결함을 들여온 줄을 찾고, 그 줄이 당시 공백이었는지 잰다 | 없음 |
| `eval-agent` | 고정된 공백 사례로 설명 에이전트를 평가한다 | `--check`·`--recheck`는 없음 |

```powershell
# 커밋 전체 (기본 eval/cases.yaml = Predict_Success). --repeat로 결정성 확인
.\.venv\Scripts\python -m releaseguard eval --repeat 2
.\.venv\Scripts\python -m releaseguard eval --cases eval\cases_week3.yaml --out out\eval\week3

# 결함을 심은 사례
.\.venv\Scripts\python -m releaseguard seeds
.\.venv\Scripts\python -m releaseguard seeds --seeds eval\seeds_week4.yaml

# SZZ
.\.venv\Scripts\python -m releaseguard szz

# 에이전트 평가: API 없이 사례 확인 → 사전 점검 2회 → 나머지 이어서
.\.venv\Scripts\python -m releaseguard eval-agent --check
.\.venv\Scripts\python -m releaseguard eval-agent --max-runs 2
.\.venv\Scripts\python -m releaseguard eval-agent
# 저장된 응답에 제안 검사(S01~S03)만 다시 (API 없음)
.\.venv\Scripts\python -m releaseguard eval-agent --out out\eval\v16 --recheck
```

결과는 `out/eval/<날짜>_eval*.{json,md}`, `_seeds_*`, `_szz`, `eval-agent`는 `--out` 폴더의 `agent_runs.{json,md}`·`proposal_checks.{json,md}`로 저장된다.

### 사례 파일

| 파일 | 내용 |
|---|---|
| `eval/cases.yaml` | Predict_Success 34커밋, 라벨 15개 (회귀용) |
| `eval/cases_week1~4.yaml` | 2026-10 주차 저장소 (독립 데이터, week1~3 라벨 24개 사용자 확정) |
| `eval/seeds_predict_success.yaml`, `seeds_week4.yaml` | 결함을 심은 사례 (Predict 19개, 4주차 6개) |
| `eval/agent_cases.yaml`, `agent_cases_v2.yaml` | 에이전트 평가 사례 8개 (실험 1·2) |
| `eval/agent_scores.yaml`, `agent_scores_v2.yaml` | 사람 채점 (사용자 확정) |

라벨 기준(v2)은 `eval/cases.yaml` 머리 주석에 있다. `need`(사람이 봐야 했나: yes/no)와 `need_reason`(followup_fix·untested·policy·risky_area), `expected_scope`를 쓴다.

`eval-agent`의 안전장치:
- 사례 파일이 `status: fixed`가 아니면 API를 부르지 않는다.
- 요청 수와 추정 비용 상한(`budget`)을 넘으면 멈춘다.
- 진행 상태 파일을 공유하므로 중간에 멈춰도 이어서 돈다.
- 조건(모델·사례·상한)이 바뀌면 이어 돌리기를 거부한다.

절차는 [eval/agent_eval_protocol.md](eval/agent_eval_protocol.md)에 있다.

## 5. 규칙 설정 — `configs/rules.yaml`

- 파일 분류 패턴 (source·test·config·docs·data·deps)
- 비밀값 패턴 5종
- `review_priority.low`: 공백 목록에서 뒤로 보낼 경로 (판정 영향 없음)

## 6. 개발

```powershell
.\.venv\Scripts\python -m pytest
```

| 모듈 | 역할 |
|---|---|
| `git_ops.py` | diff·merge-base·스냅샷 |
| `classify.py` | 파일 분류·비밀값 |
| `runner.py` | 스냅샷 실행, coverage, 재실행 |
| `compare.py` | 실패 비교 상태 (v3.1) |
| `gaps.py`, `gap_groups.py` | 줄 상태·분기 공백, 함수별 그룹·순서 |
| `decide.py` | 판정 규칙 |
| `related_tests.py` | 테스트를 못 돌릴 때 관련 테스트 추정 |
| `agent.py`, `agent_tools.py` | 공백 설명 에이전트 (읽기 전용 도구 4개) |
| `suggestion_checks.py` | 테스트 제안 검사 S01~S03 |
| `report.py` | Markdown 보고서 |
| `analyze.py`, `__main__.py` | 파이프라인, CLI |
| `evaluate.py`, `eval_agent.py` | 평가 |
