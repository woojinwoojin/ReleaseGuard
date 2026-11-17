# Stage 2.2 확인 평가 — 블라인드 A와 Claude 1차 분류 비교

- A 결과는 `review_A.md`에 받은 그대로 저장했다(`01869a3`). Claude 1차 분류(`eval/mutation_confirmation_review.yaml`, `e8643ef`)는 A 결과를 받기 전에 커밋했다.
- 사례와 mutant 번호 대응(`selection.json`): R-1=#6, R-2=#16, W-1=#23, P-1=#42, P-2=#44. 설계상 패킷은 6개지만 W에 SURVIVED가 1개뿐이어서 5개다.

| 사례 | A | Claude 1차 | 라벨 일치 | 의미 있음/없음 일치 |
|---|---|---|---|---|
| R-1 (#6) | LOW_VALUE (확신도 높음) | LOW_VALUE (명세 없음) | 일치 | 일치 |
| R-2 (#16) | ACTIONABLE_GAP 후보 (확신도 중간~높음) | MEANINGFUL_UNVERIFIED (명세 weak, 우선순위 LOW) | 불일치 | 일치 |
| W-1 (#23) | ACTIONABLE_GAP 후보 (확신도 높음) | MEANINGFUL_UNVERIFIED (명세 strong, 우선순위 LOW) | 불일치 | 일치 |
| P-1 (#42) | LOW_VALUE (확신도 중간) | LOW_VALUE | 일치 | 일치 |
| P-2 (#44) | LOW_VALUE (확신도 중간, P-1과 중복 집계하지 말 것) | LOW_VALUE (#42와 같음) | 일치 | 일치 |

**Blind Agreement: 라벨 기준 3/5, 의미 있음(ACTIONABLE 후보·MEANINGFUL)과 의미 없음(LOW·EQUIVALENT) 구분 기준 5/5.**

## 불일치의 성격

- 두 불일치는 모두 "명세상 의미 있는 차이"를 어느 라벨로 적느냐의 차이다. 패킷의 라벨 설명이 `ACTIONABLE_GAP 후보(명세상 의미 있는 차이)`와 `MEANINGFUL_UNVERIFIED`를 구분하는 기준을 주지 않았다. A는 명세상 차이가 있으면 후보로 적었고, Claude는 테스트로 확인하기 전이면 MEANINGFUL_UNVERIFIED로 적었다. 판단 내용(어떤 입력에서 동작이 달라지는지, 명세 근거가 무엇인지)은 두 사례 모두 같다.
- 명세 강도는 갈린다. R-2는 A가 "필드명과 구현으로 강하게 추론"했고 Claude는 weak(필드 이름과 같은 파일의 다른 두 도구의 일관성뿐)로 봤다. W-1은 둘 다 모듈 docstring의 오류 dict 계약을 근거로 들었다.
- 이 비교는 라벨 설명의 모호함 때문에 일치율이 낮게 나온 부분이 있다. 다음 블라인드 평가에서는 패킷에 두 라벨의 구분 기준을 적어야 한다.

## A 문서 중 사실과 다른 부분 (A 원문은 고치지 않음)

- `review_A_interim_decision.md`의 "남은 SURVIVED 5개 분류 미완료": Claude 1차 분류는 SURVIVED 10개 전부를 했다(`e8643ef`). 블라인드 검토를 받지 않은 것은 맞다(#1·#2·#3·#4·#55).
- `review_A_interim_decision.md`의 비용 범위(R 23~35초 등)는 A가 사용자에게서 들은 값이다. `mutation_result.json`과 대조하는 작업은 8단계에서 한다.
- `review_A_proposed_B_status.md`는 A가 제안한 B 상태 문서다. 사용자 기록이 아니다. B 상태는 사용자 확인 뒤 따로 기록한다.

## 7단계로 넘길 것

- A가 제안한 R-2·W-1 테스트는 Claude 1차 `test_targets`(#1·#2·#3·#16·#23)에 이미 들어 있다. A의 W-1 pandas 재현은 대상 커밋에서 실행한 테스트가 아니므로 confirmed로 세지 않는다.
