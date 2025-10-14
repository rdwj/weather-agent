# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Weather Agent is a production-ready intelligent weather assistant built with FastAPI, LangChain/LangGraph, and FastMCP v2. The system integrates with an external Weather MCP server for real-time weather data and uses LLMs for natural language processing and weather analysis.

**Key Architecture Pattern:** The agent uses a layered architecture where `BaseAgent` provides MCP and LLM capabilities, `WeatherAgent` implements weather-specific logic, and a FastAPI layer exposes REST endpoints. All prompts are stored as YAML files for easy editing and developer briefing.

## Essential Commands

### Development Server
```bash
# Start the API server (recommended method)
uvicorn src.api.weather_api:app --reload --port 8000

# Alternative: Start with python module
python -m uvicorn src.api.weather_api:app --reload --port 8000
```

### Testing and CLI
```bash
# Run CLI client for quick testing
python weather_cli.py health
python weather_cli.py weather "Seattle, WA"
python weather_cli.py forecast "Austin, TX" --days 5
python weather_cli.py compare "Seattle, WA" "Miami, FL"
python weather_cli.py chat  # Interactive mode

# Run comprehensive demo
python demo.py

# Run tests (when test suite exists)
pytest tests/
pytest --cov=src --cov-report=html
pytest tests/test_specific.py  # Run specific test file
pytest -k "test_weather"       # Run tests matching pattern
```

### Code Quality
```bash
# Format code
black src/ tests/ --line-length 100

# Lint code
ruff check .

# Type checking
mypy src/
```

### Redis (Required for Caching)
```bash
# macOS
brew services start redis
# Or manually: redis-server

# Linux
sudo systemctl start redis

# Test connection
redis-cli ping
```

### Streamlit UI
```bash
# Launch UI
streamlit run ui/weather_chat.py

# Or use the launch script
./ui/run.sh
```

### Container and Deployment
```bash
# Build container (IMPORTANT: use --platform for Mac)
podman build --platform linux/amd64 -t weather-agent:latest -f Containerfile . --no-cache

# Full OpenShift deployment
./scripts/deploy-openshift.sh

# Update secrets only
./scripts/apply-secret.sh

# Rebuild and redeploy code changes
./scripts/rebuild-openshift.sh

# Verify deployment health
./scripts/verify-deployment.sh
```

## Architecture Patterns

### Agent Framework Pattern
The codebase implements a **base agent abstraction** with MCP integration:

- **BaseAgent** (`src/core/base_agent.py`): Abstract base class providing:
  - MCP client connection and tool calling
  - LLM interaction with retry logic and schema validation
  - Resource and prompt operations from MCP server
  - Built-in methods: `think()`, `decide()`, `extract()`, `summarize()`, `chain_thought()`
  - Tool call history tracking
  - Metrics and health monitoring

- **WeatherAgent** (`src/agents/weather_agent.py`): Concrete implementation providing:
  - Weather data retrieval with caching and geocoding fallback
  - Multi-location comparison
  - Forecast analysis
  - Natural language chat interface with conversation memory
  - Weather narrative formatting using LLM

- **LLM Integration** (`src/utilities/call_model.py`, `llm_client.py`):
  - Singleton pattern for LLM client
  - Automatic retry with exponential backoff
  - Schema-validated structured outputs
  - Graceful degradation when LLM unavailable

### MCP Integration Pattern
The agent connects to an **external Weather MCP server** (not included in this repo):

- Weather MCP server repository: https://github.com/rdwj/weather-mcp
- Connection via HTTP transport (streamable-http)
- Tools available: `get_weather`, `geocode_location`, `get_weather_from_coordinates`
- MCP configuration in `.env` via `MCP_URL` variable
- Connection happens at agent initialization in FastAPI lifespan

### Prompt Management Pattern
All prompts are stored in `prompts/` as YAML files for easy editing:

- `system_prompt.yaml` - Agent personality and instructions
- `weather_report_format.yaml` - Natural language weather report formatting
- `general_analysis.yaml`, `safety_analysis.yaml`, etc. - Specific analysis types
- `location_comparison.yaml` - Multi-location comparison prompts
- `forecast_analysis.yaml` - Extended forecast interpretation

