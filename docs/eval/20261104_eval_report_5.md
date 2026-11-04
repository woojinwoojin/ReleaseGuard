# ReleaseGuard Eval 보고서 #5 — 같은 실패 조건(v3.1), 라벨 확정

- 날짜: 2026-11-04 · 판정 규칙 v3.1 · 테스트 102개
- 원자료: `out/eval/v31/{week1,week2,week3,predict}/20261104_eval.{json,md}`, `out/eval/v31/*seeds*`
- 라벨: week1~3 24개 사용자 확정 (외부 검토 2회 반영). Predict 15개는 need만 사용자 확인 (expected_scope는 초안)

## 1. 바뀐 것

| 항목 | 내용 |
|---|---|
| 라벨 | `93abf12`: no → **yes / followup_fix** (4주차 저장소 `e3867fd`에서 고침, `followup_fix_repo`에 기록). 24개 확정 |
| 같은 실패 조건 | base·head 모두 실패한 테스트는 ① 같은 node id ② 테스트 파일이 안 바뀌었거나 **새 테스트 함수만 추가** ③ 공유 테스트 맥락(의존성·conftest·pytest 설정·테스트 헬퍼 모듈) 그대로 ④ **실패 지문**(전체 메시지·예외 위치·traceback 프레임) 같음 — 모두 확인돼야 PRE_EXISTING. 근거는 `comparison_evidence` |
| 더 엄격해진 곳 | v3은 테스트 파일이 안 바뀌면 지문 비교 없이 PRE_EXISTING → v3.1은 지문도 같아야 함 |
| skip | `test_run.skipped`(node id·사유)와 보고서 표. 판정에는 안 넣음 |
| 호스트 환경 | 테스트에 넘어간 자격 증명류 환경 변수 **이름**을 `record.host_secret_env`에 (값은 저장 안 함) |

## 2. 결과 — 라벨 수정 효과와 알고리즘 효과를 나눠서

| 단계 | 과소 경고 | 과잉 경고 | 과잉 원인 |
|---|---|---|---|
| Eval #4 (v3, 이전 라벨) | 0/19 | 12/20 | G01 6, B03 3, scope_only 3 |
| 라벨만 수정 (같은 실행 결과) | 0/20 | 11/19 | G01 6, **B03 2**, scope_only 3 |
| Eval #5 (v3.1, 새 라벨) | 0/20 | 11/19 | G01 7, **B03 1**, scope_only 3 |

- 라벨 수정으로 B03 과잉 1개(`93abf12` 자체 — 결함을 들여온 커밋이므로 BLOCK이 맞음)가 사라졌다.
- 알고리즘 변경으로 `2e652ab`이 BLOCK → REVIEW(T01 + G01)로 내려갔다. 과잉 경고 개수는 같고 원인이 B03 → G01로 옮겨 갔다 (차단이 검토 요청으로 바뀜).
- 판정이 바뀐 커밋은 이것 하나뿐이다. Predict 34커밋은 변화 없음 (v3.1의 엄격해진 지문 조건으로 새로 BLOCK된 커밋 없음).
- 심은 사례: Predict 19/19, 4주차 6/6.

과소 경고를 이유별로: followup_fix 0/9, untested 0/3, policy 0/3, risky_area 0/5 — Eval #4와 같은 이유로 "경고율이 높아서 쉬운 결과"다.

## 3. 반복 BLOCK 5개는 얼마나 풀렸나 — 1/5 (+ 의도대로 남은 4개)

| 커밋 | v3 | v3.1 | 같은 실패로 못 본 이유 (`comparison_evidence`) |
|---|---|---|---|
| `2e652ab` | BLOCK | **REVIEW (T01)** | — 새 테스트만 추가, 지문 같음 |
| `8c05dc5` | BLOCK | BLOCK | 새 테스트와 함께 **새 헬퍼 함수 `read_sse`** 추가 → "새 테스트만"이 아님 |
| `12b9eb3` | BLOCK | BLOCK | 같은 파일의 헬퍼 `use_fake_llm`·`upload` 변경 |
| `260bafb` | BLOCK | BLOCK | 공유 헬퍼 `tests/fakes.py` 변경, 다른 테스트도 변경 |
| `6c6a32e` | BLOCK | BLOCK | `tests/fakes.py` 변경, import 변경 |

다섯 개 모두 실패 지문은 같았다 (같은 `OpenAIError: Missing credentials`). 남은 4개는 "확인할 수 없으면 낮추지 않는다"는 원칙대로 남은 것이고, 반례 테스트(실패하는 테스트 변경·헬퍼 변경·공유 헬퍼 변경·다른 실패)로 그 동작을 고정했다.

## 4. 다음 선택지 — 관련성까지 볼지

남은 4개를 풀려면 "바뀐 헬퍼가 **실패한 테스트와 관련이 있는가**"를 봐야 한다.

- 방법: 실패한 테스트가 참조하는 이름(본문의 이름 + fixture 인자)에서 출발해 같은 파일의 정의를 따라가고(전이 폐포), `from tests.fakes import ...`처럼 가져온 헬퍼 모듈도 포함. 바뀐 정의가 그 안에 없으면 "관련 없음".
- 효과 예상: `8c05dc5`(새 `read_sse`를 실패한 테스트가 안 씀)는 풀릴 가능성이 높다. 나머지 3개는 실제로 관련 헬퍼(`use_fake_llm`·`FakeClient` 등)를 쓰는지에 달렸다.
- 위험: 동적 fixture(`request.getfixturevalue`), 모듈 수준 부수효과, autouse fixture는 정적 분석으로 못 따라간다 → 그런 게 보이면 "확인 못 함"으로 INCOMPARABLE 유지.
- 추천: **지금은 하지 않는다.** 남은 4개는 모두 BLOCK이지만 결함 자체는 진짜이고(깨끗한 checkout에서 실패), 과잉 경고 원인 중 B03은 이제 1개다. G01 과잉 7개가 더 큰 소음이므로 1.5 branch coverage → 1.4 G01 우선순위가 먼저다.

## 5. 한계

- 같은 사람·같은 시기의 학습용 저장소 24개라 독립성은 제한적이다.
- skip은 아직 판정에 들어가지 않는다 (새 테스트가 전부 skip돼도 SAFE 가능).
- 실행 환경은 깨끗한 스냅샷이지 격리된 환경이 아니다 (호스트 환경 변수가 넘어감).
- followup_fix는 미래 정보를 쓴 사후 라벨이다. `93abf12`는 ReleaseGuard의 BLOCK을 보고 원인을 추적해 라벨을 바꿨다 — 라벨을 결과에 맞춘 것이 아니라 결함·수정 커밋을 확인한 것이지만, 이런 경로로 바뀐 라벨이라는 사실을 남긴다.
