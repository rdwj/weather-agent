# Tasks: Cloud-Native Weather Agent

**Input**: Design documents from `/specs/001-cloud-native-weather/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: tech stack, libraries, structure
2. Load optional design documents:
   → data-model.md: Extract entities → model tasks
   → contracts/: Each file → contract test task
   → research.md: Extract decisions → setup tasks
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB, middleware, logging
   → Polish: unit tests, performance, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All contracts have tests?
   → All entities have models?
   → All endpoints implemented?
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

## Phase 3.1: Setup
- [X] T001 Create project structure with src/, tests/, manifests/, prompts/ directories
- [X] T002 Initialize Python project with pyproject.toml and requirements files
- [X] T003 [P] Configure pytest, ruff, black, and mypy in pyproject.toml
- [X] T004 [P] Create .env.example with required environment variables
- [X] T005 [P] Create Containerfile with multi-stage build using UBI9 Python 3.11

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests
- [X] T006 [P] Contract test GET /health in tests/contract/test_health.py
- [X] T007 [P] Contract test GET /ready in tests/contract/test_ready.py
- [X] T008 [P] Contract test POST /api/v1/weather/query in tests/contract/test_weather_query.py
- [X] T009 [P] Contract test GET /api/v1/weather/alerts in tests/contract/test_weather_alerts.py
- [X] T010 [P] Contract test GET /api/v1/session in tests/contract/test_session_info.py
- [X] T011 [P] Contract test GET /api/v1/session/locations in tests/contract/test_locations_get.py
- [X] T012 [P] Contract test PUT /api/v1/session/locations in tests/contract/test_locations_update.py
- [X] T013 [P] Contract test GET /api/v1/session/preferences in tests/contract/test_preferences_get.py
- [X] T014 [P] Contract test PATCH /api/v1/session/preferences in tests/contract/test_preferences_update.py
- [X] T015 [P] Contract test GET /api/v1/metrics in tests/contract/test_metrics.py

### Integration Tests
- [X] T016 [P] Integration test for basic weather query scenario in tests/integration/test_weather_query_flow.py
- [X] T017 [P] Integration test for context retention across queries in tests/integration/test_context_retention.py
- [X] T018 [P] Integration test for cache hit behavior in tests/integration/test_cache_behavior.py
- [X] T019 [P] Integration test for alert detection in tests/integration/test_alert_detection.py
- [X] T020 [P] Integration test for rate limiting in tests/integration/test_rate_limiting.py
- [X] T021 [P] Integration test for session timeout after 30 minutes in tests/integration/test_session_timeout.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Data Models
- [X] T022 [P] WeatherQuery model in src/models/weather_query.py
- [X] T023 [P] WeatherResponse model in src/models/weather_response.py
- [X] T024 [P] UserSession model in src/models/user_session.py
- [X] T025 [P] Location model in src/models/location.py
- [X] T026 [P] WeatherAlert model in src/models/weather_alert.py
- [X] T027 [P] UsageMetrics model in src/models/usage_metrics.py
- [X] T028 [P] ConversationTurn model in src/models/conversation_turn.py

### MCP Integration
- [X] T029 Create MCP client wrapper using FastMCP in src/lib/mcp_client.py
- [X] T030 [P] Create MCPWeatherTool for LangChain integration in src/lib/mcp_weather_tool.py
- [X] T031 [P] Configure MCP connection settings in src/config/mcp_config.py

### LangChain Agent
- [X] T032 Create LangChain agent with memory in src/services/weather_agent.py
- [X] T033 Implement conversation memory management in src/services/conversation_memory.py
- [X] T034 [P] Create prompt templates in prompts/weather_agent.yaml
- [X] T035 [P] Implement elicitation handling for ambiguous locations in src/services/elicitation.py

### LangGraph Workflow
- [X] T036 Define WeatherAgentState TypedDict in src/lib/agent_state.py
- [X] T037 Create LangGraph workflow with state management in src/workflows/weather_workflow.py
- [X] T038 Implement workflow nodes and edges in src/workflows/weather_nodes.py

### Redis Integration
- [X] T039 Create Redis connection manager in src/lib/redis_client.py
- [X] T040 Implement session storage service in src/services/session_service.py
- [X] T041 [P] Implement cache service with TTL in src/services/cache_service.py
- [X] T042 [P] Implement rate limiting with token bucket in src/services/rate_limiter.py

### API Endpoints
- [X] T043 Create FastAPI app with CORS and middleware in src/main.py
- [X] T044 Implement health and readiness endpoints in src/api/system.py
- [X] T045 Implement POST /api/v1/weather/query endpoint in src/api/weather.py
- [X] T046 Implement GET /api/v1/weather/alerts endpoint in src/api/weather.py (same file as T045)
- [X] T047 Implement session endpoints in src/api/session.py
- [X] T048 Implement preferences endpoints in src/api/preferences.py
- [X] T049 Implement metrics endpoint in src/api/metrics.py

### Authentication
- [ ] T050 Create OAuth2 middleware for OpenShift in src/middleware/auth.py
- [ ] T051 [P] Implement token validation in src/services/auth_service.py
- [ ] T052 [P] Create user context extraction in src/middleware/user_context.py

### CLI Commands
- [ ] T053 [P] Create CLI entry point with Click in src/cli/__init__.py
- [ ] T054 [P] Implement serve command in src/cli/serve.py
- [ ] T055 [P] Implement test-mcp command in src/cli/test_mcp.py

## Phase 3.4: Integration

### OpenTelemetry
- [ ] T056 Configure OpenTelemetry with OTLP exporter in src/lib/telemetry.py
- [ ] T057 Add FastAPI auto-instrumentation in src/main.py (update existing file)
- [ ] T058 [P] Create custom metrics for weather API calls in src/lib/metrics.py

### Logging
- [X] T059 Configure structured JSON logging in src/lib/logging_config.py
- [X] T060 Add correlation ID middleware in src/middleware/correlation.py
- [X] T061 Implement request/response logging middleware in src/middleware/logging.py

### Error Handling
- [X] T062 Create custom exception classes in src/lib/exceptions.py
- [X] T063 Implement global error handler in src/api/error_handlers.py
- [X] T064 Add graceful degradation for MCP unavailability in src/services/fallback.py

## Phase 3.5: OpenShift Deployment

### Kubernetes Manifests
- [X] T065 [P] Create base Deployment manifest in manifests/base/deployment.yaml
- [X] T066 [P] Create Service manifest in manifests/base/service.yaml
- [X] T067 [P] Create Route manifest in manifests/base/route.yaml
- [X] T068 [P] Create ConfigMap for environment in manifests/base/configmap.yaml
- [X] T069 [P] Create ServiceAccount and RBAC in manifests/base/rbac.yaml
- [X] T070 [P] Create HorizontalPodAutoscaler in manifests/base/hpa.yaml

### Kustomization
- [X] T071 Create base kustomization.yaml in manifests/base/kustomization.yaml
- [X] T072 [P] Create development overlay in manifests/overlays/development/
- [X] T073 [P] Create production overlay in manifests/overlays/production/

### Health Probes
- [X] T074 Configure liveness probe in manifests/base/deployment.yaml (update)
- [X] T075 Configure readiness probe in manifests/base/deployment.yaml (update)
- [X] T076 Configure startup probe in manifests/base/deployment.yaml (update)

## Phase 3.6: Polish

### Unit Tests
- [ ] T077 [P] Unit tests for MCP client wrapper in tests/unit/test_mcp_client.py
- [ ] T078 [P] Unit tests for cache service in tests/unit/test_cache_service.py
- [ ] T079 [P] Unit tests for rate limiter in tests/unit/test_rate_limiter.py
- [ ] T080 [P] Unit tests for conversation memory in tests/unit/test_conversation_memory.py
- [ ] T081 [P] Unit tests for validation logic in tests/unit/test_validation.py

### VCR Cassettes
- [ ] T082 [P] Create VCR cassette for current weather in tests/fixtures/cassettes/test_weather_current.yaml
- [ ] T083 [P] Create VCR cassette for forecast in tests/fixtures/cassettes/test_weather_forecast.yaml
- [ ] T084 [P] Create VCR cassette for alerts in tests/fixtures/cassettes/test_weather_alerts.yaml

### Performance Tests
- [ ] T085 Performance test for <2s response time in tests/performance/test_response_time.py
- [ ] T086 Load test for 100 concurrent users in tests/performance/test_load.py

### Documentation
- [ ] T087 [P] Update README.md with project overview and setup
- [ ] T088 [P] Create API documentation in docs/api.md
- [ ] T089 [P] Create deployment guide in docs/deployment.md
- [ ] T090 [P] Update quickstart.md with actual endpoints

### Code Quality
- [ ] T091 Run ruff and fix all linting issues
- [ ] T092 Run black to format all Python files
- [ ] T093 Run mypy and fix all type errors
- [ ] T094 Achieve 80%+ test coverage

## Dependencies
- Setup (T001-T005) blocks everything
- Contract/Integration tests (T006-T021) before implementation (T022-T064)
- Models (T022-T028) before services
- MCP integration (T029-T031) before LangChain agent
- LangChain (T032-T035) before LangGraph workflow
- Redis (T039) before session/cache services
- All core implementation before integration phase
- Integration (T056-T064) before OpenShift deployment
- Everything before polish phase (T077-T094)

## Parallel Example
```bash
# Launch all contract tests together (T006-T015):
Task: "Contract test GET /health in tests/contract/test_health.py"
Task: "Contract test GET /ready in tests/contract/test_ready.py"
Task: "Contract test POST /api/v1/weather/query in tests/contract/test_weather_query.py"
Task: "Contract test GET /api/v1/weather/alerts in tests/contract/test_weather_alerts.py"
Task: "Contract test GET /api/v1/session in tests/contract/test_session_info.py"
Task: "Contract test GET /api/v1/session/locations in tests/contract/test_locations_get.py"
Task: "Contract test PUT /api/v1/session/locations in tests/contract/test_locations_update.py"
Task: "Contract test GET /api/v1/session/preferences in tests/contract/test_preferences_get.py"
Task: "Contract test PATCH /api/v1/session/preferences in tests/contract/test_preferences_update.py"
Task: "Contract test GET /api/v1/metrics in tests/contract/test_metrics.py"