**Variable substitution** uses `{variable_name}` format in templates. Prompts are loaded via `PromptLoader` utility.

### Conversation Memory Pattern
The agent implements **thread-based conversation memory** (`src/core/conversation_memory.py`):

- Tracks conversation context per thread ID
- Stores last location and weather data for follow-up queries
- Enables natural conversation: "How about tomorrow?" after asking about a location
- Memory persists across API calls within same thread
- Thread management endpoints: `GET /conversation/{thread_id}`, `DELETE /conversation/{thread_id}`

### Caching Pattern
**Redis-backed distributed caching** with graceful fallback:

- Cache manager in `src/utilities/cache_manager.py` supports both Redis and in-memory
- Default TTL: 15 minutes for weather data
- Cache keys: `weather:{location.lower().strip()}`
- Cache stats and clearing via API endpoints

## Key Files and Their Roles

### Core Agent Framework
- `src/core/base_agent.py` - Abstract agent with MCP and LLM capabilities (1100+ lines)
- `src/core/mcp_resources.py` - MCP resource handler for reading resources from server
- `src/core/mcp_prompts.py` - MCP prompt handler for retrieving prompt templates
- `src/core/conversation_memory.py` - Thread-based conversation state management

### Weather Agent Implementation
- `src/agents/weather_agent.py` - Main agent implementation (~800 lines)
  - Key methods: `get_weather()`, `compare_locations()`, `get_forecast()`, `chat()`, `analyze_weather()`
  - Uses prompt loader for YAML prompts
  - Implements geocoding fallback when direct weather lookup fails

### API Layer
- `src/api/weather_api.py` - FastAPI REST endpoints (~520 lines)
  - Lifespan handler initializes/closes agent
  - All endpoints check agent initialization
  - CORS configured for web clients
  - Conversation thread endpoints for memory management

### Utilities
- `src/utilities/call_model.py` - LLM calling with retry and schema validation
- `src/utilities/llm_client.py` - Singleton LLM client with OpenAI-compatible interface
- `src/utilities/cache_manager.py` - Redis/memory cache with singleton pattern
- `src/utilities/prompt_loader.py` - YAML prompt loading with variable substitution

### User Interfaces
- `ui/weather_chat.py` - Streamlit chat interface with status indicators and LLM controls
- `weather_cli.py` - Rich-formatted command-line client for testing
- `demo.py` - Comprehensive feature demonstration script

## Configuration

### Required Environment Variables
```bash
# LLM (required for natural language features)
LLM_URL=https://your-llm-endpoint.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=your-model-name

# MCP Server (required for weather data)
MCP_URL=https://your-mcp-server.com/mcp/
```

### Optional Environment Variables
```bash
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Application
LOG_LEVEL=INFO
CACHE_TTL=3600
CACHE_TYPE=redis

# API
API_HOST=0.0.0.0
API_PORT=8000
```

See `.env.example` for complete configuration template.

## Development Patterns

### When Adding Features

1. **Extend WeatherAgent** class in `src/agents/weather_agent.py`
2. **Add API endpoints** in `src/api/weather_api.py`
3. **Add prompts** in `prompts/` as YAML files
4. **Update UI** in `ui/weather_chat.py` if needed
5. **Add tests** in `tests/` (when test suite exists)
6. **Test with CLI** using `weather_cli.py`

### When Modifying MCP Integration

- MCP client connection happens in `BaseAgent.connect_mcp()`
- Tool calling happens via `BaseAgent.call_tool()` with automatic retry support
- All MCP operations return `{"success": bool, "data": Any, "error": str | None}`
- Tool call history tracked in `BaseAgent.tool_call_history` for debugging

### When Working with Prompts

- All prompts are YAML files in `prompts/` directory
- Use `{variable_name}` for variable substitution
- Load with `PromptLoader.load_prompt(prompt_name, variables_dict)`
- Prompts include metadata: name, description, version, parameters, variables
- Example usage in `WeatherAgent._format_weather_narrative()`

### When Handling Conversation Memory

- Use `thread_id` parameter in chat operations for persistence
- Access memory via `WeatherAgent._memory_manager`
- Key methods: `get_last_location()`, `get_last_weather_data()`, `update_conversation_state()`
- Thread summaries available via API: `GET /conversation/{thread_id}`

