# ReleaseGuard 프로젝트 제안서

## 1. 프로젝트 개요

**프로젝트명:** ReleaseGuard  
**한 줄 설명:** 코드 변경사항을 분석하고 영향 범위, 필요한 테스트, 배포 위험을 판단해 개발자의 릴리즈 의사결정을 돕는 에이전틱 시스템

ReleaseGuard는 Pull Request(PR) 또는 코드 변경사항을 입력으로 받아, 관련 코드와 문서, 테스트, 변경 이력, 과거 장애 정보를 분석하고 배포 위험을 평가하는 개발 지원 에이전트다.

단순한 코드 리뷰 도구를 목표로 하지 않는다. 핵심 목표는 다음 질문에 답하는 것이다.

> “이 변경이 시스템 어디에 영향을 주고, 무엇을 검증해야 하며, 지금 배포해도 되는가?”

이 프로젝트는 처음부터 복잡한 멀티에이전트 시스템을 만들지 않고, **단일 에이전트 MVP에서 시작해 실제 병목이 확인될 때마다 RAG, Memory, MCP, Multi-Agent, A2A, 운영 모니터링 등을 단계적으로 도입**하는 것을 원칙으로 한다.

---

## 2. 문제 정의

소프트웨어 변경은 코드 몇 줄의 수정으로 끝나지 않는다. 하나의 변경이 다음과 같은 영역에 연쇄적인 영향을 줄 수 있다.

- API 스키마
- 데이터베이스 구조
- 테스트 코드
- 설정 파일
- 외부 서비스 연동
- 배포 환경
- 기존 기능
- 과거 장애와 유사한 실패 패턴

하지만 실제 개발 과정에서는 다음 문제가 자주 발생한다.

1. 변경의 영향 범위를 사람이 모두 추적하기 어렵다.
2. 어떤 테스트를 추가하거나 실행해야 하는지 판단하기 어렵다.
3. 과거에 비슷한 변경에서 발생한 장애 경험이 재사용되지 않는다.
4. 코드 리뷰와 테스트가 분리되어 있어 전체적인 배포 위험을 보기 어렵다.
5. 변경사항이 커질수록 사람이 놓치는 edge case와 regression 가능성이 커진다.

ReleaseGuard는 이 문제를 **코드 분석 + 도구 사용 + 검색 + 경험 메모리 + 평가/검증**의 조합으로 해결한다.

---

## 3. 목표 사용자

### 1차 사용자
- 개인 개발자
- 소규모 백엔드 팀
- GitHub 기반으로 개발하는 팀
- CI/CD 환경을 사용하는 팀

### 이후 확장 사용자
- 여러 저장소를 관리하는 조직
- 배포 안정성이 중요한 서비스 팀
- 장애 대응 및 변경 추적이 중요한 기업 개발팀

---

## 4. 핵심 목표

### 기능적 목표
- PR 및 코드 변경사항 분석
- 변경 영향 범위 추정
- 관련 코드 및 문서 탐색
- 관련 테스트 탐색 및 추천
- 필요한 테스트 실행
- 주요 edge case 및 regression 위험 탐지
- 배포 위험도 산정
- Release Recommendation 생성

### 학습 목표
이 프로젝트를 통해 다음 에이전트 엔지니어링 요소를 실제로 적용한다.

- Rule / Workflow / Agent 경계 설계
- Tool Calling
- Context Engineering
- RAG
- State Management
- Semantic Experience Memory
- Agent Evaluation
- Monitoring / Observability
- Human-in-the-loop
- MCP
- Multi-Agent
- A2A
- Security / Permission Boundary
- Continuous Improvement Loop

---

## 5. 설계 원칙

### 5.1 가장 단순한 구조부터 시작한다

기본 선택 순서는 다음과 같다.

```text
Rule
→ Workflow
→ Search / RAG
→ Single Agent
→ Multi-Agent
```

새로운 복잡성은 기존 구조로 해결하기 어려운 문제가 실제로 확인된 경우에만 추가한다.

### 5.2 AI가 필요하지 않은 작업은 AI에게 맡기지 않는다

예시:

| 작업 | 우선 방식 |
|---|---|
| DB migration 파일 변경 감지 | Rule |
| API schema 변경 여부 | Rule / Code |
| 테스트 파일 존재 여부 | Search |
| 영향 범위 추론 | LLM / Agent |
| 필요한 테스트 결정 | Agent |
| 테스트 실행 | Tool |
| 테스트 결과 판정 | Deterministic + Agent |
| 최종 위험 설명 | LLM |

