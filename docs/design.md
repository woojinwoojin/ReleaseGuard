# 설계 v2 (Stage 1 MVP)

작성: 2026-11-03 · 문제 정의: `docs/problem.md` (v2) · v1 설계는 이 문서의 git 기록 참고

## 실행

```
python -m releaseguard analyze --repo ../predict-success --base HEAD~1 --head HEAD [--python <경로>] [--no-agent]
→ out/<YYYYMMDD>_<head 7자리>.json  (판정 + 근거)
→ out/<YYYYMMDD>_<head 7자리>.md    (보고서)

python -m releaseguard eval  [--cases eval/cases.yaml] [--repeat N] [--agent]   # 커밋 전체
python -m releaseguard seeds [--seeds eval/seeds_predict_success.yaml]           # 결함을 심은 사례
python -m releaseguard szz   [--cases eval/cases.yaml]                           # 결함 줄 추적
```

`base...head` 비교는 `git merge-base base head`에서 head까지의 변경이다 (PR diff와 같은 기준).

## 처리 흐름

| 단계 | 하는 일 | 방식 | 모듈 |
|---|---|---|---|
| 1. Collect | 변경 파일, 추가·수정된 줄 | git (읽기 전용) | `git_ops.py` |
| 2. Classify | 파일 분류, 비밀값 패턴 | 규칙 (`configs/rules.yaml`) | `classify.py` |
| 3. Run | head를 임시 폴더에 풀고 pytest + coverage 실행, 테스트별로 실행한 줄 기록. 실패한 테스트는 base에서 다시 실행 | 실행 (결정적) | `runner.py` |
| 4. Gaps | 바뀐 실행 가능 줄 중 어떤 테스트도 실행하지 않은 줄 = 검증 공백 | 결정적 | `gaps.py` |
| 5. Decide | 판정 규칙 v2 | 규칙 | `decide.py` |
| 6. Explain | 공백마다 "바뀐 동작 + 필요한 테스트" | 에이전트 (좁은 질문, 판정에 안 들어감) | `agent.py`, `agent_tools.py` |
| 7. Report | JSON + Markdown | 템플릿 | `report.py` |

테스트를 돌릴 수 없으면(.venv 없음, 시간 초과) 판정은 E01(REVIEW)이고, 이름 규칙·import로 **추정**한 관련 테스트를 보여준다 (`related_tests.py`, v1의 방식).

## 3단계 Run 상세

- **스냅샷**: `git archive <sha>`를 임시 폴더에 푼다. 대상 저장소의 작업 폴더·`.git`은 바뀌지 않는다. git에 없는 파일(`.env`, 로컬 데이터)은 들어가지 않는다.
- **Python**: 대상 저장소의 `.venv` (또는 `--python`). 대상 환경에는 아무것도 설치하지 않는다.
- **coverage**: ReleaseGuard가 `.rg/tools`에 설치한 coverage 7.17.0을 `PYTHONPATH`로 넣는다. 대상 Python과 버전(3.13)이 달라야 하면 실행하지 않고 사유를 남긴다.
- **테스트별 실행 줄**: coverage `dynamic_context = test_function`. pytest JUnit XML(xunit1)로 context를 node id(`tests/test_x.py::test_f`)에 연결한다.
- **전체 테스트 실행**: 선택 실행은 하지 않는다 (Predict_Success 약 12초). 시간 상한 기본 300초.
- **base 재실행**: head에서 실패한 테스트만 base에서 coverage 없이 다시 돌려 "이번 변경이 깨뜨림 / 원래 깨짐 / 새 테스트"를 나눈다.
- 문서만 바뀌었으면 실행하지 않는다.

## 4단계 Gaps 상세

바뀐 줄 하나는 넷 중 하나다.

| 상태 | 뜻 |
|---|---|
| covered | 어떤 테스트가 실행함 (테스트 목록이 남는다) |
| import_only | 모듈을 불러올 때만 실행됨 (def·클래스·상수 줄) — 공백으로 보지 않음 |
| gap | 실행 가능한 줄인데 어떤 테스트도 실행하지 않음 → **검증 공백** |
| not_executable | 빈 줄·주석·docstring 등 |

