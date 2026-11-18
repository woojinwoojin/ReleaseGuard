# Stage 2b.1 Artifact Verification Value Eval — 설계 (초안)

- 작성: 2026-11-18 · **Claude 초안, 사용자 확인 전.** 결정 대기 Q1~Q7(8장)
- 근거: [보고서 #16](eval/20261117_eval_report_16.md) (P6·P7 정정 포함), [design_stage2b_0.md](design_stage2b_0.md), [status_roadmap.md](status_roadmap.md) "2b 원칙"
- 원칙: 코드는 `spikes/stage2b_1/`에 둔다(2b.0 `artifactlib`는 가져다 쓰고 고치지 않는다). **`releaseguard/` 제품 코드와 판정(SAFE·REVIEW·BLOCK)은 바꾸지 않는다.** API 호출 없음. 대상은 V2·V3만(V1은 보류, #16 6장).

## 1. 질문

> 2b.0에서 W05·W06을 잡은 V2·V3가 **처음 보는 변경에서도** 같은 일을 하는가?

| 과제 | 핵심 질문 |
|---|---|
| **A. V2 일반화** | 다른 컨테이너 프로젝트에서도 준비 실패와 정상 변경을 구분하는가? 실패 유형(진입점·import·포트·즉시 종료)마다 근거를 남기는가? 환경 부족은 결함으로 단정하지 않는가(`INCONCLUSIVE`)? |
| **B. V3 판단 불가 처리** | `if` 표현식·경로 필터·재사용 워크플로·`make test`·`tox`에서 근거 없는 PASS/FAIL 대신 `INCONCLUSIVE`를 내는가? 2b.0에서 시험하지 않은 비활성화(`if: false`·`continue-on-error`·`\|\| true`)를 잡는가? 실제 CI 변경 이력에서 과잉 경고는 얼마인가? |
| **C. E02 대비 추가 가치** | FAIL 근거가 고칠 위치를 가리키는가? 지금 제품은 "검증하지 못했다"(E02)까지만 말한다 |
| H-F. factory 경고 (가설) | uvicorn "ASGI app factory detected" 경고가 준비 실패를 미리 알려주는가? **보조 정보로만 기록, 결과 값에 쓰지 않는다** |

- 비목표: 판정 연동, 제품 통합, V1 개선, compose 전체 실행, 실제 GitHub에서 CI 실행, 레지스트리 push.
- 2b.0과 마찬가지로 **seed는 Claude가 만든다.** 검증기를 만든 사람이 실패도 만드므로, seed 결과는 "설계한 유형을 잡는다"까지만 말한다. 일반성의 근거는 실제 이력 표본(B)과 외부 저장소(A)에서 찾는다.

## 2. 확인한 사실 (2026-11-18)

| 항목 | 사실 |
|---|---|
| 자기 저장소 | Docker·CI 파일은 4주차에만 있다. Predict_Success·release-guard·week1~3에는 없다 → **2b.1의 새 표본은 외부 저장소가 필요하다** |
| `docker/awesome-compose` | Docker 조직의 예제 모음, CC0, 보관 안 됨, 마지막 push 2026-11-14, HEAD `30f4b7f`. Python 예제 `fastapi`·`flask`·`django` 외 nginx 조합 여러 개 |
| 그 예제의 Dockerfile 구조 | 다단계. **마지막 단계 `dev-envs`가 제3자 이미지 `gloursdocker/docker`를 복사한다.** compose는 `target: builder`를 지정 → 기본 빌드 대상(마지막 단계)을 쓰면 안 된다 |
| `fastapi` 예제 | `builder` 단계에 `CMD`가 없다 → 기본 이미지 `tiangolo/uvicorn-gunicorn-fastapi:python3.9-slim`의 기본 명령(gunicorn)으로 뜬다. 앱은 `GET /` 하나 |
| `flask` 예제 | `python:3.10-alpine`, `ENTRYPOINT ["python3"]` + `CMD ["app.py"]`, Flask 개발 서버 :8000, `GET /` 하나. `USER`가 없다(root 실행) |
| 성격 | 모두 **장난감 규모**다. 실제 서비스의 대표 표본이 아니라, 4주차와 **다른 시작 방식**(기본 이미지 명령, ENTRYPOINT+CMD, WSGI 개발 서버, build target)을 주는 표본이다 |
| Docker | 데몬 꺼져 있음(V2 실행 전 사용자가 켬) |

## 3. 표본

### A. V2 — 출처 × 사례

| 출처 | 내용 | 비고 |
|---|---|---|
| S0 4주차 `fee0039` | 2b.0 기준선 재확인(N0·W05) | 회귀 확인용, 새 증거로 세지 않음 |
| S1~S3 awesome-compose `30f4b7f` | `fastapi`, `flask`, `django` (Q1) | `--target builder` 고정, 엔드포인트는 실행 전 README·compose에서 정해 사례 파일에 적음 |

출처마다 같은 seed 유형을 적용한다(적용 불가면 사유와 함께 제외, 실행 전 확정):

| 유형 | 내용 | 기대 V2 |
|---|---|---|
| F1 진입점 참조 오류 | 실행 명령의 모듈·이름 오타 | `FAIL` (종료 또는 준비 안 됨, 로그 근거) |
| F2 시작 시 import 오류 | 앱 모듈이 import하는 패키지를 requirements에서 제거 | `FAIL` |
| F3 포트 불일치 | 앱이 다른 포트로 뜸 | `FAIL` (프로세스는 살아 있고 준비 안 됨) |
| F4 즉시 종료 | 시작 직후 예외로 종료 | `FAIL` (종료 코드·로그) |
| E1 환경 부족 | 앱이 사례 파일 `env_required`에 적은 변수를 시작 때 요구 | **`INCONCLUSIVE`** — 로그에 그 변수 이름이 나오면 결함으로 단정하지 않음 |
| N 정상 변경 | 진입점 형식 변경, 의존성 버전 변경, 실행 옵션 추가 | `PASS` |
| NF 정상 factory | `uvicorn mod:create_app`(`--factory` 없음, 자동 감지로 정상 동작) — **H-F 반례** | `PASS` (+ factory 경고 있음 예상) |
| NH HEALTHCHECK 추가 | Dockerfile에 `HEALTHCHECK` 추가 → 2b.0에서 한 번도 안 쓴 healthy 경로 | `PASS` |

- `INCONCLUSIVE`(E1) 규칙은 V2에 **새로 넣는 판단**이다. 사례 파일의 `env_required` 이름이 실패 로그에 나오면 `INCONCLUSIVE`로 둔다. 실행 전에 구현·커밋한다.
- 반복: 사례마다 3회(콜드 1 + 캐시 2) (Q4).

### B. V3 — seed + 실제 이력

**B1 seed (4주차 `ci.yml` 기준, 실행 전 고정)**

| 사례 | 내용 | 기대 V3a / V3b |
|---|---|---|
| D1 | 테스트 단계에 `if: false` | `FAIL` / `FAIL` |
| D2 | 테스트 단계에 `continue-on-error: true` | `FAIL` / `FAIL` |
| D3 | `pytest -rs \|\| true` | `FAIL` / `FAIL` |
| I1 | 테스트 단계에 `if: ${{ github.event_name == 'push' }}` | `INCONCLUSIVE` / `INCONCLUSIVE` |
| I2 | push·pull_request 모두에 `paths:` 필터 | `INCONCLUSIVE` / `INCONCLUSIVE` |
| I3 | 테스트 작업을 재사용 워크플로(`uses: ./.github/workflows/test.yml`)로 이동 | `INCONCLUSIVE` / `INCONCLUSIVE` |
| I4 | `pytest -rs` → `make test` | `INCONCLUSIVE` / `INCONCLUSIVE` |
| I5 | `pytest -rs` → `tox` | `INCONCLUSIVE` / `INCONCLUSIVE` |
| C3 | matrix 추가(파이썬 버전 2개), 명령 유지 | `PASS` / `PASS` |

- I1~I5의 V3a 기대는 "base에 있던 계약이 head에서 정적으로 확인되지 않음 → 사라졌다고 단정하지 않음"이다. 2b.0 V3가 이렇게 동작하는지는 아직 모른다. 다르게 나오면 **기대값을 고치지 않고 불일치로 보고**한다.

**B2 실제 이력 (정적 분석만, 코드 실행 없음)**

- 공개 Python 저장소에서 `.github/workflows/`를 바꾼 커밋을 **규칙으로** 고른다(Q2). 저장소 선정 규칙과 커밋 선정 규칙을 결과 전에 커밋한다.
- 각 커밋(부모 → 커밋)에 V3a·V3b를 돌린다. **사람 라벨은 V3 결과를 보기 전에** diff만 보고 붙인다: `CONTRACT_REMOVED`(테스트 실행 계약이 실제로 사라짐) / `CONTRACT_KEPT` / `UNCLEAR`.
- 라벨 초안은 Claude가 붙이고, 그 커밋을 먼저 해야 V3를 실행한다(누출 방지). 라벨을 사용자가 확인할지는 Q5.

## 4. 측정

| 지표 | 정의 |
|---|---|
| seed 탐지 | 기대 `FAIL` 사례 중 `FAIL` 수 / 기대 `INCONCLUSIVE` 중 `INCONCLUSIVE` 수 (따로 셈) |
| 정상 과잉 | 정상 사례(N·NF·NH·C3, B2의 `CONTRACT_KEPT`)에서 `FAIL` 수. **`INCONCLUSIVE` 비율은 따로 보고**(판단 불가가 많으면 쓸모가 줄어듦) |
| 근거 위치 (C) | `FAIL`마다: 근거가 **seed를 넣은 파일**을 가리키는가 / 그 **줄·단계**까지 가리키는가 / 원인 종류(진입점·import·포트·종료·계약 제거)를 말하는가. 세 단계로 셈. W05처럼 로그가 앱 코드 쪽을 가리키고 Dockerfile을 가리키지 않는 경우를 그대로 드러내려는 것 |
| E02 대비 | 같은 사례에서 현재 제품 출력(E02 문구)과 V2·V3 근거를 나란히 기록. 점수는 매기지 않음 |
| 결정성 | V2 3회 결과 일치 |
| 비용 | 출처별 콜드·캐시 빌드, 준비 확인, 1회 전체(캐시 PASS만 따로) — P7 기준 |
| H-F | factory 경고 있음/없음 × READY/준비 실패 교차표. NF 반례 포함 |

## 5. 격리 (V2)

2b.0 5장 계약을 그대로 쓰고, 외부 출처 때문에 다음을 더한다(Q3).

| 영역 | 추가 계약 |
|---|---|
| 출처 | 고정 커밋(`30f4b7f`)의 `git archive` 스냅샷. 대상 디렉터리만 빌드 컨텍스트로 |
| 빌드 대상 | 사례 파일의 `build_target`(예제는 `builder`)만. `dev-envs` 단계는 빌드하지 않음 → 제3자 이미지 `gloursdocker/docker` 받지 않음 |
| 기본 이미지 | 빌드 로그(`--progress=plain`)에서 `FROM` 다이제스트 기록 (P4 재발 방지) |
| root 실행 이미지 | 예제는 `USER`가 없다. 이미지를 고치지 않고 그대로 실행하되 `--cap-drop ALL`·`no-new-privileges`·`--network none`·자원 제한 유지, root였다는 사실 기록 |
| 시작 로그 | **앞 50줄과 마지막 40줄을 따로 저장**(H-F, P6 기록 공백 해소) |
| 접두어 | `rg2b1-`, 끝나면 잔여 0 확인 |

## 6. 완료 기준 (실행 전 고정)

| 결론 | 조건 |
|---|---|
| **2b.2 후보** | A·B 모두: 기대 `FAIL` seed 전부 `FAIL`, 정상 seed `FAIL` 0, B2 `CONTRACT_KEPT`에서 `FAIL` 0, 기대 `INCONCLUSIVE` seed가 PASS·FAIL로 나오지 않음, 결정성 전부 일치, 잔여 0 |
| **범위 축소** | 한쪽(V2 또는 V3)만 위 조건 충족 → 충족한 쪽만 2b.2 후보 |
| **HOLD** | 정상 과잉 `FAIL`이 1개라도 원인 미상이거나, 외부 출처에서 V2를 못 돌림(빌드 환경 문제가 고쳐지지 않음) |

- 2b.2 후보가 돼도 **판정 연동은 하지 않는다.** 2b.2는 "선택 기능으로 보고서에 근거를 붙이는 것"까지를 다룬다.
- C(근거 위치)와 H-F는 결론 조건에 넣지 않고 보고만 한다(사람 시간 측정이 없어 가치 수치로 쓰기 어려움, #15 NOT_MEASURED 교훈).

## 7. 실행 순서 (단계마다 커밋, 결과를 보고 앞 단계를 바꾸지 않음)

1. 이 문서 확정 + 사례 파일 `eval/artifact_cases_2b1.yaml`(A seed·B1 seed·엔드포인트·`env_required`·`build_target`) + B2 선정 규칙 커밋
2. V2 보강(E1 `INCONCLUSIVE` 규칙, 시작 로그 분리 저장, 빌드 대상·다이제스트 기록) 구현·커밋 — 2b.0 동작을 바꾸지 않았는지 S0으로 회귀 확인
3. B2 표본 추출 → 라벨 초안 커밋 → (Q5) 확인
4. V3 실행(B1·B2) → 결과 커밋
5. 사용자가 Docker 켬 → V2 사전 점검(S0 N0·S1 정상 1회) → 전체 실행 → 결과 커밋
6. 보고서 #17

## 8. 결정 대기 (추천)

| # | 질문 | 추천 |
|---|---|---|
| Q1 | V2 외부 출처 | **awesome-compose `fastapi`·`flask`·`django` 3개.** Docker 조직 예제·CC0·고정 커밋이라 실행 위험이 낮고, 시작 방식이 4주차와 다름. 장난감 규모라 "다른 시작 방식에서도 동작"까지만 주장. 대안: 실서비스 OSS는 빌드 비용·위험이 커서 2b.1에서는 제외 |
| Q2 | B2 실제 이력 표본 | GitHub 공개 Python 저장소 **4개**, 저장소마다 워크플로 변경 커밋을 최근순 **10개**(총 40). 저장소 선정 규칙: pytest를 CI에서 돌리고, 최근 1년 안에 워크플로 변경이 10개 이상. 후보 목록은 규칙으로 뽑아 사용자 확인 뒤 고정 |
| Q3 | 외부 출처 격리 | 5장대로: 고정 커밋, `builder` 대상만, 빌드는 네트워크 허용·기록, 실행은 `--network none`·cap-drop, root 이미지는 고치지 않고 기록 |
| Q4 | V2 반복 | 3회 유지(콜드 1 + 캐시 2). 추정 실행 시간 약 1시간(출처 4 × 사례 약 8 × 3회, 콜드 빌드가 대부분) |
| Q5 | B2 라벨 확인 | Claude 초안 → **사용자가 `CONTRACT_REMOVED`·`UNCLEAR`만 확인**(대부분 `CONTRACT_KEPT`일 것이라 전수 확인은 비용 대비 효과 낮음) |
| Q6 | E1 환경 부족 규칙 | 사례 파일에 적은 `env_required` 이름이 로그에 나올 때만 `INCONCLUSIVE`. 일반 추론(`KeyError` 전부 등)은 하지 않음 — 넓히면 진짜 결함을 숨김 |
| Q7 | H-F factory 경고 | 기록·교차표만. 결과 값·결론 조건에 쓰지 않음. NF 반례 필수 |
