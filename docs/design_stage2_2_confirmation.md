# Stage 2.2 전 독립 확인 평가 — 설계 (평가 기준 고정용 초안)

- 작성: 2026-11-13 · **Claude 초안, 사용자 확인 전** (결정 대기 Q1~Q6는 10장)
- 근거: 외부 리뷰 "Stage 2.1 최종 승인 및 독립 검증 설계"(2026-11-13), [보고서 #14](eval/20261111_eval_report_14.md), [design_stage2_1.md](design_stage2_1.md), [정정 기록](eval/v21/review_corrections.yaml)
- 원칙: 코드는 `spikes/stage2_2_confirmation/` 아래에 둔다. **`releaseguard/` 제품 코드와 판정(SAFE·REVIEW·BLOCK)은 바꾸지 않는다.** 에이전트 API 호출 없음.

## 1. 질문 하나만 검증한다

2.1이 보인 것: 줄·분기 coverage가 공백으로 표시하지 않은 위치에서 mutation으로 테스트 부족을 찾을 수 있다 (Predict, 탐색 집합, confirmed 4건·커밋 3개).

이번에 검증할 것:

> **새로운 코드 변경에서도** mutation이 명세로 정당화되는 테스트 부족을 반복해서 찾고, 그 가치가 실행·사람 검토 비용을 정당화하는가?

- 2.1의 분류 기준(3장)·선택 규칙(커밋당 8개·줄당 1개·연산자 계열)은 **Predict 결과를 보고 정한 것**이다. 이번 평가는 그 규칙을 새 커밋에 그대로 적용해 유효한지 본다. 결과를 보고 바꾸지 않는다.
- KILLED/SURVIVED 비율은 목표가 아니다. 보는 것은 명세로 정당화된 테스트 개선과 그 비용이다.
- 기존 공백 보고서가 표시하지 않았다는 사실은 "**기존 자동 분석 결과 대비 추가 정보**"까지만 말한다. 개발자가 그 문제를 발견할 수 없었다고 주장하지 않는다.

비목표: 통계적 일반화(소규모 확인 평가다), 판정 연동, 새 연산자 개발, SZZ 결함 위치 평가.

## 2. 정보 누출 방지 — 순서와 고정 파일

| 순서 | 작업 | 고정 시점·산출물 |
|---|---|---|
| 1 | 이 프로토콜과 판정 기준 확정 | 이 문서 커밋 (Q1~Q6 반영) |
| 2 | 커밋·파일·줄·연산자 선정 | `eval/mutation_confirmation_cases.yaml` 커밋 — **mutant 실행 전** |
| 3 | 원본 테스트 결과와 줄·분기 상태 기록 | cases 파일에 함께 (ReleaseGuard analyze 결과에서) |
| 4 | Mutation 실행, 전체 결과 보존 | `docs/eval/v22c/mutation_result.json` + 실행 조건 |
| 5 | **모든** SURVIVED의 의미 분류 | `eval/mutation_confirmation_review.yaml` |
| 6 | 명세 근거 확인 → 새 테스트로 차등 검증 | `docs/eval/v22c/test_additions.json`, 테스트 코드 `docs/eval/v22c/tests/` |
| 7 | 8장 기준 적용 | 보고서 #15 |

- 2단계 선정에는 coverage 상태(실행된 줄인지)만 쓰고 mutation 결과는 쓰지 않는다. 2단계 커밋 전에는 어떤 mutant도 실행하지 않는다.
- 실행 뒤 규칙을 고쳐야 하면 `docs/eval/v22c/protocol_changes.yaml`에 따로 남긴다. 고친 기준으로 다시 계산한 값은 **사후 분석**으로만 보고하고, 독립 확인에 성공했다고 표현하지 않는다.
- 단계마다 따로 커밋한다. 커밋 순서가 곧 사전 고정의 증거다.

## 3. 표본

### 3.1 코드베이스 (2026-11-13 확인한 사실)

| 코드베이스 | 저장소 | 소스 Python을 바꾼 커밋 | 전체 테스트 시간 | 비고 |
|---|---|---|---|---|
| **P** Predict_Success | `predict-success/` | 19 (이미 관찰한 6개 제외 → 약 13) | 약 3초 | 2.0·2.1 규칙을 만든 곳 |
| **R** ReleaseGuard | `release-guard/` | 19 | **167초** (194개) | 다른 도메인(도구 자체). 명세 문서가 많다 → 아래 편향 주의 |
| **W** AI Data Analyst 계열 | `2026-10/week1~4` | 2 + 7 + 11 + 1 = 21 | week3·4 약 16초 | 한 프로젝트의 연속 버전 → **코드베이스 1개로 센다** |

- 관찰한 커밋(제외): `fc58c0e` `99309f2` `82e4305` `568ea41` `b67e806` `c7733b3`, 그리고 2.1 평가 B 대조군에 쓴 커밋 전부 (`eval/mutation_cases_2_1.yaml`에서 자동 추출).
- 편향 주의: R은 Claude가 이 세션들에서 만든 코드이고 설계 문서가 촘촘하다. 명세 근거를 찾기 쉬워 ACTIONABLE이 부풀 수 있다. R의 명세 근거는 **그 커밋 시점 이전에 저장소에 있던 문서·docstring·테스트 이름**만 인정한다 (P·W도 같은 규칙).
- W는 week1 `test_app.py`가 `data/` 없음으로 skip된다 (Stage 1.7 기록). 선택 테스트가 전부 skip인 mutant는 `NO_EXECUTED_TEST`로 따로 센다.

### 3.2 선정 규칙 (고정)

| 항목 | 규칙 |
|---|---|
| 커밋 | 관찰하지 않은 커밋 중 소스 Python을 바꾼 커밋, **커밋 시간순**(오래된 것부터) |
| 대상 줄 | 그 커밋에서 바뀌었고 ReleaseGuard analyze가 **covered**로 본 줄 (`not_executable`·줄 공백 제외). 테스트 파일·`spikes/`·`eval/` 제외 |
| 분기 공백 | 분기 공백이 없는 줄을 먼저 고른다. 분기 공백 줄은 같은 커밋에서 예산이 남을 때만 |
| 연산자 계열 | 2.1과 같다: 불리언(`ReplaceAndWithOr` 계열), 비교(`ReplaceComparisonOperator`), 상수(`NumberReplacer`) |
| 계열 균형 | 코드베이스마다 계열별 예산을 같게 (예: 20개면 7·7·6). 한 계열 후보가 모자라면 남은 예산을 다른 계열에 **정해진 순서**(비교 → 불리언 → 상수)로 넘긴다 |
| 상한 | 커밋당 8개, 줄당 1개. 줄 안에서는 Cosmic Ray `dump` 순서의 첫 후보 |
| 규모 | 코드베이스당 약 20개, 전체 40~60개 (Q1에 따라) |
| 배제 | 기준 테스트 실패, 스냅샷·환경 오류, 수집 불가 → mutant를 만들지 않고 **사유를 cases 파일에 기록**. 다음 커밋으로 넘어간다 |
| 무작위성 | 쓰지 않는다. 순서는 위 규칙과 `dump` 순서로 정해진다 |

**SZZ 결함 위치는 쓰지 않는다.** 결함 위치를 고르면 일반 변경에서의 효용이 부풀고, 2.1에서 SZZ 오류도 확인됐다.

## 4. 실행

- 어댑터는 `spikes/stage2_1/mutlib.py`를 그대로 쓴다 (`COLLECTION_ERROR`·`NO_EXECUTED_TEST` 분리, mutant마다 새 스냅샷, 선택 vs 전체 비교). 바꿔야 하면 실행 전 커밋에서 바꾸고 이 문서에 적는다.
- 저장: 원본 JSON 전체, Cosmic Ray·pytest·coverage·Python 버전, 저장소별 HEAD, 실행 시각, 테스트 명령. 홈·임시 경로·계정 이름은 2.0과 같이 가린다.
- **선택 실행 vs 전체 실행**: Q2에 따른다. R은 전체가 167초라 모든 mutant에 전체를 돌리면 R 20개에 약 1시간이다.

## 5. 분류 기준 — 2.1 그대로 + 2.1 검토에서 확정된 두 가지

2.1 3장의 분류(`ACTIONABLE_GAP` · `MEANINGFUL_UNVERIFIED` · `LOW_VALUE` · `EQUIVALENT_SUPPORTED` · `UNRESOLVED`)와 `ACTIONABLE_GAP` 세 조건(명세 근거 · 차등 테스트 · assertion 기반)을 바꾸지 않는다. 2.1 리뷰에서 확정된 두 규칙은 결과를 보기 전인 지금 넣는다.

1. **오라클 부적격 (`KNOWN_BUG_ORACLE`)**: 원본 동작이 이후 이력에서 결함으로 고쳐졌으면, 그 mutant를 죽이는 테스트는 ACTIONABLE 검증 대상에서 뺀다. 분류는 `MEANINGFUL_UNVERIFIED`에 표시를 단다. 확인 방법: 대상 줄·함수를 이후 커밋에서 바꾼 수정 커밋 메시지·diff를 본다 (`git log -L` 범위).
2. **동등성 범위 표시**: `EQUIVALENT_SUPPORTED`에는 근거를 세 칸으로 적는다 — 코드로 보장 / 데이터로 관측 / 아직 미보장. 일반적인 의미의 equivalent mutant로 확정하지 않는다.
3. **의미 있는 차이 ≠ 우선순위** (2.1 T5): 계약 안의 변화면 `ACTIONABLE_GAP`이고, 실무 우선순위는 `review_priority`로 따로 적는다.
4. **명세 시점**: 명세 근거는 대상 커밋 시점 이전에 저장소에 있던 것만 인정한다. 근거를 지금 새로 쓰는 것은 인정하지 않는다 (2.1 #23의 provisional과 같은 처리).

분류자: Claude 초안 → 사용자 확인. 다만 사람 검토 비용을 재기 위해 **일부는 사용자가 먼저 분류한다** (Q4).

## 6. 테스트로 차등 검증

2.1은 커밋마다 1개만 테스트했다. 그러면 유용할 가능성이 높은 사례만 골라 성공률이 부풀 수 있다. 이번에는:

- **모든 SURVIVED가 검토 대상이다.** 분류 없이 남기는 SURVIVED는 없다.
- `MEANINGFUL_UNVERIFIED` 중 명세 근거가 있는 것은 **전부** 테스트를 시도한다 (Q3의 상한까지, 넘으면 mutant 번호 순).
- 시도한 것은 실패까지 모두 보고한다. 시도하지 않은 것은 실패로도 성공으로도 세지 않는다.
- 절차·결과 해석 표·보관 위치는 2.1 6장과 같다 (대상 저장소에는 넣지 않음).

## 7. 지표

| 지표 | 정의 |
|---|---|
| **Actionable Yield** | confirmed `ACTIONABLE_GAP` / 전체 SURVIVED. **세 값을 함께**: confirmed, provisional, 미검증(`MEANINGFUL_UNVERIFIED` 중 시도 안 함). 분모를 "테스트를 시도한 SURVIVED"로 한 값도 |
| **Incremental Value** | confirmed `ACTIONABLE_GAP` 중 기존 보고서에서 줄 공백도 분기 공백도 아니었던 수. 위치마다 기존 표시(`covered` / `not_executable` / `branch_gap` / `fixture_only`)를 기록 |
| **Oracle Validity** | `KNOWN_BUG_ORACLE`로 뺀 수와, 확인 방법을 적용한 SURVIVED 수 (모든 ACTIONABLE 후보에 이력 확인을 했는가) |
| **Review Effort** | 사용자가 직접 분류한 SURVIVED당 실제 분(사용자 기록). Claude 초안의 읽은 파일 수는 참고로만 |
| **Execution Overhead** | 커밋당 mutation 추가 시간(선택 실행 합), mutant당 선택·전체 실행 시간 중앙값. 기준 analyze 시간 대비 배수 |
| **Operator Value** | 계열별 mutant·SURVIVED·confirmed ACTIONABLE·LOW/EQUIVALENT 수 |
| **Selection Fidelity** | 선택 실행과 전체 실행의 상태·실패 종류·실패 id 완전 일치 비율 (전체를 돌린 mutant만) |

모든 지표를 **코드베이스별로** 나눠 보고하고, 합계는 그 뒤에 둔다.

## 8. Go / Hold / No-Go (고정)

| 결정 | 기준 |
|---|---|
| **GO** — 2.2 정식 통합 | confirmed `ACTIONABLE_GAP`이 **P를 뺀 독립 코드베이스 2곳(R·W) 각각에서 1건 이상**, 전체로는 **서로 다른 커밋 2건 이상**, 그중 Incremental Value 1건 이상. 그리고 비용 상한(Q5) 안 |
| **HOLD** — 제한적 기능만 | ACTIONABLE은 있지만 한 코드베이스에만 몰려 있거나(P만 포함), 비용 상한을 넘거나, 미검증이 많아 판단 근거가 부족 |
| **NO-GO** — 2b로 | confirmed ACTIONABLE이 없거나, 검토 비용이 상한을 크게 넘어 실용성이 없음 |

- P의 결과는 보고하지만 GO의 재현 조건에는 넣지 않는다 (규칙을 만든 코드베이스라서). Q1에서 P를 빼면 이 줄은 지운다.
- 결과가 GO여도 mutation 결과를 판정(SAFE·REVIEW·BLOCK)에 반영하지 않는다.

## 9. GO일 때 Stage 2.2 구현 범위 (미리 제한)

| 항목 | 내용 |
|---|---|
| 실행 | 명시적 옵션으로만 (예: `--mutation`), 기본 꺼짐 |
| 대상 | 바뀌었고 실행된 Python 줄 |
| 결과 | KILLED / SURVIVED / 실행 불가(`COLLECTION_ERROR`·`NO_EXECUTED_TEST`·`TIMEOUT`·`INVALID`) |
| 근거 | 변형 위치·연산자·원본/변형 소스·실패한 테스트 id |
| 보고서 | 줄·분기 결과와 **별도 절** (`mutation_result`) |
| 상한 | 사용자 지정 mutant 수·시간 |
| 판정 | 변경 없음 |
| 에이전트 | 필수 아님 |

목표는 mutation 엔진을 풍부하게 만드는 것이 아니라, 테스트가 감지하지 못한 동작 변화를 개발자가 검토할 수 있는 근거로 주는 것이다.

## 10. 결정 대기 (사용자)

| # | 질문 | 선택지 | 추천 |
|---|---|---|---|
| Q1 | 코드베이스 구성 | (a) **R + W 각 약 20개 + P 신규 커밋 약 15개 (P는 GO 재현 조건에서 제외)** (b) R + W만 각 약 25개 (c) P + R + W 동등 | **(a)**. P의 새 커밋으로 "같은 코드베이스의 새 커밋에서도 반복되나"를 따로 보고, 독립 재현은 R·W로만 판단한다 |
| Q2 | 전체 실행 범위 (Selection Fidelity·비용) | (a) **모든 mutant에 선택 + 전체** (R 약 1시간, 백그라운드) (b) R은 SURVIVED 전부 + KILLED 중 mutant 번호 순 1/3만 전체 | **(a)**. 일치율을 표본 없이 재고, 실제 비용 숫자가 나온다. 한 번만 돌리면 된다 |
| Q3 | 테스트 시도 상한 | (a) **명세 근거가 있는 `MEANINGFUL_UNVERIFIED` 전부, 최대 15개** (b) 커밋당 1개 (2.1과 같음) | **(a)**. 2.1의 선택 편향을 줄이는 것이 이번 평가의 핵심이다 |
| Q4 | 사람 검토 시간 측정 | (a) **사용자가 SURVIVED 중 정해진 6개(코드베이스별 mutant 번호 앞에서부터 2개씩)를 Claude 초안을 보기 전에 직접 분류하고 분을 기록** → 시간 + Claude 초안과의 일치도 (b) 사용자가 Claude 초안을 확인하는 시간만 기록 (c) 재지 않고 읽은 파일 수로 대신 | **(a)**. 실제 제품에서는 개발자가 초안 없이 SURVIVED를 읽는다. (b)는 사람 비용을 낮게 잰다 |
| Q5 | GO 비용 상한 | (a) **커밋당 선택 실행 추가 시간 중앙값 ≤ 5분(8 mutant 기준), 사람 검토 SURVIVED당 중앙값 ≤ 5분** (b) 상한 없이 숫자만 보고 | **(a)**. "감당 가능"을 결과 보기 전에 숫자로 정해 둔다 |
| Q6 | 시간순 선택의 방향 | (a) **오래된 커밋부터** (b) 최신 커밋부터 | **(a)**. 2.0과 같은 규칙이라 규칙 자체를 바꾸지 않는다. R의 초기 커밋은 단순하다는 편향이 있지만 W·P와 같은 조건이다 |

## 11. 산출물

```text
release-guard/
├── docs/design_stage2_2_confirmation.md      ← 이 문서 (1단계 고정)
├── eval/mutation_confirmation_cases.yaml      ← 2·3단계, mutant 실행 전 커밋
├── eval/mutation_confirmation_review.yaml     ← 5·6단계, 실행 뒤 분류·명세 근거
├── docs/eval/v22c/                           ← 원본 JSON, 실행 조건, test_additions, tests/, protocol_changes
├── docs/eval/202611xx_eval_report_15.md
└── spikes/stage2_2_confirmation/              ← 선정·실행 스크립트 (mutlib 재사용)
```
