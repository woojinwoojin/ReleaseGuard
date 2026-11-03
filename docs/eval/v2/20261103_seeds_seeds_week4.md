# ReleaseGuard Eval v2 — 결함을 심은 사례 (4/6 통과)

- 저장소: `C:\Project_Folder\2026-10\week4-docker-aws` (임시 clone에서 실행) · base `fee0039`

| id | 심은 변경 | 기대 | 결과 | 기대 규칙 | 발동 규칙 | 근거 | 통과 |
|---|---|---|---|---|---|---|---|
| W01 | 다른 데이터셋의 대화로 질문할 때 400 → 409로 변경 (테스트가 상태 코드를 확인함) | BLOCK | BLOCK | B03 | B03 | tests/test_api.py::test_chat_conversation_of_other_dataset (passed) | ✓ |
| W02 | 테스트 없는 새 엔드포인트 추가 | REVIEW REQUIRED | REVIEW REQUIRED | G01 | G01 | api.py:411-411 | ✓ |
| W03 | 대화 조회 404 메시지 문구 변경 (404 경로는 테스트되지 않음) | REVIEW REQUIRED | REVIEW REQUIRED | G01 | G01 | api.py:413-413 | ✓ |
| W04 | FastAPI 버전 올림 | REVIEW REQUIRED | REVIEW REQUIRED | R04 | R04 | - | ✓ |
| W05 | Dockerfile 실행 명령 오타 (컨테이너가 뜨지 않음) — 바라는 판정 | REVIEW REQUIRED | SAFE | - | - | - | ✗ |
| W06 | CI에서 테스트 단계 삭제 — 바라는 판정 | REVIEW REQUIRED | SAFE | - | - | - | ✗ |
