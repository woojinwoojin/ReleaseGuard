# ReleaseGuard Eval 결과

- 저장소: `C:\Project_Folder\predict-success` · 커밋 34개 · 분류 규칙 v1
- 판정 분포: REVIEW REQUIRED 19, SAFE 15
- 규칙 발동률: R01 9%, R02 50%, R03 41%, R04 3%, R05 32%, R07 9%
- 관련 테스트 탐색 (규칙, 테스트가 함께 바뀐 커밋 19개): precision 0.705, recall 0.969
- 판정 (수기 정답 15개): 정확도 0.867, 과잉 경고 2, 과소 경고 0
  - REVIEW REQUIRED → REVIEW REQUIRED: 8
  - SAFE → REVIEW REQUIRED: 2
  - SAFE → SAFE: 5
- 에이전트 (15회, 실패 0): 평균 LLM 3.6회, 도구 12.1회, 입력 토큰 47,078.1, 14.1초
  - 근거 확인 비율 0.914, HIGH 위험 3건
  - 추천 기존 테스트 (커밋 10개): precision 0.783, recall 1.0

## 커밋별

| 커밋 | 제목 | 판정 | 기대 | 규칙 | 실제 테스트 | 예측 테스트 | 에이전트 |
|---|---|---|---|---|---|---|---|
| `0fc36c3` | Write README from the EvidenceFirst proposal | SAFE ✓ | SAFE | - | - | - | 도구 5, 토큰 27,646, HIGH 0, 확인 2/2 |
| `93fd788` | Add roadmap checklist for the 4-week MVP | SAFE | - | - | - | - | - |
| `f962d60` | Record OpenDART key setup and add env example | REVIEW REQUIRED ✗ | SAFE | R03 | - | - | 도구 4, 토큰 5,298, HIGH 0, 확인 3/3 |
| `c7878e3` | Define the five questions, trust checks, and why V1 is a score | SAFE | - | - | - | - | - |
| `60dbee2` | Fix the pilot companies and the data-handling rules they surfaced | SAFE | - | - | - | - | - |
| `fc58c0e` | Collect pilot filings and financial API responses as immutable raw data | REVIEW REQUIRED | - | R02, R03, R04 | tests/__init__.py<br>tests/test_dart_collector.py | tests/test_dart_collector.py | - |
| `32c4dc5` | Record the raw storage decision and first collection results | SAFE | - | - | - | - | - |
| `99309f2` | Flatten financial API responses into a per-source observation table | SAFE ✓ | SAFE | - | tests/test_dart_facts.py | tests/test_dart_facts.py | 도구 14, 토큰 77,814, HIGH 0, 확인 6/7 |
| `82e4305` | Map required accounts to internal accounts and build the checklist | REVIEW REQUIRED | - | R02, R03 | tests/test_account_map.py<br>tests/test_dart_facts.py | tests/test_account_map.py<br>tests/test_dart_facts.py | - |
| `568ea41` | Reconcile required-account mismatches and add manual note confirmations | REVIEW REQUIRED | - | R02, R03, R05 | tests/test_account_map.py<br>tests/test_dart_facts.py<br>tests/test_manual.py | tests/test_account_map.py<br>tests/test_dart_facts.py<br>tests/test_manual.py | - |
| `b67e806` | Confirm balance-sheet sections by arithmetic and adjust held-for-sale items | REVIEW REQUIRED ✓ | REVIEW REQUIRED | R02, R03, R05 | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_manual.py | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_dart_facts.py<br>tests/test_manual.py | 도구 18, 토큰 50,905, HIGH 0, 확인 11/11 |
| `3db2f31` | Fix the reporting basis per company and compute the first 2025 metrics | REVIEW REQUIRED ✓ | REVIEW REQUIRED | R02, R03, R05 | tests/test_bs_sections.py<br>tests/test_metrics.py | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_dart_facts.py<br>tests/test_metrics.py | 도구 19, 토큰 54,828, HIGH 0, 확인 11/11 |
| `9e9c12b` | Fill 2025 note gaps with separated amount, scope, and component checks | REVIEW REQUIRED ✓ | REVIEW REQUIRED | R01, R02, R05, R07 | tests/test_manual.py | tests/test_manual.py<br>tests/test_metrics.py | 도구 16, 토큰 38,761, HIGH 1, 확인 11/11 |
| `c7733b3` | Close paths that promoted unconfirmed values, per code review | REVIEW REQUIRED ✗ | SAFE | R02, R03 | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_dart_facts.py<br>tests/test_manual.py<br>tests/test_metrics.py | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_dart_facts.py<br>tests/test_manual.py<br>tests/test_metrics.py | 도구 20, 토큰 58,829, HIGH 0, 확인 11/14 |
| `99c3179` | Add run manifests, proposed scoring rules, and coverage without redistribution | REVIEW REQUIRED | - | R02, R03 | tests/test_dart_facts.py<br>tests/test_scoring.py | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_dart_facts.py<br>tests/test_scoring.py | - |
| `b515f78` | Adopt scoring rules v2 as unvalidated project policy and keep v1 | REVIEW REQUIRED ✓ | REVIEW REQUIRED | R02, R03, R07 | tests/test_scoring.py | tests/test_scoring.py | 도구 11, 토큰 26,707, HIGH 1, 확인 9/9 |
| `a75285f` | Mark where to resume next session | SAFE | - | - | - | - | - |
| `24faf5b` | Add 2022-2025 retrospective trend with comparability flags | REVIEW REQUIRED | - | R02, R03, R05 | tests/test_trend.py | tests/test_manual.py<br>tests/test_metrics.py<br>tests/test_trend.py | - |
| `da30a78` | Split working-capital checks, add comparison spans, and evidence report | REVIEW REQUIRED ✓ | REVIEW REQUIRED | R01, R02 | tests/test_trend.py | tests/test_metrics.py<br>tests/test_trend.py | 도구 17, 토큰 73,704, HIGH 0, 확인 9/11 |
| `075e30c` | Add Cosmecca Korea evidence report sample | SAFE ✓ | SAFE | - | - | - | 도구 1, 토큰 8,971, HIGH 0, 확인 0/0 |
| `c2fe0d1` | Check activity classification in cash-flow identity and narrow report claims | REVIEW REQUIRED | - | R01, R02, R05 | tests/test_trend.py | tests/test_account_map.py<br>tests/test_bs_sections.py<br>tests/test_metrics.py<br>tests/test_trend.py | - |
| `b326bd1` | Update Cosmecca Korea evidence report sample | SAFE | - | - | - | - | - |
| `fa03441` | Match same-period rows across renamed accounts and split unverified reasons | REVIEW REQUIRED | - | R02 | tests/test_trend.py | tests/test_trend.py | - |
| `59e0fb4` | Update Cosmecca Korea evidence report sample | SAFE | - | - | - | - | - |
| `f2d690e` | Link domestic cosmetics production statistics to pilot companies | REVIEW REQUIRED ✓ | REVIEW REQUIRED | R02, R03, R05 | tests/test_market.py | tests/test_market.py | 도구 14, 토큰 52,784, HIGH 0, 확인 11/11 |
| `694de2e` | Add market statistics sample and refresh evidence report sample | SAFE | - | - | - | - | - |
| `f57b432` | Link cosmetics production by product type to pilot companies | REVIEW REQUIRED | - | R02, R03, R05 | tests/test_market.py | tests/test_market.py | - |
| `0b57374` | Refresh market statistics and evidence report samples | SAFE | - | - | - | - | - |
| `adb2f5b` | Check M01/M02 guidelines: price basis, reporting scope, continuity (D20) | REVIEW REQUIRED ✓ | REVIEW REQUIRED | R02, R03, R05, R07 | tests/test_market.py | tests/test_market.py | 도구 18, 토큰 59,957, HIGH 1, 확인 9/10 |
| `c9824b0` | Sync weekly checklist with actual progress; reorder next steps after check-in | SAFE ✓ | SAFE | - | - | - | 도구 1, 토큰 5,089, HIGH 0, 확인 2/2 |
| `142912b` | Close verification gaps from external review (D21) | REVIEW REQUIRED ✓ | REVIEW REQUIRED | R02, R03, R05 | tests/test_market.py<br>tests/test_metrics.py | tests/test_market.py<br>tests/test_metrics.py<br>tests/test_trend.py | 도구 16, 토큰 44,393, HIGH 0, 확인 5/8 |
| `388da2a` | Compare 2020-2025 reporting guidelines and close market research (D22) | REVIEW REQUIRED | - | R05 | tests/test_market.py | tests/test_market.py | - |
| `a5465f0` | Update README status, pilot industry and samples to current implementation | SAFE ✓ | SAFE | - | - | - | 도구 8, 토큰 120,485, HIGH 0, 확인 6/6 |
| `895dbe4` | Set next session start: minimal lookup screen | SAFE | - | - | - | - | - |