연속된 공백 줄은 사이에 실행 불가 줄만 있으면 하나의 범위로 묶는다. Python 소스(테스트 제외)만 본다.

## 판정 규칙 v2

가장 심각한 규칙의 판정이 최종 판정. 아무 규칙도 발동하지 않으면 SAFE. NOTE는 판정에 영향 없음.

| id | 판정 | 조건 |
|---|---|---|
| B01 | BLOCK | 추가된 줄에 비밀값 패턴 |
| B03 | BLOCK | head에서 실패하는 테스트가 base에서는 통과했거나 base에 없음 (이번 변경이 깨뜨림) |
| B04 | BLOCK | head에서 테스트 수집·실행 오류 (import 실패 등) |
| G01 | REVIEW REQUIRED | 검증 공백이 1줄 이상 |
| T01 | REVIEW REQUIRED | base에서도 실패하던 테스트 |
| R04 | REVIEW REQUIRED | 의존성 변경 (테스트 환경이 실제와 다를 수 있음) |
| E01 | REVIEW REQUIRED | 테스트 미실행·시간 초과·coverage 없음 → 검증하지 못함 |
| N03 | NOTE | 설정 변경 |
| N05 | NOTE | 데이터 변경 |
| N06 | NOTE | 소스 삭제 (참조가 남으면 B03·B04로 드러남) |

v1에서 없어진 것: R01·R02(이름·import 추측), R03·R05(설정·데이터 → NOTE), R06(소스 삭제 → NOTE), R07(에이전트 HIGH), B02(테스트 삭제 → G01·B03으로 드러남).

## 6단계 Explain 상세

- 공백이 있을 때만, 큰 공백부터 최대 5개. 공백 하나에 tool calling 루프 하나 (LLM 최대 4회, 도구 최대 6회).
- 입력: 공백 위치, 앞뒤 15줄(줄 번호 포함), 그 파일의 diff, 같은 파일의 다른 변경을 실행하는 테스트 목록.
- 출력: `behavior`(바뀐 동작), `trigger`(실행 조건), `suggested_test`(file·name·scenario·assertion), `evidence`.
- "코드가 맞는지"는 판단하지 않는다. 무엇이 검증되지 않았는지만 다룬다.
- 검증: 근거(`file:경로:줄`, `tool:#n`)가 실제로 있는지, 제안 테스트 파일이 테스트 분류 경로인지. 새 파일인지도 표시.
- 실패해도 판정·결과는 그대로 남는다.

도구는 v1과 같은 읽기 전용 4개 (`git_diff`, `read_file`, `search_code`, `list_files`), head 커밋 기준.

## Eval v2

| 평가 | 무엇을 재나 | 정답 |
|---|---|---|
| `eval` | 커밋 전체의 판정 분포, 공백, 실행 시간, 결정성(반복 실행 결과가 완전히 같은가) | 수기 판정 15개(참고), 같은 커밋에서 바뀐 테스트 |
| `seeds` | 결함을 심은 사례에서 기대 판정·규칙이 나오는가 | `eval/seeds_*.yaml`의 expected·expect_rules |
| `szz` | 나중에 고쳐진 결함 줄이 들어올 때 검증 공백이었는가 | 고친 커밋(`fix_commits`)이 지우거나 바꾼 줄을 `git blame`으로 추적 |

SZZ의 공백 비율이 낮으면 "테스트가 실행은 했지만 결함을 못 잡았다"는 뜻이다. coverage만으로는 결함을 잡지 못한다는 한계를 숫자로 보여준다.

## 보안·안전

- 대상 저장소는 읽기만 한다. 테스트는 임시 폴더의 스냅샷에서 돌린다.
- 결함 심기(`seeds`)는 임시 clone에서만 한다.
- 대상 저장소의 테스트 코드를 실행하므로, **신뢰하는 저장소에만** 쓴다 (샌드박스는 이후 단계).
- 비밀값은 위치만 남기고 값은 저장하지 않는다.
