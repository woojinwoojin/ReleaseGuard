# ReleaseGuard

머지하기 전에, 바뀐 코드 중 **어떤 테스트도 실행하지 않는 곳(검증 공백)**을 찾고, 테스트를 **실제로 돌려서** SAFE / REVIEW REQUIRED / BLOCK으로 알려주는 로컬 CLI.

- **현재 상태와 로드맵: [docs/status_roadmap.md](docs/status_roadmap.md)**
- 문제 정의: [docs/problem.md](docs/problem.md) · 설계: [docs/design.md](docs/design.md) · 제안서: [docs/proposal.md](docs/proposal.md)
- 평가 보고서: [#1](docs/eval/20261103_eval_report.md), [#2](docs/eval/20261103_eval_report_2.md) (v1), [#3](docs/eval/20261103_eval_report_3.md) (v2), [#4](docs/eval/20261104_eval_report_4.md), [#5](docs/eval/20261104_eval_report_5.md) (v3·v3.1), [#6](docs/eval/20261104_eval_report_6.md) (분기 coverage), [#7](docs/eval/20261107_eval_report_7.md) (함수별 공백 그룹)
- 보고서 샘플: [docs/samples/report_142912b.md](docs/samples/report_142912b.md)

## 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt

# 분석 (대상 저장소의 .venv로 테스트를 돌린다. coverage는 처음 실행 때 .rg/tools에 설치된다)
.\.venv\Scripts\python -m releaseguard analyze --repo ..\predict-success --base HEAD~1 --head HEAD --no-agent

# 평가
.\.venv\Scripts\python -m releaseguard eval --repeat 2          # 커밋 전체 + 결정성
.\.venv\Scripts\python -m releaseguard seeds                    # 결함을 심은 사례 (임시 clone)
.\.venv\Scripts\python -m releaseguard szz                      # 결함 줄이 들어올 때 공백이었나

.\.venv\Scripts\python -m pytest
```

결과는 `out/`에 JSON(판정과 근거)과 Markdown(보고서)으로 저장된다.
공백 설명 에이전트(`--no-agent`를 빼면 실행)는 `.env`의 `OPENAI_API_KEY`가 필요하다 (`.env.example` 참고).

**주의**: 대상 저장소의 테스트 코드를 그대로 실행한다. 신뢰하는 저장소에만 쓴다.