### 5.3 설명 가능성을 유지한다

모든 주요 판단에는 다음 정보가 남아야 한다.

- 어떤 변경을 발견했는가
- 어떤 근거를 사용했는가
- 어떤 위험을 판단했는가
- 어떤 테스트를 선택했는가
- 테스트 결과는 무엇이었는가
- 최종 판단에 어떤 근거가 사용되었는가

### 5.4 상태 변경 작업은 별도의 승인 경계를 둔다

초기 버전에서는 분석과 테스트 실행까지만 자동화한다.

향후 다음 작업은 Human Approval 이후에만 실행하도록 설계한다.

- PR merge
- deployment
- rollback
- issue 생성
- 외부 시스템 변경

---

## 6. 핵심 사용자 시나리오

### Scenario A. 일반적인 PR 분석

```text
PR 생성
↓
변경 파일 분석
↓
관련 코드 / 테스트 / 문서 탐색
↓
영향 범위 추정
↓
위험 요소 탐지
↓
필요 테스트 추천
↓
Release Report 생성
```

### Scenario B. 테스트까지 수행

```text
PR
↓
Change Analysis
↓
Risk Classification
↓
Test Selection
↓
Test Execution
↓
Result Validation
↓
Release Recommendation
```

### Scenario C. 과거 장애 활용

```text
현재 PR
↓
유사한 과거 변경 검색
↓
관련 Incident / Failure Pattern 검색
↓
현재 변경과 비교
↓
추가 위험 제시
```

예시:

> 과거 유사한 DB migration 변경에서 integration test 누락으로 rollback이 발생했습니다.  
> 이번 PR에서도 동일한 integration test가 존재하지 않습니다.

---

## 7. 초기 MVP 범위

### MVP 목표

하나의 Git 저장소와 하나의 PR을 입력으로 받아 다음 결과를 생성한다.

1. 변경 파일 요약
2. 변경 유형 분류
3. 영향 가능성이 높은 파일 및 기능
4. 관련 테스트 탐색
5. 주요 위험 요소
6. 권장 테스트
7. Release Recommendation

### Release Recommendation

```text
SAFE
REVIEW REQUIRED
BLOCK
```

초기 버전에서는 최종 판단을 자동 배포와 연결하지 않는다.

---

## 8. 초기 시스템 구조

```text
User / PR
   ↓
Change Collector
   ↓
Repository Analyzer
   ↓
Single Release Agent
   ├─ Git / Diff Tool
   ├─ Code Search Tool
   ├─ Test Search Tool
   └─ Document Search Tool
   ↓
Risk Analysis
   ↓
Release Report
```

### 주요 State 예시

```text
repository
pull_request
changed_files
diff
detected_changes
related_files
related_tests
risks
recommended_tests
test_results
release_decision
evidence
```

---

## 9. 단계별 발전 로드맵

### Stage 1. Repository Analyst

목표:
- PR 변경사항 분석
- 관련 코드와 테스트 검색
- 영향 범위 설명

핵심 기술:
- Single Agent
- Tool Calling
- Repository Search
- Structured Output
- Context Engineering

---

### Stage 2. Release Guardian

목표:
- 테스트 선정 및 실행
- 결과 검증
- Release Recommendation

추가 요소:
- Workflow / Graph Orchestration
- State Management
- Retry / Fallback
- Evaluation

예상 흐름:

```text
Analyze
→ Classify Risk
→ Select Tests
→ Execute Tests
→ Validate
→ Decide
```

---

### Stage 3. Knowledge RAG

Repository 전체를 매번 Context에 넣지 않고 필요한 정보만 검색한다.

대상:
- README
- Architecture 문서
- API 명세
- 개발 규칙
- 테스트 가이드
- 운영 문서

목표:

> Minimum Sufficient Context

---

### Stage 4. Semantic Experience Memory

과거 PR과 장애 사례를 저장하고 유사한 변경에서 재사용한다.

저장 예시:

```text
Change:
DB migration 변경

Failure:
Integration test 누락

Result:
Production rollback

Insight:
DB schema 변경 시 migration + integration test 필요
```

현재 PR과 유사한 경험을 검색해 위험 판단에 활용한다.

---

### Stage 5. MCP Integration

외부 개발 도구와 Agent의 결합을 표준화한다.

후보:

```text
ReleaseGuard
    ↓
   MCP
 ┌──┼─────────────┐
GitHub   CI/CD   Docs
```

