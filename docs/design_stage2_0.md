# Stage 2.0 Mutation Feasibility Spike — 설계안

- 작성: 2026-11-11 · **Claude 초안, 사용자 확인 전**
- 근거: [보고서 #11](eval/20261111_eval_report_11.md) 6장, [#12](eval/20261111_eval_report_12.md), 외부 리뷰 (2026-11-11 Stage 1.7 종료 승인)
- 성격: **제품 기능이 아니라 독립 실험**이다.
  - 판정 변경 없음, 에이전트 API 호출 없음.
  - 코드는 `releaseguard/` 패키지 밖(`spikes/stage2_0/`)에 둔다.

## 1. 목적

mutation testing을 ReleaseGuard의 실행 구조(스냅샷 실행, coverage, `nodeid_map`)에 붙일 수 있는지만 확인한다.
mutation이 쓸모 있는지(가치)는 2.1에서 본다.

**성공의 정의**: mutant를 실행했다는 사실이 아니다. 2.1에서 가치를 평가할 수 있을 만큼 결과를 **수집하고 해석할 수 있는지**를 입증하는 것이다.

### 답할 질문 (외부 리뷰)

| # | 질문 | 2.0에서 보는 것 |
|---|---|---|
| 1 | 기존 테스트 실행 환경을 재사용할 수 있는가 | 대상 `.venv` + `git archive` 스냅샷에서 도구가 그대로 도는지 |
| 2 | 특정 변경 줄에만 mutant를 만들 수 있는가 | 만들어진 mutant가 모두 지정한 줄에 있는지 |
| 3 | 기존 저장소를 안전하게 보존하는가 | 실행 전후 대상 저장소의 `git status`·HEAD가 같은지 |
| 4 | 관련 테스트만 돌린 결과가 전체 실행과 같은가 | mutant마다 두 방식으로 실행해 결과 일치율을 잰다 |
| 5 | KILLED·SURVIVED를 해석할 수 있는가 | 실패 종류(assertion·수집 오류·환경)를 구분해 기록할 수 있는지. 가치 판단은 2.1 |
| 6 | 시간·환경 비용을 감당할 수 있는가 | mutant당 시간, 설치·설정 비용 |

## 2. 도구 — 확인한 사실

2026-11-11, Windows 11 + Python 3.13 임시 venv에서 직접 확인했다.

| 도구 | 버전 | 결과 |
|---|---|---|
| mutmut | 3.8.1 | 실행 거부: "To run mutmut on Windows, please use the WSL". WSL(Ubuntu)은 이 PC에 있지만, 대상 `.venv`가 Windows용이라 Linux 환경을 따로 만들어야 한다 |
| Cosmic Ray | 8.9.0 | 설치·실행됨 |

Cosmic Ray에는 2.0에 필요한 기능이 있다.
- `mutate-and-test MODULE OPERATOR OCCURRENCE TEST_COMMAND`: mutant 하나에 원하는 테스트 명령을 붙여 돌린다. 그래서 관련 테스트만 돌리는 방식과 전체 실행을 같은 mutant로 비교할 수 있다.
- `cr-filter-lines`, `cr-filter-git`: 지정한 줄·바뀐 줄 밖의 mutation을 건너뛴다.
- 연산자 목록: `core/ReplaceBinaryOperator_*`, 비교·불리언·상수 계열 등. `cosmic-ray operators`로 확인했다.

이 기능들이 실제로 의도대로 동작하는지는 아직 확인하지 않았다. 그것이 2.0의 1단계다.

## 3. 실험 설계 (초안)

| 항목 | 범위 |
|---|---|
| 대상 저장소 | Predict_Success 1개. 전체 테스트가 약 3초로 빠르고, 34커밋·SZZ 자료가 있어 2.1로 이어진다 |
| 대상 줄 | **바뀌었고 테스트가 실행한 줄**(covered)만. 공백 줄은 이미 G01이 설명한다 |
| 커밋 선택 | 결과를 보기 전에 규칙으로 정해 기록한다. 예: covered 바뀐 줄이 있는 커밋을 시간순으로 3~5개 |
| mutant 수 | 20~40개 (상한 40) |
| 연산자 | 비교(`<`↔`<=`, `==`↔`!=`), 불리언(`and`↔`or`, `not` 제거), 상수(숫자 ±1, `True`↔`False`). 이항 산술은 필요하면 소수만 |
| 실행 | mutant마다 (a) 그 줄을 실행한 테스트만(`nodeid_map`의 원본 node id) (b) 전체 테스트 |
| 위치 | `git archive` 스냅샷 복사본에서만 실행. 대상 저장소는 실행 전후 상태를 비교해 확인한다 |
| 결과 | `mutation_result` JSON을 따로 저장 (`out/spike/2_0/`). 판정·findings·보고서에 넣지 않는다 |

결과 분류 (내부):

| 상태 | 뜻 |
|---|---|
| KILLED | 테스트가 실패함. 실패 종류를 따로 기록: assertion / 예외 / 수집 오류 |
| SURVIVED | 관련 테스트가 모두 통과함 |
| INVALID | mutant 코드 자체가 유효하지 않음 (import·구문 오류 등) |
| TIMEOUT | 시간 상한 안에 끝나지 않음 |
| INCOMPARABLE | 기준 실행(mutant 없음)이 실패해서 비교할 수 없음 |
| NO_RELEVANT_TEST | 그 줄을 실행한 테스트가 없음 (covered 줄만 고르므로 0이어야 함 — 0이 아니면 도구와 coverage가 어긋난다는 신호) |

SURVIVED를 결함이나 경고로 해석하지 않는다. 동등 mutant(동작이 바뀌지 않는 변형)가 있을 수 있기 때문이다.

## 4. 단계

1. **도구 확인** (mutant 몇 개): Cosmic Ray가 스냅샷 + 대상 `.venv`에서 돌고, 줄 필터가 지정한 줄만 남기며, `mutate-and-test`의 결과를 읽을 수 있는지.
2. **어댑터**: `spikes/stage2_0/`의 스크립트로 연결한다. ReleaseGuard `analyze` 결과(covered 줄·`nodeid_map`) → 대상 줄 목록 → Cosmic Ray 세션 → mutant별 (a)·(b) 실행 → `mutation_result` JSON.
3. **실행**: 20~40개 mutant.
4. **보고서 #13**: 질문 1~6에 답하고, 2.1로 갈지(Go / Hold / No-Go) 판단한다.

## 5. 완료 기준 (사전 고정)

| 질문 | 기준 |
|---|---|
| 1 환경 재사용 | Windows 네이티브 + 대상 `.venv`로 실행됨, 또는 안 되는 이유가 기록됨 |
| 2 줄 지정 | 만들어진 mutant가 100% 지정한 줄 안에 있음 |
| 3 저장소 보존 | 대상 저장소의 `git status`·HEAD 변화 0 |
| 4 테스트 선택 | 관련 테스트만 vs 전체의 결과 일치율과 불일치 사례를 모두 기록 (일치율 목표값은 두지 않고 관찰만) |
| 5 해석 가능성 | 모든 mutant가 위 6개 상태 중 하나로 분류되고, KILLED의 실패 종류가 기록됨 |
| 6 비용 | mutant당 시간(선택·전체 각각), 설치·설정 단계 수 |
| 불변 | 58커밋 판정 변화 0 (spike 코드는 제품 경로에 없음), API 0 |

**2.1로 가는 조건**:
- 질문 1~3이 충족되고, 4·5의 결과를 해석할 수 있으면 → Go (2.1)
- 도구 문제는 남지만 우회 방법이 보이면 → Hold
- 줄 지정이나 저장소 보존이 불가능하거나, 비용이 감당할 수 없으면 → No-Go (2b로)

## 6. 결정이 필요한 것 (추천 포함)

| # | 질문 | 선택지 | 추천 |
|---|---|---|---|
| Q1 | 도구 | (a) **Cosmic Ray만** (b) Cosmic Ray + WSL의 mutmut 비교 (c) 직접 만든 최소 변형기 | **(a)**. Windows에서 바로 돌고 mutant별 테스트 명령을 받는다. (b)는 Linux용 대상 환경을 따로 만들어야 해서 "기존 실행 환경 재사용"(질문 1)과 어긋난다. (c)는 리뷰 권고(엔진을 만들지 말고 어댑터로)와 어긋난다. Cosmic Ray가 1단계에서 실패할 때만 (b)·(c)를 다시 본다 |
| Q2 | 대상 저장소 | (a) **Predict_Success** (b) week3 | **(a)**. 테스트가 빠르고(3초) SZZ 자료가 있다. week3는 테스트 33~55초와 `data/` skip 문제가 있다 |
| Q3 | 커밋 선택 규칙 | (a) **covered 바뀐 줄이 있는 커밋을 시간순으로 앞에서부터, mutant 40개가 찰 때까지** (b) SZZ 결함 줄이 있는 커밋 위주 | **(a)**. 2.0은 가능성 확인이라 결함 줄을 고르면 2.1의 가치 평가와 섞인다. SZZ는 2.1에서 쓴다 |
| Q4 | 연산자 범위 | (a) **비교·불리언·상수만** (b) 이항 산술 포함 | **(a)**. 리뷰 권고와 같다. mutant 수를 40 안에 맞추기 쉽다 |
| Q5 | spike 코드 위치 | (a) **`spikes/stage2_0/` (커밋함, 제품 경로 밖)** (b) scratchpad (커밋 안 함) | **(a)**. 결과를 재현할 수 있어야 한다. `releaseguard/`는 import하기만 하고 바꾸지 않는다 |