# Launch all model creation tasks together (T022-T028):
Task: "WeatherQuery model in src/models/weather_query.py"
Task: "WeatherResponse model in src/models/weather_response.py"
Task: "UserSession model in src/models/user_session.py"
Task: "Location model in src/models/location.py"
Task: "WeatherAlert model in src/models/weather_alert.py"
Task: "UsageMetrics model in src/models/usage_metrics.py"
Task: "ConversationTurn model in src/models/conversation_turn.py"
```

## Notes
- [P] tasks = different files, no dependencies
- Verify tests fail before implementing
- Commit after each completed task
- Follow TDD strictly - tests must exist and fail first
- Use VCR for all external API calls
- Ensure FIPS compliance if required

## Task Generation Rules
*Applied during main() execution*

1. **From Contracts**:
   - Each endpoint → contract test task [P]
   - Each endpoint → implementation task

2. **From Data Model**:
   - Each entity → model creation task [P]
   - Relationships → service layer tasks

3. **From User Stories**:
   - Each story → integration test [P]
   - Quickstart scenarios → validation tasks

4. **Ordering**:
   - Setup → Tests → Models → Services → Endpoints → Polish
   - Dependencies block parallel execution

## Validation Checklist
*GATE: Checked by main() before returning*

- [x] All contracts have corresponding tests (10 endpoints, 10 contract tests)
- [x] All entities have model tasks (7 entities, 7 model tasks)
- [x] All tests come before implementation
- [x] Parallel tasks truly independent
- [x] Each task specifies exact file path
- [x] No task modifies same file as another [P] task

## Summary
Total tasks: 94
- Setup: 5 tasks
- Tests: 21 tasks (all [P])
- Core Implementation: 43 tasks (14 [P])
- Integration: 9 tasks (1 [P])
- OpenShift Deployment: 12 tasks (8 [P])
- Polish: 18 tasks (12 [P])

Ready for execution via agents or manual implementation.