도입 조건:
- 외부 Tool 수가 증가
- Tool integration code가 Agent logic과 강하게 결합
- 다른 Agent에서도 동일 Tool을 재사용할 필요 발생

---

### Stage 6. Multi-Agent

Single Agent에서 실제 병목이 확인된 경우에만 도입한다.

예상 구조:

```text
Release Supervisor
       │
 ┌─────┼────────────┐
 ↓     ↓            ↓
Code   Test       Incident
Agent  Agent        Agent
       │
       ↓
    Reviewer
```

분리 후보:

- Code Analysis Agent
- Test Agent
- Incident / Memory Agent
- Reviewer Agent

도입 기준:

- Tool 수 증가로 selection 성능 저하
- Context 과다
- 서로 독립적인 작업 증가
- 전문화된 검증 필요
- 병렬 처리의 효과가 명확함

---

### Stage 7. A2A Experiment

독립적인 Agent를 서비스 단위로 분리할 필요가 생기면 Agent 간 통신 구조를 실험한다.

예:

```text
Release Agent
     ↓
     A2A
     ↓
Security Audit Agent
```

또는:

```text
Release Agent
     ↓
     A2A
     ↓
Independent Test Agent
```

목표는 A2A 자체의 사용이 아니라 **Agent 간 독립성과 재사용성이 실제로 필요한 상황에서 효과를 검증하는 것**이다.

---

## 10. Evaluation Strategy

ReleaseGuard의 핵심은 Agent 기능 자체보다 **정확한 위험 판단과 검증 가능성**이다.

### 10.1 Component Evaluation

평가 대상:

- 변경 파일 탐지
- 변경 유형 분류
- 관련 파일 검색
- 관련 테스트 검색
- Tool selection
- Tool arguments
- 테스트 실행
- State transition
- 최종 위험 분류

### 10.2 End-to-End Evaluation

과거 PR을 Eval Set으로 구성한다.

예:

```text
PR
+
실제 변경 범위
+
실제 테스트
+
실제 발생한 regression
+
실제 배포 결과
```

평가 질문:

- 실제 영향 파일을 찾았는가
- 필요한 테스트를 찾았는가
- 위험한 변경을 탐지했는가
- 실제 regression 가능성을 경고했는가
- 잘못된 위험 경고를 과도하게 만들지 않았는가

### 10.3 테스트 유형

- 정상 PR
- 작은 변경
- 대규모 변경
- DB migration
- API breaking change
- 테스트 누락
- configuration 변경
- 문서만 변경
- 잘못된 테스트
- CI 실패
- 외부 Tool 실패

---

## 11. 핵심 지표

### Quality
- Risk Detection Recall
- False Positive Rate
- Relevant Test Retrieval Precision
- Test Selection Recall
- Release Decision Accuracy

### Reliability
- Tool Failure Recovery Rate
- Regression Detection Rate
- 반복 실행 시 결과 일관성

### Efficiency
- 평균 Agent 실행 시간
- LLM 호출 수
- Tool 호출 수
- Token usage
- Cost per analyzed PR

### User Outcome
- 개발자가 실제로 수용한 경고 비율
- 추천 테스트 실행 비율
- Release Recommendation override 비율
- 사용자가 수정한 분석 비율

---

## 12. Monitoring / Observability

Agent의 결과뿐 아니라 실행 과정 전체를 추적한다.

관찰 대상:

```text
Request
↓
Context Construction
↓
Planning / Routing
↓
Tool Calls
↓
Retrieval
↓
Test Execution
↓
Validation
↓
Decision
```

수집할 정보:

- Trace
- Tool latency
- Model latency
- Token usage
- Retrieval 결과
- 실패한 Tool
- Retry 횟수
- 최종 decision
- 사용자 override

후보 도구:
- Langfuse
- OpenTelemetry
- 일반 로그/메트릭 스택

---

## 13. Improvement Loop

```text
Production / Test Runs
↓
Failure Detection
↓
Root Cause Analysis
↓
Eval Set 추가
↓
Prompt / Tool / Workflow 수정
↓
Regression Test
↓
Deployment
↓
Monitoring
```

실제 실패 사례를 Eval Set에 계속 추가하여 평가 데이터 자체가 프로젝트와 함께 성장하도록 한다.

---

## 14. Security

### 기본 원칙
- Least Privilege
- Tool input validation
- Structured schema
- Sandbox
- Authentication / Authorization
- Audit log
- Human approval

### 주요 위험
- 악성 repository content
- Prompt Injection
- 위험한 shell command
- 과도한 repository 권한
- 민감 정보 노출
- 잘못된 state-changing action

