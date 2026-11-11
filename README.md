# ReleaseGuard

머지하기 전에 바뀐 코드 중 **어떤 테스트도 실행하지 않는 곳(검증 공백)**을 찾고, 테스트를 **실제로 돌린 뒤** SAFE / REVIEW REQUIRED / BLOCK으로 알려주는 로컬 CLI.

코드가 맞는지는 판단하지 않는다. **무엇이 검증됐고 무엇이 검증되지 않았는지**를 근거와 함께 보여준다. 판정은 규칙으로만 하고, LLM은 공백을 설명할 때만 쓴다(선택).

**상태 (2026-11-11)**: Stage 1 기술 MVP 완료 ([종료 심사 #11](docs/eval/20261111_eval_report_11.md)) · 버전 0.2.0 · 판정 규칙 v3.1 · 테스트 149개 통과

**1차 결과물은 검증 공백 보고서다.** SAFE / REVIEW REQUIRED / BLOCK은 검증 부족을 놓치지 않도록 만든 보수적 게이트이고, 코드 변경 커밋에서 검토가 필요한 것과 아닌 것을 잘 구분한다는 근거는 아직 없다 (아래 과잉 경고).

## 문서

| 문서 | 내용 |
|---|---|
| [docs/usage.md](docs/usage.md) | **사용법** — 설치, `analyze`, 보고서 읽는 법, 평가 명령 |
| [docs/eval/reports_summary.md](docs/eval/reports_summary.md) | **평가 보고서 #1~#11 정리** |
| [docs/status_roadmap.md](docs/status_roadmap.md) | 현재 상태, 한계, 로드맵 |
| [docs/problem.md](docs/problem.md) · [docs/design.md](docs/design.md) · [docs/proposal.md](docs/proposal.md) | 문제 정의 · 설계 · 제안서 |
| [docs/samples/report_142912b.md](docs/samples/report_142912b.md) | 보고서 샘플 |

## 빠른 시작

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt

# 규칙만 (API 호출 없음). 대상 저장소의 .venv(Python 3.13)로 테스트를 돌린다
.\.venv\Scripts\python -m releaseguard analyze --repo ..\predict-success --base HEAD~1 --head HEAD --no-agent

.\.venv\Scripts\python -m pytest
```

결과는 `out/<날짜>_<SHA>.{json,md}`에 저장된다. 공백 설명 에이전트를 쓰려면 `--no-agent`를 빼고 `.env`에 `OPENAI_API_KEY`를 넣는다 (`.env.example` 참고).

## 판정

| 판정 | 언제 |
|---|---|
| **BLOCK** | 비밀값(B01), 원래부터 실패했다고 확인되지 않은 테스트 실패(B03), 수집 오류(B04) |
| **REVIEW REQUIRED** | 검증 공백(G01), 원래 깨진 테스트(T01), 불안정한 테스트(T02), 의존성 변경(R04), 테스트를 못 돌림(E01), 검증 범위 밖 변경(E02), 스냅샷 예외(E03) |
| **SAFE** | ReleaseGuard의 검증 절차에서 검토 사유를 찾지 못함 — **코드가 맞다는 보증이 아님** |

판정과 따로 검증 범위(COMPLETE / PARTIAL / UNSUPPORTED)를 기록한다. 분기 공백, 공백 그룹 순서, skip 목록, 테스트 제안 검사(S01~S03)는 참고로만 표시하고 판정에는 넣지 않는다.

## 지금까지 확인된 것

| 지표 | 값 |
|---|---|
| 결함을 심은 사례 | Predict_Success 19/19, 4주차 6/6 |
| 반복 실행 결정성 | 판정 15/15, 공백 순서 39/39 |
| 과소 / 과잉 경고 (라벨 39개) | 0/20 / 11/19 |
| 과잉 경고 (코드 변경만) | **11/12** — 코드 변경 41개 중 SAFE는 1개 |
| SZZ: 나중에 고쳐진 결함 줄이 들어올 때 공백이었던 비율 | 59% (41%는 실행됐는데도 결함) |
| 공백 설명 에이전트 | 설명 31/32, 실행 가능성 22/32, Gap Closure 4/4, 16회 추정 $0.24 |

- 깨끗한 checkout에서만 실패하는 진짜 결함을 사람보다 먼저 찾았다 (week3 `93abf12`, 4주차 `e3867fd`에서 사람이 고침).
- 처음 설계(v1, 에이전트가 위험을 추론)는 결함을 0/6 짚었다. 그래서 테스트를 실행해 검증 공백을 찾는 v2로 다시 설계했다. 과정은 [보고서 정리](docs/eval/reports_summary.md)에 있다.

## 한계

- "실행됐다"가 "확인됐다"는 뜻은 아니다. assert가 얼마나 강하게 확인하는지는 보지 않는다.
- 과잉 경고가 많다 (G01은 공백 크기와 관계없이 REVIEW).
- 테스트만 바뀐 경우 일부가 SAFE로 나온다: 새 테스트 수집 0개, 전부 skip, 테스트 전부 삭제 (Stage 1.7에서 보완).
- Docker·CI·설정·데이터 변경은 검증하지 않고 E02로 표시만 한다.
- Python + pytest만 지원한다.
- **대상 저장소의 테스트 코드를 그대로 실행한다 (샌드박스 없음).** 신뢰하는 저장소에만 쓴다.

전체 목록: [status_roadmap.md 7장](docs/status_roadmap.md#7-알려진-한계)

## 다음 단계

1. **1.7 Reliability Gate**: T03(바뀐 테스트가 실행되지 않음), coverage 실제 버전 확인, 원본 node id 보존
2. **2.0 Mutation spike**: 도구 호환성·비용 확인
3. **2.1 Value Eval**: coverage 대비 추가 가치 측정
4. **2.2 조건부 통합**: 2.1에서 효과가 확인될 때만
5. **2b 배포 산출물 검증**: 컨테이너 시작 확인, CI 필수 단계 정책

판정 구분력(Decision Utility)은 별도 측정 과제로 추적한다. 각 단계는 앞 단계의 평가에서 근거가 확인될 때만 시작한다. 자세한 내용: [status_roadmap.md 8장](docs/status_roadmap.md#8-로드맵)