## Testing Strategy

### Manual Testing
- Use `weather_cli.py` for quick endpoint testing
- Use `demo.py` for comprehensive feature testing
- Use Streamlit UI for interactive testing with visual feedback

### Automated Testing (When Implemented)
- Unit tests: Test individual components in isolation
- Integration tests: Test API endpoints and agent workflows
- Contract tests: Verify MCP server contract compliance
- Target coverage: 80%+ for all new code

### Test Markers (pyproject.toml)
```bash
pytest -m unit          # Run only unit tests
pytest -m integration   # Run only integration tests
pytest -m "not slow"    # Skip slow tests
```

## API Endpoint Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | System health and component status |
| `/weather` | GET/POST | Current weather for location |
| `/weather/analyze` | POST | LLM analysis of weather data |
| `/weather/compare` | POST | Compare multiple locations |
| `/forecast` | GET/POST | Extended weather forecast |
| `/chat` | POST | Natural language chat interface |
| `/cache/clear` | POST | Clear weather cache |
| `/cache/stats` | GET | Cache statistics |
| `/tools` | GET | List available MCP tools |
| `/prompts` | GET | List available MCP prompts |
| `/resources` | GET | List available MCP resources |
| `/conversation/{thread_id}` | GET | Get thread summary |
| `/conversation/{thread_id}` | DELETE | Clear thread history |

## OpenShift Deployment Notes

- All deployment scripts in `scripts/` directory
- Manifests in `manifests/base/` with Kustomize overlays in `manifests/overlays/`
- **IMPORTANT:** Always use `-n namespace` flag with `oc` commands (never `oc project`)
- Secrets managed via `scripts/apply-secret.sh` from `.env` file
- Container platform: **Podman only** (not Docker)
- Base images: Red Hat UBI9 (`registry.redhat.io/ubi9/python-311`)
- Build with `--platform linux/amd64` when building on Mac

## Dependencies

Key Python dependencies (see `pyproject.toml` for versions):
- **fastapi** - REST API framework
- **uvicorn** - ASGI server
- **langchain**, **langgraph** - Agent framework
- **fastmcp** - MCP v2 client
- **redis** - Distributed caching
- **pydantic** - Data validation
- **httpx** - Async HTTP client
- **opentelemetry** - Observability
- **streamlit** - UI framework

Development dependencies:
- **pytest**, **pytest-asyncio**, **pytest-cov** - Testing
- **black** - Code formatting (line length: 100)
- **ruff** - Linting
- **mypy** - Type checking

## Common Issues and Solutions

### MCP Connection Failures
- Verify `MCP_URL` in `.env` points to deployed Weather MCP server
- Check MCP server is accessible: `curl $MCP_URL/health`
- Review API logs: `oc logs deployment/weather-agent-api -n weather-agent`

### Cache Issues
- Ensure Redis is running: `redis-cli ping`
- Check Redis connection in health endpoint: `curl http://localhost:8000/health`
- Clear cache if stale: `curl -X POST http://localhost:8000/cache/clear`

### LLM Not Available
- Agent gracefully degrades without LLM (returns formatted data without analysis)
- Verify `LLM_URL`, `LLM_API_KEY`, and `LLM_MODEL_NAME` in `.env`
- Check health endpoint for LLM availability status

### Conversation Memory Not Working
- Thread IDs must be passed consistently in chat requests
- Memory is in-process (not persisted across pod restarts)
- Use `GET /conversation/{thread_id}` to verify thread state

## Code Style

- **Line length:** 100 characters (Black + Ruff)
- **Python version:** 3.11+
- **Type hints:** Required for all function signatures
- **Async/await:** Used throughout for all I/O operations
- **Error handling:** Always return structured responses with `{"success": bool, "error": str | None}`
- **Logging:** Use module-level logger, INFO for operations, DEBUG for details, WARNING for degraded state

## Related Documentation

- **README.md** - User-facing project documentation and quick start
- **README-OPENSHIFT.md** - Detailed OpenShift deployment guide
- **ui/README.md** - Streamlit UI documentation
- **Weather MCP Server** - https://github.com/rdwj/weather-mcp (required dependency)
