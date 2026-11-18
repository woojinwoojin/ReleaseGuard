# Stage 2b.1 Artifact Verification Value Eval — 설계

- 작성: 2026-11-18 · 초안 `989d933` → **외부 리뷰 조건부 승인 반영** (Q1·Q4·Q7 승인, Q2 조건부 승인, Q3·Q5·Q6 수정, V3 정책 재정의). 결정 기록 10장. Q8(V2 실행 환경)은 사용자 결정으로 일회용 EC2(9장). **남은 결정: Q9(B2 사례 목록 고정, 3단계)**
- 사례: [eval/artifact_cases_2b1.yaml](../eval/artifact_cases_2b1.yaml) (V2 30 · V3 10, 편집이 원본에 정확히 한 번 적용되고 `read_at` 줄에 변수가 있음을 실행 전 확인), B2 선정 규칙 [eval/b2_selection_2b1.yaml](../eval/b2_selection_2b1.yaml)
- 근거: [보고서 #16](eval/20261117_eval_report_16.md) (P6·P7 정정 포함), [design_stage2b_0.md](design_stage2b_0.md), [status_roadmap.md](status_roadmap.md) "2b 원칙"
- 원칙: 코드는 `spikes/stage2b_1/`에 둔다(2b.0 `artifactlib`는 가져다 쓰고 고치지 않는다). **`releaseguard/` 제품 코드와 판정(SAFE·REVIEW·BLOCK)은 바꾸지 않는다.** API 호출 없음. 대상은 V2·V3만(V1은 보류, #16 6장).

## 1. 질문

> **W05·W06을 다시 잡는 실험이 아니다.** 처음 보는 프로젝트·변경에서 V2·V3가 **고칠 수 있는 근거**를 내면서, **정상 변경을 잘못 경고하지 않는가**를 본다.

| 과제 | 핵심 질문 |
|---|---|
| **A. V2 일반화** | 4주차와 다른 시작 방식에서도 준비 실패와 정상 변경을 구분하는가? 실패 유형마다 근거를 남기는가? 환경 부족을 결함으로 단정하지 않는가? |
| **B. V3 정책·판단 불가** | 필수 테스트가 **실행되지 않거나 실패가 전파되지 않는** 변경을 잡는가? 정적으로 확인할 수 없는 구조에서 근거 없는 PASS/FAIL 대신 `INCONCLUSIVE`를 내는가? 실제 CI 변경 이력에서 과잉 경고는 얼마인가? |
| **C. E02 대비 추가 가치** | `FAIL` 근거가 고칠 위치를 가리키는가? 지금 제품은 "검증하지 못했다"(E02)까지만 말한다 |
| H-F. factory 경고 (관찰만) | uvicorn "ASGI app factory detected" 경고와 준비 결과의 관계. **결과 값·결론에 쓰지 않고, 이번 결과를 보고 탐지 규칙을 더하지 않는다** |

- V2와 V3는 **따로 결론을 낸다.** 하나만 유효하면 그것만 2b.2 후보가 된다(6장).
- seed는 Claude가 만든다. 검증기를 만든 쪽이 실패도 만드므로 seed 결과는 "설계한 유형을 잡는다"까지만 말한다. 일반성의 근거는 실제 이력(B2)과 외부 출처(A)에서 찾는다.
- 비목표: 판정 연동, 제품 통합, V1 개선, compose 전체 실행, 실제 GitHub에서 CI 실행, 레지스트리 push.

## 2. 확인한 사실 (2026-11-18)

| 항목 | 사실 |
|---|---|
| 자기 저장소 | Docker·CI 파일은 4주차에만 있다 → 새 표본은 외부 저장소가 필요하다 |
| `docker/awesome-compose` | Docker 조직의 예제 모음, CC0, HEAD `30f4b7f`. **세 예제는 한 저장소 안에 있다** → 독립 프로젝트 세 곳에서 재현했다고 주장하지 않는다 |
| Dockerfile 구조 | 세 예제 모두 다단계이고 마지막 `dev-envs`가 제3자 이미지 `gloursdocker/docker`를 복사한다. compose는 `target: builder` → 빌드 대상 `builder` 고정 |
| `fastapi` | 기본 이미지 `tiangolo/uvicorn-gunicorn-fastapi:python3.9-slim`, `builder`에 `CMD` 없음(기본 이미지 명령 상속), `GET /`. **requirements `fastapi`·`uvicorn` 버전 고정 없음** |
| `flask` | `python:3.10-alpine`, `ENTRYPOINT ["python3"]` + `CMD ["app.py"]`, Flask 개발 서버 :8000, `GET /`. `USER` 없음(root). **requirements `flask` 버전 고정 없음** |
| `django` | `python:3.7-alpine`, `Django==3.2.13`·`environs==7.3.1`, `python3 manage.py runserver 0.0.0.0:8000`. `SECRET_KEY`·`DEBUG`·`ALLOWED_HOSTS`를 환경에서 읽되 기본값 있음. 오래된 실행 환경이라 지금 빌드되는지 미확인 |
| B2 후보 저장소 | `pytest-dev/pytest`(`test.yml`), `fastapi/fastapi`(`test.yml`, 변경 경로·조건부 작업), `psf/requests`(`run-tests.yml`), `pallets/flask`(`tests.yaml`). 2025-11-18 이후 워크플로 변경 커밋: 60 / 100+ / 31 / 16 (GitHub API, 봇·의존성 커밋 포함) |
| Docker | 데몬 꺼져 있음 |

## 3. 표본

### A. V2 — 출처 × 사례

| 출처 | 내용 |
|---|---|
| S0 4주차 `fee0039` | 2b.0 기준선 재확인(N0·W05). 회귀 확인용, 새 증거로 세지 않음 |
| S1~S3 awesome-compose `30f4b7f` | `fastapi`, `flask`, `django`. 빌드 대상 `builder`. **원본의 실행 명령·환경 설정을 바꾸지 않는다** (정상 기준이 바뀌지 않게) |

**A0 표본 적합성 사전 검사** (seed 전, 원본만, 결과 커밋):
- 원본 이미지가 빌드되는가, 사전에 적은 엔드포인트·포트에서 준비되는가, 필요한 환경 변수와 실행 명령은 무엇인가, 실패하면 앱 결함인가 환경 문제인가.
- 설치된 패키지 버전(`pip freeze`)과 기본 이미지 다이제스트를 기록한다(버전 고정 없는 requirements 때문).
- **적합하지 않은 출처는 이 단계에서만 제외하고 사유를 남긴다.** seed 결과를 본 뒤에는 출처·사례를 바꾸지 않는다.

**seed 유형** (출처마다 적용, 적용할 수 없으면 실행 전에 사유와 함께 제외):

| 유형 | 내용 | 기대 V2 |
|---|---|---|
| F1 진입점 참조 오류 | 실행 명령의 모듈·이름 오타 | `FAIL` |
| F2 시작 시 import 오류 | 앱이 import하는 패키지를 requirements에서 제거 | `FAIL` |
| F3 포트 불일치 | 앱이 다른 포트로 뜸 | `FAIL` (프로세스는 살아 있고 준비 안 됨) |
| F4 즉시 종료 | 시작 직후 예외로 종료 | `FAIL` |
| E1 환경 부족 | 앱이 시작 때 사례 파일에 적은 변수를 요구 (기본값 없음) | `INCONCLUSIVE` (사유 `ENV_INSUFFICIENT`) |
| N 정상 변경 | 진입점 형식 변경, 의존성 버전 고정, 실행 옵션 추가 | `PASS` |
| NF 정상 factory | `uvicorn mod:create_app`(`--factory` 없음, 자동 감지로 정상 동작) — H-F 반례 | `PASS` |
| NH HEALTHCHECK 추가 | Dockerfile에 `HEALTHCHECK` 추가 → 2b.0에서 안 쓴 healthy 경로 | `PASS` |

**E1 환경 부족 규칙** (Q6 수정, 실행 전 구현·커밋). 다음 셋을 **모두** 만족할 때만 `INCONCLUSIVE`/`ENV_INSUFFICIENT`:
1. 사례 파일에 필요한 변수와 역할, **읽는 위치(파일·줄)**가 적혀 있다.
2. 마지막 예외가 그 위치에서 났고, 예외 종류·메시지가 그 변수의 누락·부적합을 가리킨다.
3. 다른 실패 근거가 없다: 연쇄 예외(`During handling…`)·그 앞의 다른 오류 로그가 없다.
- 1은 맞지만 2·3이 확인되지 않으면 `INCONCLUSIVE`/`UNKNOWN_CAUSE`로 둔다. 사례 파일에 변수가 없으면 이 규칙을 쓰지 않고, 준비 실패는 그대로 `FAIL`이다.
- 규칙은 사례 종류(seed인지)를 보지 않는다. **F 계열 seed에서 `ENV_INSUFFICIENT`가 나오면 규칙 오류로 보고한다.**
- **구현 해석 (2단계, 결과 전):** `UNKNOWN_CAUSE`는 2·3이 확인되지 않았고 **실패 로그에 선언된 변수 이름이 단어로 나올 때만** 쓴다. 이름이 로그에 없으면 준비 실패 그대로 `FAIL`이다. 그렇지 않으면 `env_required`가 켜진 S3의 모든 심은 결함(F1~F4)이 `UNKNOWN_CAUSE`가 된다. "앱 코드 프레임" = 사이트 패키지·표준 라이브러리 밖의 가장 안쪽 프레임. 근거: `spikes/stage2b_1/lib2b1.py` 머리말

**반복:** 사례마다 3회(콜드 1 + 캐시 2). **3회는 안정성 측정이지 독립 표본을 세 배로 늘리는 것이 아니다.**

### B. V3 — 정책 재정의 + seed + 실제 이력

**정책 (재정의).** "테스트 단계가 있다"가 아니라 **필수 테스트가 실행되고, 실패하면 작업이 실패하는가**를 본다. `FAIL`에는 메커니즘 코드를 붙인다.

| 코드 | 뜻 | 예 |
|---|---|---|
| `REMOVED` | 테스트 실행 단계가 사라짐 | W06 |
| `NOT_EXECUTED` | 단계는 있지만 실행되지 않음 | `if: false` |
| `FAILURE_ALLOWED` | 실행되지만 실패해도 작업이 성공 (Actions에서 단계 `outcome`은 실패여도 `conclusion`은 성공) | 단계·작업 `continue-on-error: true` |
| `FAILURE_MASKED` | 셸 명령이 테스트 실패를 숨김 | `pytest \|\| true` |

- `make test`·`tox`·재사용 워크플로는 **그 자체로 불안전하지 않다.** V3가 실제 실행 계약을 확인하지 못할 때만 `INCONCLUSIVE`다.
- 2b.0 V3가 위 코드를 내도록 고치는 것은 2단계(구현)에서 하고, 결과 전에 커밋한다.
- **구현 해석 (2단계, 결과 전):** V3a는 실패를 숨기는 꼬리(`|| true` 등)를 뗀 명령으로 같은 계약을 맞춘다(그래야 `FAILURE_MASKED`가 `REMOVED`로 잡히지 않음). V3a `INCONCLUSIVE`: 같은 명령이 있지만 if가 표현식, 필터 없던 정책 이벤트가 모두 필터로 좁혀짐, 같은 명령이 없지만 판별하지 못하는 실행 경로가 있음. 2b.0 사례 회귀 10/10 같음(`docs/eval/v2b1/v3_regression_2b0.json`)

**B1 seed (4주차 `ci.yml` 기준)**

| 사례 | 내용 | 기대 V3a / V3b |
|---|---|---|
| D1 | 테스트 단계에 `if: false` | `FAIL`(`NOT_EXECUTED`) / `FAIL` |
| D2 | 테스트 단계에 `continue-on-error: true` | `FAIL`(`FAILURE_ALLOWED`) / `FAIL` |
| D3 | `pytest -rs \|\| true` | `FAIL`(`FAILURE_MASKED`) / `FAIL` |
| I1 | 테스트 단계에 `if: ${{ github.event_name == 'push' }}` | `INCONCLUSIVE` / `INCONCLUSIVE` |
| I2 | push·pull_request 모두에 `paths:` 필터 | `INCONCLUSIVE` / `INCONCLUSIVE` |
| I3 | 테스트 작업을 재사용 워크플로(`uses: ./.github/workflows/test.yml`)로 이동 | `INCONCLUSIVE` / `INCONCLUSIVE` |
| I4 | `pytest -rs` → `make test` | `INCONCLUSIVE` / `INCONCLUSIVE` |
| I5 | `pytest -rs` → `tox` | `INCONCLUSIVE` / `INCONCLUSIVE` |
| C3 | matrix 추가(파이썬 버전 2개), 명령 유지 | `PASS` / `PASS` |

- 결과가 기대와 다르면 기대값을 고치지 않고 불일치로 보고한다.

**B2 실제 이력 (정적 분석만, 코드 실행 없음)** — 선정 규칙(Q2 조건 반영, 실행 전 커밋):

| 항목 | 규칙 |
|---|---|
| 저장소 | `pytest-dev/pytest`, `fastapi/fastapi`, `psf/requests`, `pallets/flask` |
| 기간·정렬 | 2025-11-18 00:00Z ~ 2026-11-18 00:00Z, 기본 브랜치 1차 부모 이력, 최신순 |
| 대상 커밋 | `.github/workflows/*.yml`·`*.yaml`을 실제로 바꾼 커밋. 바뀐 워크플로 중 하나 이상이 base 또는 head에서 push·pull_request 이벤트를 가짐(트리거만 보는 YAML 파싱, V3 판단과 무관) |
| 제외 | 병합 커밋, 같은 patch-id의 재적용(먼저 것만), 워크플로가 아닌 파일만 바뀐 경우 |
| 과대표집 방지 | 봇 작성자 또는 의존성 갱신(메시지 `Bump`·`chore(deps)`, `uses:` 버전만 바뀜) 커밋은 저장소당 최대 3개 |
| 개수 | 저장소당 최대 10개, 총 최대 40개 |
| 보존 | 저장소·base SHA·head SHA·바뀐 워크플로 경로·선정 사유 |

- **선정에 V3 결과를 쓰지 않는다.** 목록 추출 → 라벨 → 고정 → V3 실행 순서다.
- **라벨** (Q5 수정): Claude가 V3 결과를 보기 전에 diff만 보고 전수 초안: `CONTRACT_REMOVED`(테스트 실행 계약이 실제로 사라지거나 비활성화됨) / `CONTRACT_PRESERVED` / `UNCLEAR`.
  - `CONTRACT_REMOVED`·`UNCLEAR`는 **전수** 사용자 확인.
  - `CONTRACT_PRESERVED`는 **저장소당 2개를 고정 시드(`random.Random(20261118)`)로 뽑아** 사용자 확인.
  - 확인하지 않은 라벨은 `CLAUDE_ONLY`로 표시하고, 사람이 확인한 라벨과 따로 집계한다. `CLAUDE_ONLY`를 객관적 정답으로 쓰지 않는다.

## 4. 측정

| 지표 | 정의 |
|---|---|
| seed 탐지 | 기대 `FAIL` 중 `FAIL`, 기대 `INCONCLUSIVE` 중 `INCONCLUSIVE` (따로 셈). V3는 메커니즘 코드 일치도 따로 셈 |
| 정상 과잉 | 정상 사례(N·NF·NH·C3, B2 `CONTRACT_PRESERVED`)에서 `FAIL` 수. B2는 사람 확인 / `CLAUDE_ONLY`로 나눠 보고. **`INCONCLUSIVE` 비율은 따로 보고**(판단 불가가 많으면 쓸모가 줄어듦) |
| 근거 위치 (C) | `FAIL`마다 세 단계: seed를 넣은 **파일**을 가리키는가 / **줄·단계**까지 가리키는가 / **원인 종류**를 말하는가. W05처럼 로그가 앱 코드 쪽을 가리키는 경우를 그대로 드러낸다 |
| E02 대비 | 같은 사례에서 현재 제품 출력(E02 문구)과 V2·V3 근거를 나란히 기록. 점수는 매기지 않음 |
| 결정성 | V2 3회 결과 일치 |
| 비용 | 출처별로 따로: 콜드 빌드, 캐시 빌드, 컨테이너 시작, 준비 확인, 1회 전체(콜드·캐시 구분). **시간 초과·환경 실패는 빼지 않고 따로 집계.** 사전 추정(약 1시간)은 계획용일 뿐 |
| H-F | factory 경고 × 준비 결과 2×2 교차표 (경고 있음·PASS = 경고만으로 실패 아님 / 있음·FAIL = 원인 관계 추가 분석 / 없음·PASS = 정상 / 없음·FAIL = 경고로 못 잡는 실패) |

## 5. 격리 (V2)

**이미지 빌드도 신뢰할 수 없는 코드 실행으로 본다.** `--target builder`는 불필요한 단계를 빼줄 뿐, `builder`의 `RUN pip install …`을 안전하게 만들지 않는다. Windows의 Docker Desktop이 외부 코드를 안전하게 실행한다고 가정하지 않는다.

| 항목 | 계약 |
|---|---|
| 실행 환경 | **일회용 EC2** (Q8, 9장). 4주차·이 PC의 Docker Desktop에서는 외부 출처를 빌드·실행하지 않는다 |
| 출처·버전 | 고정 커밋 `30f4b7f`의 `git archive` 스냅샷, 대상 디렉터리만 빌드 컨텍스트. 기본 이미지 다이제스트(빌드 로그 `FROM`), 설치 패키지 버전 기록 |
| 빌드 전 정적 확인 | `builder`까지의 모든 `RUN`·`COPY --from`·requirements를 읽고 기록(외부 다운로드 대상 목록) |
| 빌드 네트워크 | 허용하되 접근 대상을 기록(기본 이미지 레지스트리, PyPI). 그 밖의 접근은 범위 밖 |
| 실행 | `--network none`, `--cap-drop ALL`, `no-new-privileges`, 메모리 512MB·CPU 1·PID 256. root 이미지는 고치지 않고 root였다는 사실을 기록 |
| 비밀·호스트 접근 | 비밀값·환경 변수 파일·호스트 볼륨·Docker 소켓 전달 금지. build secret·SSH 전달 없음 |
| 준비 확인 | 사례 파일에 미리 적은 엔드포인트·포트로만 |
| 시작 로그 | **앞 50줄과 마지막 40줄을 따로 저장** (H-F, P6 기록 공백 해소) |
| 정리 | 접두어 `rg2b1-`, 끝나면 컨테이너·이미지·네트워크 잔여 0 확인. 대상 저장소 HEAD·작업 트리 보존 확인 |

## 6. 결론 기준 (실행 전 고정, V2·V3 각각)

| 결론 | 조건 |
|---|---|
| **2b.2 후보** | 기대 `FAIL` seed를 모두 탐지하고, 지원 범위의 정상 사례에서 근거 없는 `FAIL`이 없고(B2는 사람 확인 라벨 기준), 기대 `INCONCLUSIVE`가 PASS·FAIL로 나오지 않고, 결정성 전부 일치, 비용·격리 조건이 수용 가능 |
| **범위 축소** | 특정 실행 방식(V2) 또는 특정 CI 패턴(V3)에서만 위 조건을 충족 → 그 범위만 후보 |
| **HOLD** | 오탐, 확인되지 않은 라벨, 환경 실패, 비용 문제로 실용적 가치를 판단하기 어려움 |

- V2와 V3를 묶지 않는다. 둘 다 2b.2 후보가 돼도 **판정 연동은 하지 않는다.** 2b.2는 "선택 기능으로 보고서에 근거를 붙이는 것"까지다.
- C(근거 위치)와 H-F는 결론 조건에 넣지 않고 보고만 한다.

## 7. 실행 순서 (단계마다 커밋, 결과를 보고 앞 단계를 바꾸지 않음)

1. 이 문서 확정 + 사례 파일 `eval/artifact_cases_2b1.yaml`(A seed·B1 seed·엔드포인트·`env_required`(역할·읽는 위치)·`build_target`) + B2 선정 규칙 커밋
2. 구현·커밋: V2 보강(E1 규칙, 시작 로그 분리 저장, 빌드 대상·다이제스트·패키지 버전 기록), V3 메커니즘 코드. 2b.0 사례로 회귀 확인(2b.0 결과와 같아야 함, V3 코드 추가분 제외)
3. B2 목록 추출 → Claude 라벨 초안 커밋 → 사용자 확인(3장 범위) → 고정 커밋
4. V3 실행(B1·B2) → 결과 커밋
5. (Q8 환경에서) A0 적합성 사전 검사 → 결과 커밋 → V2 전체 실행 → 결과 커밋
6. 보고서 #17

## 8. 기록할 것

- 사례 × 검증기마다 결과·사유 코드·근거·시간
- 환경: Docker 버전, 실행 옵션 전체, 기본 이미지 다이제스트, 설치 패키지 버전, 빌드의 외부 접근 대상
- 정리·보존 확인, 프로토콜 변경은 `docs/eval/v2b1/protocol_changes.yaml`

## 9. 남은 결정

| # | 질문 | 추천 |
|---|---|---|
| **Q8 (결정, 2026-11-18)** | V2 실행 환경 ("폐기 가능한 격리 VM 우선") | **사용자 결정: 일회용 EC2.** 조건: 이번 실험 전용으로 새로 띄우고 끝나면 terminate, IAM 역할 없음, 보안 그룹은 SSH(사용자 IP만) 인바운드만, 인스턴스에 AWS 자격 증명·OpenAI 키를 두지 않음, 저장소는 인스턴스에서 공개 원격으로 clone, 결과 파일만 scp로 가져옴, Docker 버전 기록. (초안 추천 문구:) **일회용 EC2 인스턴스**(시드니, 4주차와 같은 Ubuntu 24.04, t3.small 이상): 실행 뒤 종료(terminate)해서 버립니다. 비용은 몇 시간 사용 기준 수백 원 수준으로 추정(시간당 요금 기준, 실제 요금은 확인 필요, 예산 알림 이미 있음). 키·자격 증명은 인스턴스에 두지 않고, 결과 파일만 가져옴. 대안: 이 PC의 Docker Desktop + 빌드 전 정적 확인 — 출처가 Docker 조직의 고정 커밋이라 위험은 낮지만, 리뷰 조건("VM 우선")을 못 채운 것으로 기록 |
| **Q9** | B2 사례 목록 | 3단계에서 규칙으로 추출한 목록과 라벨을 함께 보여드리고, 확인 받은 뒤 고정 |

## 10. 결정 기록 (2026-11-18, 외부 리뷰)

| # | 결정 |
|---|---|
| Q1 | 승인: awesome-compose `fastapi`·`flask`·`django`, `builder` 고정. 조건: A0 적합성 사전 검사, 한 저장소라 독립 프로젝트 세 곳이라고 주장하지 않음 |
| Q2 | 조건부 승인: 후보 4개 저장소, 저장소당 최대 10·총 40. 선정 기간·정렬·제외 기준 사전 고정, V3 결과로 고르지 않음. 최종 목록은 따로 확정(Q9) |
| Q3 | 수정: 빌드도 신뢰할 수 없는 실행. 격리 VM 우선, 원본 실행 명령·설정 보존 |
| Q4 | 승인: 3회. 안정성 측정이지 표본 증가가 아님, 비용은 항목별·실패 포함 집계 |
| Q5 | 수정: 전수 초안 → REMOVED·UNCLEAR 전수 확인 → PRESERVED 규칙 표본 확인, 나머지 `CLAUDE_ONLY` |
| Q6 | 수정: 변수 이름만으로 불충분. 세 조건 모두 만족 시 `ENV_INSUFFICIENT`, 아니면 `UNKNOWN_CAUSE`. 심은 결함을 환경 부족으로 분류하지 않음 |
| Q7 | 승인: factory 경고는 관찰 지표만, 2×2 교차표, 결과를 보고 규칙을 더하지 않음 |
| V3 정책 | 재정의: 필수 테스트의 실행 가능성과 실패 전파. 메커니즘 코드 `REMOVED`·`NOT_EXECUTED`·`FAILURE_ALLOWED`·`FAILURE_MASKED`. `make test`·`tox`·재사용 워크플로는 확인 못 할 때만 `INCONCLUSIVE` |
| 결론 | V2·V3 따로. 2b.2 후보 / 범위 축소 / HOLD. 판정 연동 없음 |
