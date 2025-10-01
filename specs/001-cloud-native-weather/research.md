# Research Findings: Cloud-Native Weather Agent

## MCP Client Implementation

### Decision: FastMCP v2 with STDIO Transport
**Rationale**:
- FastMCP v2 provides native Python support with async capabilities
- STDIO transport for local development, HTTP for production
- Built-in tool schema validation and error handling

**Alternatives Considered**:
- Direct HTTP client: More complex, requires manual protocol handling
- gRPC: Overkill for this use case, adds complexity

## LangChain Integration Pattern

### Decision: Custom Tool Wrapper for MCP Tools
**Rationale**:
- LangChain's Tool interface can wrap MCP tool calls
- Maintains separation between agent logic and MCP protocol
- Enables easy testing with mock tools

**Implementation Pattern**:
```python
from langchain.tools import Tool
from fastmcp import FastMCP

class MCPWeatherTool(Tool):
    """Wrapper for MCP weather tools"""
    def _run(self, query: str) -> str:
        # Call MCP server via FastMCP client
        pass
```

**Alternatives Considered**:
- Direct MCP calls in agent: Tight coupling, harder to test
- Custom chain: Unnecessary complexity for simple tool calls

## LangGraph Workflow State Management

### Decision: TypedDict State with Conversation Memory
**Rationale**:
- TypedDict provides type safety for state management
- Conversation memory stored in state for context retention
- Clear state transitions for debugging

**State Structure**:
```python
class WeatherAgentState(TypedDict):
    query: str
    location: Optional[str]
    conversation_history: List[Message]
    cache_key: Optional[str]
    response: Optional[WeatherResponse]
```

**Alternatives Considered**:
- Pydantic models: Heavier weight, not needed for simple state
- Dict: No type safety, prone to errors

## Redis Session Management

### Decision: Redis with TTL-based Expiration
**Rationale**:
- Native TTL support for 30-minute session timeout
- Atomic operations for concurrent access
- JSON serialization for complex session data

**Key Pattern**:
```
session:{user_id}:{session_id} → {conversation_history, preferences}
cache:weather:{location}:{metric} → {data, timestamp}
```

**Alternatives Considered**:
- In-memory: Not scalable, lost on restart
- PostgreSQL: Overkill for simple key-value storage

## OpenShift OAuth2/OIDC Integration

### Decision: OpenShift Built-in OAuth with Service Account
**Rationale**:
- Native OpenShift integration via ServiceAccount tokens
- No additional auth infrastructure needed
- Automatic token rotation and management

**Configuration**:
```yaml
serviceAccountName: weather-agent
automountServiceAccountToken: true
```

**Alternatives Considered**:
- Keycloak: Additional infrastructure overhead
- Custom OAuth: Unnecessary complexity

## VCR Pattern for Testing

### Decision: vcrpy with Cassette per Test Module
**Rationale**:
- Records actual API responses for consistent testing
- Prevents hitting rate limits during test runs
- Easy to update when API changes

**Structure**:
```
tests/fixtures/cassettes/
├── test_weather_current.yaml
├── test_weather_forecast.yaml
└── test_weather_alerts.yaml
```

**Alternatives Considered**:
- Mock objects: Drift from actual API behavior
- Live API calls: Rate limits, test flakiness

## OpenTelemetry Configuration

### Decision: OTLP Exporter with Structured Logging
**Rationale**:
- OTLP is standard for OpenShift monitoring stack
- Structured logging enables better querying
- Auto-instrumentation for FastAPI

**Instrumentation**:
```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentator
FastAPIInstrumentator.instrument(app)
```

**Alternatives Considered**:
- Prometheus only: Limited tracing capabilities
- Custom metrics: Reinventing the wheel

## Containerization Strategy

### Decision: Multi-stage Build with UBI9 Python
**Rationale**:
- Red Hat UBI for OpenShift compatibility
- Multi-stage reduces image size
- FIPS-compliant base image available

**Build Pattern**:
```dockerfile
FROM registry.redhat.io/ubi9/python-311 as builder
# Build dependencies
FROM registry.redhat.io/ubi9/python-311-minimal
# Runtime only
```

**Alternatives Considered**:
- Alpine: Not Red Hat supported
- Ubuntu: Larger image size

## Rate Limiting Strategy

### Decision: Token Bucket with Redis Backend
**Rationale**:
- Token bucket allows burst traffic
- Redis provides distributed rate limiting
- Per-user and global limits supported

**Implementation**:
- 1000 requests/minute global limit
- 100 requests/minute per user
- Cached responses don't count against limits

**Alternatives Considered**:
- Fixed window: Can cause thundering herd
- Sliding window: More complex, minimal benefit

## Summary

All technical decisions align with constitutional principles:
- MCP-first architecture via FastMCP client
- Real-time data with Redis caching (15-min TTL)
- TDD with vcrpy for deterministic tests
- OpenTelemetry for comprehensive observability
- Simple REST API with clear contracts

No remaining clarifications needed - ready for Phase 1 design.