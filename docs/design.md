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
| R02 | REVIEW REQUIRED | 소스 수정, 관련 테스트를 찾지 못함 |
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
