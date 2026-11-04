# ReleaseGuard Eval 보고서 #4 — 판정 규칙 v3 + 라벨 v2, 독립 데이터 첫 실행

- 날짜: 2026-11-04 · 판정 규칙 v3 · 테스트 90개
- 원자료: `out/eval/v3c/{week1,week2,week3,predict}/20261104_eval.{json,md}`
- 라벨: week1~3 24개는 **Claude 초안 (외부 검토 반영, 사용자 확인 전)**, Predict 15개는 need만 사용자 확인 (expected_scope는 초안)
- 원칙: G01을 고치기 전에 **현재 규칙 그대로** 독립 데이터에 돌려 실패 유형을 본다 (외부 검토 권고)

## 1. 저장소별 결과

| 저장소 | 커밋 | 라벨 | 과소 경고 (봐야 했는데 SAFE) | 과잉 경고 (안 봐도 됐는데 경고) | 과잉 원인 | 범위 일치 |
|---|---|---|---|---|---|---|
| week1 CSV_LLM_Report | 4 | 4 | 0/2 | 1/2 | scope_only 1 (`.gitignore`) | 4/4 |
| week2 Tool_Calling_Agent | 7 | 7 | 0/4 | 3/3 | G01 2, scope_only 1 | 7/7 |
| week3 FastAPI_UI | 13 | 13 | 0/5 | 5/8 | **B03 3**, G01 2 | 13/13 |
| Predict_Success (회귀) | 34 | 15 | 0/8 | 3/7 | G01 2, scope_only 1 | 15/15 |
| **합계** | 58 | 39 | **0/19** | **12/20** | G01 6, B03 3, scope_only 3 | 39/39 |

과소 경고를 이유별로 보면 untested 0/3, followup_fix 0/8, policy 0/3, risky_area 0/5.

## 2. 해석 — 숫자가 말하는 것과 말하지 않는 것

1. **과소 경고 0/19는 강점의 증거가 아니다.** 안 봐도 됐던 커밋의 60%(12/20)에도 경고하는 상태라서, 위험한 커밋을 놓치지 않는 건 쉽다. 특히 risky_area 0/5는 ReleaseGuard가 마이그레이션·동시성을 알아봐서가 아니라, 그 커밋들에 G01이나 B03이 함께 걸렸기 때문이다 (원리상 보지 못하는 영역이라는 점은 그대로다).
2. **범위 일치 39/39는 분류 규칙 확인 이상의 의미가 없다.** expected_scope를 v3와 같은 정의로 달았기 때문에, 이 지표는 파일 분류가 맞는지만 확인한다. 불일치가 없다는 것은 분류에 버그가 없다는 뜻일 뿐이다.
3. **G01 과잉 6개가 실제 소음이다**: week2 `ef7ed86`(6/62줄 공백)·`1d72d34`(실험 스크립트, 136/136), week3 `4e3d04a`·`7df65e6`(실험 스크립트, 105/105), Predict `99309f2`·`c7733b3`. 실험 스크립트 2개는 전체가 공백이고, 나머지 4개는 공백 비율이 낮다(6~45줄). → 1.4 G01 우선순위의 입력이 된다.
4. **scope_only 3개**(`.gitignore`·`.env.example`만 바뀐 커밋)는 방식 A의 의도된 비용이다.

## 3. 새로 발견한 것 — week3의 BLOCK 6개는 진짜 결함 하나에서 나왔다

week3 커밋 13개 중 9개에서 테스트가 실패했다. 원인은 모두 같다.

- `93abf12`(FastAPI 서비스 추가)가 넣은 `tests/test_api.py`의 4개 테스트(`test_chat_unknown_conversation`, `test_chat_validation[*]`)가 가짜 클라이언트를 넣기 전에 실제 `openai.OpenAI()`를 만든다 → `OPENAI_API_KEY`가 없으면 실패.
- 로컬에는 `.env`가 있어 통과했지만, ReleaseGuard는 `git archive` 스냅샷(= CI와 같은 깨끗한 checkout)에서 돌려서 실패를 봤다.
- **4주차 저장소에서 이 결함이 고쳐졌다**: `e3867fd Never build a real OpenAI client in tests` — 커밋 안에 "이게 없으면 OPENAI_API_KEY가 없는 CI에서 실패" 주석. 즉 ReleaseGuard가 사람보다 먼저 본 결함이다.

이후 커밋의 판정은 비교 상태 규칙대로 갈렸다.

| 비교 상태 | 커밋 | 판정 |
|---|---|---|
| NEW_TEST_FAILING | `93abf12` (결함을 들여온 커밋) | BLOCK — **맞음** |
| PRE_EXISTING (test_api.py 안 바뀜) | `0b30585`, `4e3d04a`, `7df65e6` | T01 REVIEW — 맞음 |
| INCOMPARABLE (test_api.py가 바뀜) | `12b9eb3`, `8c05dc5`, `260bafb`, `2e652ab`, `6c6a32e` | BLOCK — **같은 옛 결함을 5번 BLOCK** |

INCOMPARABLE은 "테스트 파일이 바뀌었으면 기존 실패로 인정하지 않는다"는 보수적 규칙이라, 실패한 테스트 함수 자체는 그대로인데 같은 파일의 다른 테스트가 추가돼도 BLOCK이 된다. 이번 데이터에서 BLOCK 6개 중 5개가 이 경우다.

또 하나: week3의 UI 테스트 3~5개는 `data/`(gitignore)의 Superstore CSV가 없어 **skip**됐다 (4주차 `abe0ad4`가 작은 가짜 CSV로 고침). 지금은 skip이 판정에 드러나지 않고, 그 테스트가 실행했을 줄이 G01 공백으로만 나타난다 (`0b30585` 158/172줄).

## 4. 결정이 필요한 것

| # | 질문 | 추천 |
|---|---|---|
| 1 | `93abf12` 라벨을 need: yes / followup_fix(4주차 `e3867fd`, 저장소 간)로 바꿀지 | 바꿈 — 깨끗한 환경에서 실패하는 테스트를 들여왔고 이후 고쳐짐. 지금 no라서 BLOCK이 과잉으로 잡힘 |
| 2 | INCOMPARABLE을 좁힐지: 실패한 **테스트 함수의 소스**가 base와 같고 **실패 메시지**도 같으면 PRE_EXISTING | 좁힘 — 옛 결함 1개가 BLOCK 5개가 되는 문제. 판정이 내려가는 방향이라 근거(함수 소스·메시지 동일)를 보고서에 남김 |
| 3 | 스냅샷에서 skip된 테스트를 드러낼지 (예: base 대비 skip 증가, skip 사유를 보고서에) | 드러냄 — 검증하지 못한 것을 검증한 것처럼 보이지 않게 (1.1 원칙). 판정 반영은 데이터를 더 보고 |

## 5. 이 Eval의 한계

- week1~3 라벨은 아직 Claude 초안이다. 라벨이 바뀌면 숫자도 바뀐다.
- 독립 데이터 24개는 같은 사람·같은 시기의 학습용 저장소라 "독립"의 정도가 제한적이다.
- followup_fix는 미래 정보를 쓴 사후 라벨이다.
