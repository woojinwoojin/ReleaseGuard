# 설계 (Stage 1 MVP)

작성: 2026-11-03 · 문제 정의: `docs/problem.md`

## 실행

```
python -m releaseguard analyze --repo ../predict-success --base HEAD~1 --head HEAD
→ out/<YYYYMMDD>_<head 7자리>.json  (판정 + 근거, 평가용)
→ out/<YYYYMMDD>_<head 7자리>.md    (사람이 읽는 보고서)
```

`base...head` 비교는 `git merge-base base head`에서 head까지의 변경이다 (PR diff와 같은 기준).

## 처리 흐름

| 단계 | 하는 일 | 방식 | 모듈 |
|---|---|---|---|
| 1. Collect | 변경 파일, 추가·삭제 줄 수, 추가된 줄 | 코드 (읽기 전용 git) | `git_ops.py` |
| 2. Classify | 파일마다 `source / test / config / docs / data / deps / other` | 규칙 (`configs/rules.yaml`) | `classify.py` |
| 3. Related tests | 소스 ↔ 테스트 연결 (이름 규칙 + import 검색) | 규칙 + 검색 | `related_tests.py` |
| 4. Impact | 호출 관계, 영향 기능, 위험 | 에이전트 (tool calling) | 미구현 |
| 5. Decide | SAFE / REVIEW REQUIRED / BLOCK | 규칙 | `decide.py` |
| 6. Report | JSON + Markdown | 템플릿 (+ LLM 설명은 4단계 이후) | `report.py` |

## 에이전트 도구 (4단계)

읽기 전용 4개만: `git_diff`, `read_file`, `search_code`, `list_files`. 경로는 대상 저장소 안으로 제한하고, 파일은 head 커밋 기준으로 `git show`로 읽는다 (작업 폴더를 건드리지 않음).

## 4단계 Impact 상세

### 입력 (Context)
규칙 단계 결과만 준다: 변경 파일 목록(경로·상태·분류·줄 수), 소스별 관련 테스트, 발동한 판정 규칙. diff 본문은 넣지 않고 에이전트가 `git_diff`로 필요한 파일만 꺼내 본다 (Minimum Sufficient Context).

### 도구 (모두 head 커밋 기준 읽기 전용, 결과 크기 상한 있음)

| 도구 | 인자 | 상한 |
|---|---|---|
| `git_diff` | path (null이면 전체) | 12,000자 |
| `read_file` | path, start_line, end_line | 한 번에 200줄, 줄 번호 붙임 |
| `search_code` | text (고정 문자열), path_prefix | 50건 |
| `list_files` | path_prefix | 300개 |

경로에 `..`·절대 경로는 거부한다. 파일은 git 객체에서 읽으므로 저장소 밖으로 나갈 수 없다.

### 출력 (Structured Output)

```
summary            변경 요약 (2~3문장)
impacts[]          area, files[], reason, evidence[]
risks[]            level(HIGH|MEDIUM|LOW), title, detail, evidence[]
recommended_tests[] target, kind(run_existing|add_new), reason, evidence[]
```

### 근거 형식과 검증
에이전트는 근거를 아래 형식으로만 쓴다. 실행 후 코드가 하나씩 확인해 항목마다 `verified`를 붙인다.

| 형식 | 확인 내용 |
|---|---|
| `file:<경로>:<줄>` 또는 `file:<경로>:<시작>-<끝>` | head에 파일이 있고 줄 범위가 파일 안 |
| `tool:#<n>` | n번째 도구 호출이 실제로 있었고 성공 |
| `rule:<id>` | 이번 결과에서 발동한 판정 규칙 |

- 근거가 비었거나 하나라도 확인되지 않으면 `verified: false` → 보고서에 "근거 미확인"
- `run_existing` 추천은 대상 테스트 파일이 head에 있어야 확인됨
- **R07은 verified인 HIGH 위험만** 반영한다

### 한도와 실패 처리
- LLM 호출 최대 8회, 도구 호출 최대 20회. 마지막 호출은 도구 없이 답하게 한다.
- 에이전트가 실패해도 규칙 결과는 그대로 저장하고 `agent_error`에 사유를 남긴다 (fallback).
- `--no-agent`로 규칙만 실행할 수 있다 (Eval 반복 실행·비용 절감용).
- 실행 기록(`agent`): 모델, LLM 호출 수, 도구 호출 목록, 토큰, 소요 시간.

## 근거 추적

결과의 모든 판단 항목에 `evidence`를 붙인다.

- 분류: `rule:C03` (rules.yaml 규칙 id)
- 관련 테스트: `name:test_metrics.py` 또는 `import:tests/test_metrics.py:5`
- 판정: 발동한 판정 규칙 id + 해당 파일 목록
- 에이전트 위험: `tool:<호출 번호>`, `file:<경로>:<줄>` — 근거가 없으면 보고서에 "근거 미확인"

## 판정 규칙 v1

가장 심각한 규칙의 판정을 최종 판정으로 쓴다. 아무 규칙도 발동하지 않으면 SAFE.

| id | 판정 | 조건 |
|---|---|---|
| B01 | BLOCK | 추가된 줄에 비밀값 패턴 (`rules.yaml`의 `secrets`) |
| B02 | BLOCK | 수정된 소스의 관련 테스트가 삭제됨 |
| R01 | REVIEW REQUIRED | 소스 수정, 관련 테스트는 있으나 하나도 수정되지 않음 |
| R02 | REVIEW REQUIRED | 소스 수정, 관련 테스트를 찾지 못함 (빈 파일·줄 변화 없는 이름 변경은 제외) |
| R03 | REVIEW REQUIRED | 설정 변경 |
| R04 | REVIEW REQUIRED | 의존성 변경 |
| R05 | REVIEW REQUIRED | 데이터 변경 (결과에 직접 영향) |
| R06 | REVIEW REQUIRED | 소스 삭제 |
| R07 | REVIEW REQUIRED | 에이전트가 근거와 함께 HIGH 위험 제시 (4단계 이후) |

## Eval Set

Predict_Success 커밋을 그대로 쓴다.

- 자동 정답: 같은 커밋에서 실제로 수정된 테스트 파일 → 관련 테스트 탐색 precision / recall
- 수기 정답: 10~15개 커밋의 기대 판정 → 판정 정확도

## 기술 선택

- Python 3.13, 의존성 최소 (PyYAML, pytest; 4단계에서 openai)
- LLM: OpenAI Responses API (2주차와 같은 방식)
- 오케스트레이션: 직접 만든 tool calling 루프. LangGraph는 Stage 2에서 상태 전이가 생길 때 검토
