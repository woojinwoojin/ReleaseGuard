# Stage 2b.0 Artifact Verification Spike — 설계 (확정)

- 작성: 2026-11-17 · 초안 `539fc57` → **외부 리뷰 반영 확정** (Q1·Q3·Q6 승인, Q2 수정, Q4·Q5 조건부 승인 → 조건을 4~6장에 반영). 결정 기록은 10장
- 근거: [보고서 #3](eval/20261103_eval_report_3.md) 2장(W05·W06 첫 실패), [#11](eval/20261111_eval_report_11.md) 로드맵 5번, [status_roadmap.md](status_roadmap.md) "2b 원칙"
- 원칙: 코드는 `spikes/stage2b_0/` 아래에 둔다. **`releaseguard/` 제품 코드와 판정(SAFE·REVIEW·BLOCK)은 바꾸지 않는다.** API 호출 없음.

## 1. 질문과 성공의 뜻

> W05·W06 같은 배포 산출물 결함을 잡으려면 **최소한 어떤 검증**이 필요한가? 그 검증이 이 기기(Windows 11, Docker Desktop)에서 **격리된 상태로, 감당할 수 있는 비용으로** 돌아가는가? **정상 변경에서는 조용한가?**

- **W05·W06은 이미 REVIEW다**(E02, `scope: UNSUPPORTED`). 그래서 성공은 REVIEW를 더 내는 것이 아니다. **E02가 설명하지 못한, 개발자가 고칠 수 있는 구체적인 실패 원인을 증명하는 것**이다.
  - W05: 정확한 시작 실패 원인(어느 명령의 어느 참조가 왜 실패했는지)
  - W06: 어떤 CI 테스트 실행 계약이 사라졌는지(어느 워크플로·어느 단계)
- 2.0처럼 **가능성 확인(spike)**만 한다. 일반적인 가치(정상 변경 전반의 과잉 경고, 다른 저장소)는 2b.1에서 본다. 반례가 적으므로 2b.0 결과를 높은 정확도의 증거로 해석하지 않는다.
- Mutation(2.x)은 "테스트가 동작 변화를 감지하는가"를 물었다. 2b는 "**배포 산출물이 동작 계약을 지키는가**"를 묻는다. 서로 다른 질문이다.
- 비목표: 판정 연동, 제품 통합, 외부·신뢰할 수 없는 저장소 실행, 레지스트리 push, EC2 배포 확인, CI를 실제 GitHub에서 돌리기, compose 전체 실행.

## 2. 지금까지 확인한 사실 (2026-11-17)

| 항목 | 사실 |
|---|---|
| W05 (`eval/seeds_week4.yaml`) | Dockerfile `CMD ["uvicorn", "api:app", …]` → `"app:api"`. `app.py`는 Streamlit 화면 파일이고 최상위 이름 `api`가 없다. `docker build`는 통과하고 **컨테이너 시작에서만** 실패한다 |
| W06 | `.github/workflows/ci.yml`에서 `Run tests`(`pytest -rs`) 단계 삭제. YAML은 여전히 유효하다. **CI를 실제로 돌려도 초록불**이다(테스트가 안 돌 뿐). 그래서 실행해서는 못 잡고, **정책 검사**로만 잡힌다 |
| 현재 제품 | 두 파일은 `C03 config`로 분류된다. 판정 v3부터 검증하지 못한 변경으로 E02 REVIEW + `scope: UNSUPPORTED`가 난다 |
| 실제 이력 | Docker·CI 파일을 바꾼 커밋은 4주차의 3개뿐이다: `6a987e0`(CI 추가), `f54b612`(Dockerfile + CI build), `cc36c47`(compose). 세 커밋 모두 GitHub Actions push 실행 success(`gh run list`, 2026-11-17 확인). 나머지 저장소에는 Docker·CI가 없다 |
| 4주차 구성 | 이미지 하나로 API(uvicorn :8000)와 UI(streamlit :8501)를 띄운다. **Dockerfile에는 `HEALTHCHECK`가 없다.** healthcheck(`/docs` 요청)는 compose의 `api` 서비스에만 있다 |
| API 시작 조건 | `api.py`는 OpenAI 클라이언트와 SQLite 연결을 요청할 때 만든다. `/docs`는 DB·네트워크·API 키 없이 응답할 수 있다(코드 확인, 실행 확인 전) |
| 도구 | Docker Desktop CLI 29.8.2가 설치돼 있다. **데몬은 꺼져 있다.** actionlint는 없다(이번 질문에 필요 없음) |

## 3. 결함을 계약으로 정의한다

| 계약 | 내용 | 깨는 사례 |
|---|---|---|
| **K1 컨테이너 준비** | 이미지가 빌드되고, 기본 명령으로 띄운 컨테이너가 시간 상한 안에 **서비스 준비 상태(READY)**가 된다. 프로세스가 살아 있는 것만으로는 K1을 만족하지 않는다 | W05 |
| **K2 CI 테스트 실행 계약** | push·pull_request 이벤트에서 도는 워크플로에 **테스트를 실행하는 단계**가 있고, 그 단계가 꺼져 있지 않으며(`if`가 항상 거짓이 아님), 실패하면 작업도 실패한다(`continue-on-error`·`\|\| true` 없음) | W06 |

## 4. 검증기

모든 검증기 결과는 판정과 **분리해서** 보관한다. 공통 결과 값: `PASS` / `FAIL` / `INCONCLUSIVE` / `NOT_RUN`. 모든 `FAIL`과 `INCONCLUSIVE`에는 근거(파일·줄·단계·로그 발췌)를 붙인다.

### V1 정적 진입점 검사 (코드 실행 없음, Docker 불필요)

- 대상: Dockerfile의 마지막 `CMD`/`ENTRYPOINT`(exec 형식). `uvicorn`·`python -m uvicorn`·`gunicorn`의 `모듈:이름` 인자만 해석한다.
- 판단:
  - `FAIL` (확실한 문제): 모듈 파일이 스냅샷에도 이미지 `COPY` 범위에도 없다. 또는 모듈은 있는데 그 이름이 **어디에서도** 정의되지 않았다. 여기서 "어디에서도"는 최상위 대입·`def`·`class`·`import … as`·`from … import`를 모두 본다는 뜻이다.
  - `PASS` (확인한 정상 구조): 모듈 최상위에 그 이름이 직접 정의돼 있다.
  - `INCONCLUSIVE` (정적으로 판단 불가): 셸 형식 명령, 환경 변수 치환, `--factory`, 모듈의 `__getattr__`·`globals()`·`exec` 사용, `from x import *`, 해석하지 않는 서버 형식.
- **이해하지 못한 구조를 오류로 내지 않는다.** Stage 1의 과잉 경고를 반복하지 않기 위해서다.

### V2 동적 준비 검사 (Docker 필요, 코드 실행)

1. 이미지 빌드 → 2. 기본 명령으로 컨테이너 시작 → 3. 준비 확인:
   - 이미지에 `HEALTHCHECK`가 있으면 그 상태가 `healthy`인지 본다.
   - 없으면 **사례 파일에 미리 적은 로컬 엔드포인트**에 컨테이너 안에서 요청한다(`docker exec`로 Python `urllib`, slim 이미지에 curl이 없음). 4주차는 `http://localhost:8000/docs`다. 이 값을 고른 출처는 compose healthcheck지만, compose 자체는 실행하지 않는다.
   - compose 파일에만 있는 healthcheck 설정(간격·재시도)은 쓰지 않는다(Q3과 일관).
- 결과:

| 결과 | 조건 |
|---|---|
| `PASS` (READY) | 시간 상한 안에 healthy 또는 엔드포인트 2xx·3xx 응답 |
| `FAIL` | 컨테이너가 상한 전에 종료됐거나(종료 코드·로그 마지막 줄 기록), 프로세스는 살아 있지만 엔드포인트가 상한까지 응답하지 않음 |
| `STARTED_ONLY` | `HEALTHCHECK`도 사전 엔드포인트도 없는데 프로세스만 상한까지 살아 있음. **K1 PASS로 세지 않는다** |
| `INCONCLUSIVE` | 빌드 단계 실패 중 네트워크·레지스트리 등 환경 원인으로 보이는 것. 또는 사례에 적은 환경 변수가 없으면 뜰 수 없는 구성(환경 불충분)이라 결함으로 단정할 수 없음 |
| `NOT_RUN` | Docker 데몬 없음, 사용자 미승인 등으로 실행하지 않음. **FAIL이 아니다** |

- 시간 상한: 준비 확인 30초, 0.5초 간격으로 확인한다. 이미지 `HEALTHCHECK`의 `interval`·`start-period`가 더 길면 상한을 `start-period + interval × 2`로 늘리고 기록한다(Docker 기본 간격은 30초다).
- **V1이 W05를 잡았다고 V2가 반드시 실패해야 하는 것은 아니다.** 둘은 검증 범위가 다르다. 결과가 같아도 "이번 사례에서 V2의 추가 효과가 관찰되지 않았다"까지만 말한다. V2가 일반적으로 불필요하다고 결론 내리지 않는다.

### V3 CI 정책 검사 (코드 실행 없음)

- 워크플로 YAML을 **구조로** 파싱한다(문자열 검색이 아님): `on`, `jobs.*.if`, `steps[*].if`, `continue-on-error`, `run`, `uses`, `needs`.
- 테스트 실행 단계 판별: `run` 명령의 셸 토큰에 `pytest`(또는 `python -m pytest`)가 있고, 같은 명령에 `|| true`·`; true`가 붙지 않은 단계.
  - **`pytest` 패턴은 이번 실험(4주차)의 명시적 정책이다.** 범용 기본 정책이라고 주장하지 않는다. `make test`·`tox`·`nox`·재사용 워크플로(`uses: ./.github/workflows/…`) 안의 테스트는 판별하지 못하고 `INCONCLUSIVE`로 둔다.
- 두 검사:

| 검사 | 확인하는 사실 | 결과 |
|---|---|---|
| **V3a 상대** | base에서 push·PR에 돌던 테스트 실행 단계가 head에서 **제거·비활성화**됐는가 (비활성화 = `if` 상수 거짓, `continue-on-error: true` 추가, `\|\| true` 추가) | 제거·비활성화 → `FAIL`, 그대로·이동(다른 단계·작업에 같은 계약이 있음) → `PASS`, base에 원래 없음 → `NOT_RUN`(비교 대상 없음) |
| **V3b 절대** | head가 정책의 테스트 실행 계약을 **포함**하는가 | 없음 → `FAIL`, 있음 → `PASS`, `if`가 표현식이라 정적으로 참·거짓을 못 정함, `paths`·`branches` 필터가 정책 이벤트를 좁힘, 재사용 워크플로 → `INCONCLUSIVE` |

- **V3는 "단계가 있다"까지만 확인한다.** 그 단계가 실제로 실행됐다는 것은 확인하지 않는다(그것은 실제 워크플로 실행 기록으로만 알 수 있다). 보고에 이 구분을 그대로 적는다.

## 5. 격리 (V2) — 빌드와 실행을 나눈다

**이미지 빌드와 컨테이너 실행 모두 임의 코드를 실행할 수 있다. Docker Desktop을 쓴다고 완전한 보안 격리가 보장되지 않는다.** 그래서 2b.0은 **신뢰하는 실험용 저장소(사용자 자신의 4주차 저장소)만** 대상으로 한다.

| 영역 | 계약 |
|---|---|
| 대상 | 사용자 자신의 저장소만 (4주차). 외부 저장소는 2b.0에서 실행하지 않는다 |
| 빌드 컨텍스트 | `git archive` 스냅샷 (작업 트리의 `.env`·`data/`가 들어가지 않음) |
| 이미지 빌드 | 네트워크 허용(pip 설치 필요). **외부 접근을 했다는 사실과 기본 이미지 다이제스트, requirements 해시를 기록**한다. 빌드 시 비밀값·build secret·SSH 전달 없음 |
| 컨테이너 실행 | `--network none` (루프백만, 준비 확인은 컨테이너 안 localhost) |
| 자원 | `--memory 512m --cpus 1 --pids-limit 256` |
| 권한 | `--privileged` 금지, `--cap-drop ALL`, `--security-opt no-new-privileges`. Dockerfile의 `USER app`(root 아님)을 그대로 쓴다 |
| 비밀·호스트 접근 | 환경 변수 파일·비밀값·호스트 볼륨·Docker 소켓 전달 금지 |
| 종료 | 시간 상한에 도달하면 `docker rm -f`. 이미지·컨테이너 이름에 고유 접두어(`rg2b0-`)를 붙인다. 끝나면 접두어로 남은 것이 0개인지 확인한다 |
| 결과 | 대상 저장소 **밖**(`release-guard/docs/eval/v2b0/`)에 쓴다. 대상 저장소의 HEAD·작업 트리가 그대로인지 확인한다(#15의 청결성 실패를 반복하지 않음). 홈·임시 경로·계정 이름은 가린다 |

## 6. 사례 (실행 전 고정)

| 사례 | 내용 | 기대 |
|---|---|---|
| **W05** | 기존 seed (`app:api`) | V1 `FAIL`(이름 `api`가 `app.py`에 없음), V2 `FAIL`(시작 실패 원인이 로그에 있음) |
| **W06** | 기존 seed (테스트 단계 삭제) | V3a `FAIL`, V3b `FAIL` (사라진 단계 이름·명령을 근거로) |
| N0 | base `fee0039` 그대로 | V1 `PASS`, V2 `PASS`, V3a `PASS`, V3b `PASS` |
| N1 | 실제 커밋 `6a987e0` (CI 추가) | V3a `NOT_RUN`(부모 커밋에 워크플로 없음), V3b `PASS`. Dockerfile이 아직 없음 → V1·V2 `NOT_RUN` |
| N2 | 실제 커밋 `f54b612` (Dockerfile 추가 + CI build 작업) | V1·V2·V3a·V3b `PASS` |
| N3 | 실제 커밋 `cc36c47` (compose 추가) | V1·V2·V3a·V3b `PASS` |
| **DN1** Docker 정상 1 | 유효한 진입점 변경: `CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]` | V1 `PASS`, V2 `PASS` |
| **DN2** Docker 정상 2 | 서비스가 그대로 뜨는 설정 변경: `CMD`에 `"--timeout-keep-alive", "10"` 추가 | V1 `PASS`, V2 `PASS` |
| **CN1** CI 정상 1 | 테스트 단계 이름만 변경(`Run tests` → `Unit tests`), 명령 유지 | V3a `PASS`, V3b `PASS` |
| **CN2** CI 정상 2 | 테스트 단계를 새 작업 `unit`으로 옮기고 `build`가 `needs: [test, unit]`이 됨, 실행 계약 유지 | V3a `PASS`, V3b `PASS` |

- 사례와 기대값, V2 사전 엔드포인트는 `eval/artifact_cases_2b0.yaml`에 적어 **검증기 실행 전에 커밋**한다. 결과를 보고 사례를 더하거나 바꾸지 않는다. 바꿔야 하면 `docs/eval/v2b0/protocol_changes.yaml`에 따로 남긴다.
- V2는 사례마다 3회 돌린다(콜드 빌드 1회 + 캐시 빌드 2회). 결정성과 시간 편차를 본다.
- seed 적용 방식은 기존 `seeds_week4.yaml`과 같다: base 스냅샷에 `find`/`replace` 편집을 적용한다. 실제 커밋 N1~N3은 그 커밋의 스냅샷을 쓰고, 상대 검사의 base는 부모 커밋이다.

## 7. 기록할 것

- 사례 × 검증기마다 결과, 근거, 시간. V2는 빌드·시작·준비 확인·정리 시간을 나눠 잰다.
- 환경: Docker 클라이언트·서버 버전, 기본 이미지 다이제스트, 실행 옵션 전체, 빌드의 외부 접근 여부.
- 정리 확인: 접두어로 남은 이미지·컨테이너 수, 대상 저장소 보존 여부.

## 8. 완료 기준 (2b.1로 가는 조건)

| 검증기 | 최소 성공 조건 |
|---|---|
| V1 | W05에서 진입점 오류를 근거(명령·모듈·이름)와 함께 `FAIL`. 정상 사례(N0·N2·N3·DN1·DN2)에서 `FAIL` 0개 (`INCONCLUSIVE`는 따로 셈) |
| V2 | N0에서 `PASS`(READY). W05에서 시작·준비 실패를 근거(종료 코드·로그)와 함께 `FAIL`. 정상 사례에서 `FAIL` 0개. 3회 결과 일치. 정리 후 잔여 0 |
| V3 | W06에서 사라진 테스트 실행 계약(단계 이름·명령·작업)을 근거와 함께 `FAIL`. CN1·CN2(이름 변경·작업 이동)에서 `PASS` |

- V1과 V2가 W05에서 다른 결과를 내도 실패가 아니다. 차이를 그대로 기록한다.
- 데몬이 꺼져 V2를 못 돌리면 V2는 `NOT_RUN`이다. 이 경우 V2 기준은 "미평가"로 남기고 V1·V3만 판단한다.
- 기준을 못 채우면 원인을 기록하고 검증기 범위를 줄인다(예: V1·V3만 2b.1로).

## 9. 실행 순서

1. 이 문서 + 사례 파일(`eval/artifact_cases_2b0.yaml`) 커밋 — 검증기 결과를 보기 전
2. V1·V3 구현·커밋 → 실행 → 결과 커밋 (Docker 불필요)
3. 사용자가 Docker Desktop을 켠다 → V2 구현·커밋 → 사전 점검(N0 1회) → 전체 실행 → 결과 커밋
4. 보고서 #16

## 10. 결정 기록 (2026-11-17, 외부 리뷰)

| # | 결정 |
|---|---|
| Q1 | 승인: V1·V2 모두 실행해 추가 가치 비교. V1은 FAIL / PASS / INCONCLUSIVE 구분 |
| Q2 | **수정**: 15초 생존은 성공이 아니다. 이미지 `HEALTHCHECK` → 사전 정의 엔드포인트 순으로 준비 확인. 둘 다 없으면 `STARTED_ONLY`(K1 PASS 아님). compose healthcheck는 쓰지 않음 |
| Q3 | 승인: Dockerfile 기본 실행 명령만. compose 전용 환경 변수가 없어서 실패하면 환경 불충분(`INCONCLUSIVE`) |
| Q4 | 조건부 승인 → 4장 V3: 구조 분석, 상대·절대 구분, `pytest`는 이번 실험의 명시적 정책, 정적으로 못 정하면 `INCONCLUSIVE`, "단계가 있음 ≠ 실행됨" |
| Q5 | 조건부 승인 → 5장: 빌드(네트워크 허용·기록)와 실행(`--network none`) 분리, 권한·자원·비밀 제한, 신뢰하는 저장소만 |
| Q6 | 승인 + 구성 확정: Docker 정상 2(진입점 형식 변경, 설정 변경), CI 정상 2(이름 변경, 작업 이동) |
| 결과 값 | 검증기마다 `PASS` / `FAIL` / `INCONCLUSIVE` / `NOT_RUN` (V2는 `STARTED_ONLY` 추가). 판정과 분리 |