### 대응 방향

Agent에게 모든 명령 실행 권한을 직접 주지 않는다.

예:

```text
read_file()
search_code()
run_test()
```

처럼 범위가 좁은 Tool부터 제공한다.

---

## 15. Human-in-the-loop

위험도에 따라 자율성을 다르게 설정한다.

```text
LOW
→ 자동 분석

MEDIUM
→ 사람에게 Review 요청

HIGH
→ Human Approval 필수
```

초기 프로젝트에서는 분석과 테스트 실행까지 Agent가 담당하고, 실제 merge/deployment는 사람이 결정한다.

---

## 16. 기술 스택 후보

### Backend
- Python
- FastAPI

### Agent / Orchestration
- LangGraph 우선 검토
- 필요에 따라 다른 Agent SDK 비교

### Repository
- Git
- GitHub API

### Storage
- PostgreSQL
- pgvector 또는 별도 Vector Store

### Cache / Queue
- Redis

### Observability
- Langfuse
- OpenTelemetry

### Deployment
- Docker
- GitHub Actions
- Cloud VM 또는 Container 환경

초기 단계에서는 필요한 최소 구성만 사용한다.

---

## 17. 개발 원칙

프로젝트의 목표는 많은 Agent 기술을 사용하는 것이 아니다.

다음 질문을 반복한다.

> 이 기능은 정말 Agent가 필요한가?

> 이 복잡성을 추가하면 어떤 실제 문제가 해결되는가?

> 제대로 동작한다는 것을 어떻게 증명할 것인가?

기술 도입은 항상 실제 문제와 평가 결과를 근거로 결정한다.

---

## 18. 예상 리스크

### 기술적 리스크
- 코드 의미 분석의 불확실성
- 대규모 Repository에서 Context 증가
- 잘못된 Risk 판단
- 테스트 실행 비용
- Agent loop 증가
- 외부 CI/GitHub 장애

### 제품 리스크
- False Positive가 많아 경고가 무시될 가능성
- 기존 코드 리뷰 도구와 차별성이 부족할 가능성
- 개발자가 Agent 판단을 신뢰하지 않을 가능성

따라서 초기 단계에서는 자동 배포보다 **의사결정 지원 도구**에 집중한다.

---

## 19. 초기 성공 기준

MVP 단계에서 다음을 만족하면 Stage 1 성공으로 판단한다.

1. 실제 Git Repository를 분석할 수 있다.
2. PR diff에서 주요 변경사항을 추출할 수 있다.
3. 관련 코드와 테스트를 탐색할 수 있다.
4. 근거와 함께 주요 위험을 설명할 수 있다.
5. 필요한 테스트를 추천할 수 있다.
6. 동일 입력에 대해 크게 불안정하지 않은 결과를 제공한다.
7. 결과가 어떤 evidence에서 나왔는지 추적할 수 있다.
8. Eval Set으로 성능을 반복 측정할 수 있다.

---

## 20. 장기 제품 형태

최종적으로 GitHub App 또는 개발 플랫폼 통합 형태를 목표로 한다.

예시:

```text
ReleaseGuard

Risk: HIGH

변경:
user_schema.py 수정으로 DB schema 변경 감지

영향:
User API serializer 및 migration 영향 가능

검증:
관련 unit test 존재
integration test 미발견

과거 경험:
유사 변경에서 migration 누락으로 rollback 발생

추천:
1. Migration test 실행
2. /users integration test 추가
3. Staging verification

Decision:
REVIEW REQUIRED
```

장기적으로는 단순 코드 리뷰 기능이 아니라 **변경 영향 분석, 테스트 선택, 과거 장애 활용, 검증, 배포 의사결정을 연결하는 Agentic Release Intelligence System**으로 발전시키는 것을 목표로 한다.

---

## 21. 프로젝트의 최종 학습 목표

이 프로젝트에서 가장 중요한 것은 최종 제품 자체보다 발전 과정이다.

```text
Single Agent MVP
↓
Evaluation
↓
실제 병목 발견
↓
필요한 기술 도입
↓
Monitoring
↓
실패 분석
↓
Improvement
↓
Production-ready Agent
```

Agent 기술을 먼저 선택한 뒤 사용할 문제를 찾지 않는다.

**실제 문제를 해결하면서 필요한 기술이 무엇인지 판단하고, 그 판단을 평가 결과로 검증하는 것**을 이 프로젝트의 핵심 원칙으로 삼는다.
