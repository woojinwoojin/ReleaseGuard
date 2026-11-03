# ReleaseGuard

코드 변경(`base...head`)을 분석해 **영향 범위, 필요한 테스트, 배포 위험**을 근거와 함께 알려주는 개발자용 도구.

- 제안서: [docs/proposal.md](docs/proposal.md)
- 문제 정의: [docs/problem.md](docs/problem.md)
- 설계: [docs/design.md](docs/design.md)

## 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m releaseguard analyze --repo ..\predict-success --base HEAD~1 --head HEAD
.\.venv\Scripts\python -m pytest
```

결과는 `out/<날짜>_<head>.json`(판정과 근거)과 `.md`(보고서)로 저장된다.
에이전트(4단계)는 `.env`의 `OPENAI_API_KEY`가 필요하다 (`.env.example` 참고). 규칙만 돌리려면 `--no-agent`.

## 현재 상태 (Stage 1)

| 단계 | 상태 |
|---|---|
| 1. Collect — 변경 파일·줄 수·추가된 줄 | 완료 |
| 2. Classify — 규칙 분류 (`configs/rules.yaml`) | 완료 |
| 3. Related tests — 이름 규칙 + import 검색 | 완료 |
| 4. Impact — 에이전트 영향 분석 (읽기 전용 도구 4개, 근거 코드 검증) | 완료 |
| 5. Decide — 판정 규칙 v1 (B01·B02·R01~R07) | 완료 |
| 6. Report — JSON + Markdown | 완료 |
| Eval Set — Predict_Success 커밋 | 예정 |
