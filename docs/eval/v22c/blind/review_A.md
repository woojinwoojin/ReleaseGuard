# ReleaseGuard Stage 2.2 — A 블라인드 독립 분류

- 평가 시점: 2026-11-17
- 평가자: ChatGPT (AI 독립 리뷰; 사람 평가자가 아님)
- 사용한 자료: `packets.md`, `selection.json`의 5개 선정 사례만. Claude 분류 초안, `mutation_confirmation_review.yaml`, B 사용자 기록은 열람하지 않음.
- 블라인드 범위: **다른 평가자의 이번 사례 분류에는 블라인드**. 기존 프로젝트와 mutation 기획에 대한 사전 지식이 없는 평가는 아님.
- 중요 제한: 대상 Git 커밋의 문서 원문, 저장소 자체의 차등 테스트 실행 기록은 제공되지 않았음. 패킷에 수록된 원본 코드와 문서 발췌만으로 판단. 코드를 부분적으로 재현한 실험은 정식 대상 저장소의 테스트 추가와 구분함.

## 독립 분류 (A 확정 기록)

| 사례 | 분류 | 확신도 | 근거 | 미확인 사항 |
|---|---|---|---|---|
| R-1 | `LOW_VALUE` | 높음 | `json.dumps(..., indent=2)` → `indent=3`은 출력 JSON의 공백·바이트를 변경하지만 파싱 결과의 데이터는 동일. 패킷의 당시 docstring에는 공백 들여쓰기 계약이 없음. | 당시 README·설계 문서에 바이트/포맷 호환 계약이 있는지는 확인하지 못함. 그 경우 재분류 필요. |
| R-2 | **`ACTIONABLE_GAP` 후보 (미확정)** | 중간~높음 | `len(text) == MAX_DIFF_CHARS`에서는 원본 `truncated=False`, mutant `True`. `text[:MAX_DIFF_CHARS]`는 이때 글자를 잃지 않으므로 `truncated`가 실제 잘림 여부를 뜻한다면 mutant는 잘못된 상태를 표시함. | 필드의 명세 및 경계 테스트를 당시 코드/문서로 독립 확인해야 하고, 대상 저장소에서 원본 PASS·mutant assertion FAIL 테스트를 실행해야 confirmed 가능. |
| W-1 | **`ACTIONABLE_GAP` 후보 (미확정)** | 높음 | `parent`가 1행이면 원본 `iloc[0]`는 유효하지만 mutant `iloc[1]`은 `IndexError`. 함수 docstring은 없는 카테고리에 오류 dict를 반환한다고 설명하며, 모듈 docstring은 잘못된 인자를 예외가 아닌 오류 dict로 돌려준다고 명시함. 단일 부모 매칭은 코드에서 배제되지 않음. | 대상 커밋에서 정확한 회귀 테스트를 추가하고 원본 PASS·mutant assertion FAIL을 확인해야 confirmed. |
| P-1 | `LOW_VALUE` | 중간 | `candidate/reference` 경로의 보류 사유 메모 표시를 60→61자로 확대. 내부 `calc_status`·`score_eligible` 계산 로직은 이 변형으로 달라지지 않음. 패킷의 당시 발췌는 60자 표시 계약을 보이지 않음. | 당시 README·decisions에 문자열 길이·표시 정책이 있을 경우 재분류. |
| P-2 | `LOW_VALUE` | 중간 | `not_computed` 경로의 보류 사유 메모 표시를 60→61자로 확대. P-1과 같은 출력 형식 변경이며, 명시된 계산 상태 규칙은 유지. P-1과 동일 커밋·함수이므로 독립적 가치 사례로 중복 집계하지 않아야 함. | 당시 문서에 60자 제한 계약이 있으면 재분류. |

### 분류 근거 상세

**R-1** — JSON 파싱값은 유지되고 사람 눈에 보이는 들여쓰기만 달라진다. `LOW_VALUE`는 "동등"과 다르다. 출력 바이트는 달라지므로 `EQUIVALENT_SUPPORTED`로 보지 않았다.

**R-2** — 원본과 mutant의 `truncated`는 입력 길이가 **정확히 제한값**일 때만 다르다. `truncated`가 "원본 텍스트가 잘렸다"는 뜻인 것은 필드명과 구현으로 강하게 추론되지만, 커밋 시점의 공식 명세 원문이 없으므로 **후보**로만 분류한다.

**W-1** — 아래 입력은 함수의 코드 경로상 허용되는 단일 부모 매칭 상황이다. 판다스 2.2.3에서 `parent.iloc[0]`는 '식품', `parent.iloc[1]`은 `IndexError`로 확인했다. 이는 격리된 최소 코드 실험이며 대상 Git 커밋에서 작성·실행한 회귀 테스트는 **아니다**.

```python
import pandas as pd

df = pd.DataFrame({
    "category": ["식품", "가구"],
    "sub_category": ["과일", "책상"],
})
category = "과일"  # category 컬럼에는 없고 sub_category에만 있음
parent = df.loc[df["sub_category"] == category, "category"]
assert parent.tolist() == ["식품"]
assert parent.iloc[0] == "식품"  # 원본 경로
# parent.iloc[1] -> IndexError: single positional indexer is out-of-bounds
```

**P-1 / P-2** — 메모 내용의 61번째 문자까지 포함될 수 있으므로 동작 차이는 있다. 다만 패킷에 제시된 기간·후보값·보류 명세는 문자열 자르기 길이를 규정하지 않는다. 계약의 증거 없이 `ACTIONABLE`로 높이지 않는다.

## 블라인드 검토 결과 요약

- 총 5개: `ACTIONABLE_GAP` **후보 2건**(R-2, W-1), `LOW_VALUE` 3건(R-1, P-1, P-2).
- **Confirmed ACTIONABLE 0건**: 정식 대상 저장소에서 명세 확인과 차등 테스트 추가를 수행하지 않았기 때문. 후보 수를 confirmed 수로 계산하지 않는다.
- R/W의 각 1건 후보는 독립 코드베이스 재현 조건을 만족할 **가능성**이 있지만, 이를 이미 입증했다고 주장하지 않는다.
- AI 검토에 걸린 실제 사람의 시간은 **측정하지 않았고, AI 검토 시간은 사람 비용의 대용값이 아니다**.
- A 결과는 다른 평가자의 초안을 보지 않고 기록한 독립 의견이지만, 사람 검토 B는 대체하지 않는다.

## 다음 검증에 필요한 최소 조건

1. R-2 당시 명세에 `truncated` 계약이 있는지 확인하고 `len(text)==MAX_DIFF_CHARS`로 원본 PASS / mutant FAIL assertion 테스트.
2. W-1 당시 명세에 오류 dict 보장이 있는지 확인하고 부모 매칭이 정확히 1행인 입력으로 원본 PASS / mutant FAIL assertion 테스트.
3. 실제 기존 10개 SURVIVED 전수분류, 원본/변형 실행 비용, 이후 수정 이력 오라클 검사를 별도로 평가. 이 문서의 5개 표본만으로 전체 2.2 효용 판정을 내리지 않는다.
