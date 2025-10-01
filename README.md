# Weather Agent

A production-ready intelligent weather assistant with MCP integration, REST API, and modern chat UI.

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Streamlit  │────▶│  FastAPI     │────▶│ WeatherAgent │────▶│  MCP Server  │
│     UI      │     │   REST API   │     │              │     │   (Weather)  │
└─────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
       ↓                    ↓                     ↓
   [Chat Interface]    [Endpoints]          [Caching]
                                            [Analysis]
```

## ✨ Features

### Weather Operations
- ✅ Current weather retrieval
- ✅ Extended forecasts (up to 7 days)
- ✅ Multi-location comparison
- ✅ Geocoding fallback
- ✅ Smart caching (15-minute TTL)

### System Features
- ✅ MCP server integration with tool calling
- ✅ Health monitoring and diagnostics
- ✅ Distributed cache management (Redis)
- ✅ Comprehensive error handling
- ✅ OpenTelemetry observability

### UI Features
- ✅ Modern Streamlit chat interface
- ✅ Real-time status indicators
- ✅ LLM parameter controls
- ✅ Example queries and preflight checks
- ✅ Weather data visualization

### Optional LLM Features
- 🔧 Natural language processing
- 🔧 Intelligent weather analysis
- 🔧 Conversational interface
- 🔧 Context retention

## ⚠️ Important: Weather MCP Server Required

**This weather-agent requires the Weather MCP server to function.** Before deploying or using this project, you must first deploy the Weather MCP server.

👉 **Go to the Weather MCP server repository and follow the deployment instructions:**
**https://github.com/rdwj/weather-mcp**

Once the Weather MCP server is deployed, configure the `MCP_URL` in your `.env` file to point to your deployed instance.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Redis (for distributed caching)
- Access to an MCP weather server
- LLM API credentials (optional, for analysis features)

### Local Development

1. **Clone and setup environment**

```bash
# Clone repository
git clone <repository-url>
cd weather-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

2. **Configure environment**

```bash
# Copy template and configure
cp .env.example .env
# Edit .env with your API keys and endpoints
```

See [Configuration](#-configuration) section for required variables.

3. **Start Redis (local development)**

```bash
# macOS
brew services start redis

# Or manually
redis-server

# Linux
sudo systemctl start redis
```

4. **Start the API server**

```bash
uvicorn src.main:app --reload --port 8000
```

5. **Launch the UI**

```bash
streamlit run ui/weather_chat.py
# Or use the launch script
./ui/run.sh
```

6. **Test with CLI**

```bash
# Check health
python weather_cli.py health

# Get weather
python weather_cli.py weather "Seattle, WA"

# Run demo
python demo.py
```

### OpenShift/Kubernetes Deployment

For production deployment to Red Hat OpenShift:

```bash
# Configure .env with your credentials
cp .env.example .env
# Edit .env...

# Deploy everything
./scripts/deploy-openshift.sh
```

See [README-OPENSHIFT.md](./README-OPENSHIFT.md) for detailed deployment guide.

## 📦 Components

### Core System (`src/`)

- **Weather Agent** (`src/agents/weather_agent.py`)
  - MCP integration for weather tools
  - Intelligent caching with Redis
  - Weather analysis and comparison
  - Natural language interface

- **REST API** (`src/api/weather_api.py`)
  - FastAPI endpoints
  - Health monitoring
  - Cache management
  - CORS support

- **Base Framework** (`src/core/`)
  - `base_agent.py` - Abstract agent with MCP support
  - `mcp_prompts.py` - Prompt template handling
  - `mcp_resources.py` - Resource management

- **Utilities** (`src/utilities/`)
  - `llm_client.py` - LLM integration
  - `call_model.py` - Model calling utilities

### User Interface (`ui/`)

- **Streamlit Chat App** (`ui/weather_chat.py`)
  - Modern, sleek design
  - Real-time status indicators
  - LLM parameter controls
  - Preflight system checks
  - Weather data visualization

### Testing & Demo

- **CLI Client** (`weather_cli.py`) - Command-line interface with rich formatting
- **Demo Script** (`demo.py`) - Comprehensive feature demonstration

## 📋 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health check |
| `/weather` | GET/POST | Get weather for location |
| `/weather/analyze` | POST | Analyze weather data with LLM |
| `/weather/compare` | POST | Compare multiple locations |
| `/forecast` | GET/POST | Get weather forecast |
| `/chat` | POST | Natural language chat interface |
| `/cache/clear` | POST | Clear cache |
| `/cache/stats` | GET | Cache statistics |
| `/tools` | GET | List available MCP tools |
| `/prompts` | GET | List MCP prompts |
| `/resources` | GET | List MCP resources |

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

**Required:**
```env
# LLM Configuration
LLM_URL=https://your-llm-endpoint.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=your-model-name

# MCP Server
MCP_URL=https://your-mcp-server.com/mcp/
```

**Optional:**
```env
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

See [.env.example](./.env.example) for complete configuration reference.

## 🧪 Testing

### CLI Testing

```bash
# Health check
python weather_cli.py health

# Get weather
python weather_cli.py weather "Seattle, WA"

# Get forecast
python weather_cli.py forecast "Austin, TX" --days 5

# Compare locations
python weather_cli.py compare "Seattle, WA" "Miami, FL"

# Interactive chat mode (requires LLM)
python weather_cli.py chat

# Cache management
python weather_cli.py cache stats
python weather_cli.py cache clear
```

### Demo Script

```bash
python demo.py
```

### UI Testing

1. Start API server: `uvicorn src.main:app --reload`
2. Start Redis: `redis-server`
3. Launch Streamlit: `streamlit run ui/weather_chat.py`
4. Click "Run Preflight Checks"
5. Try example queries

### Automated Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific tests
pytest tests/test_weather.py
```

## 🛠️ Development

### Project Structure

```
weather-agent/
├── src/                    # Source code
│   ├── agents/            # Agent implementations
│   ├── api/              # REST API
│   ├── core/             # Core framework
│   └── utilities/        # Utilities
├── ui/                    # Streamlit UI
├── manifests/            # Kubernetes/OpenShift configs
│   ├── base/             # Base manifests
│   └── overlays/         # Environment overlays
├── prompts/              # YAML prompt templates
├── scripts/              # Helper scripts
├── tests/                # Test suite
└── archive/              # Archived code

```

### Adding Features

1. Extend `WeatherAgent` class in `src/agents/weather_agent.py`
2. Add API endpoints in `src/api/weather_api.py`
3. Update UI in `ui/weather_chat.py`
4. Add tests in `tests/`
5. Test with CLI client

### Code Style

```bash
# Format code
black src/ tests/

# Lint
ruff check .

# Type checking
mypy src/
```

## 🔒 Security

- API keys stored in `.env` (never committed)
- `.gitignore` configured for secrets
- OpenShift Secrets for production
- TLS edge termination on routes
- CORS configuration for web clients

**Important:** Never commit `.env` files. Use `.env.example` as a template.

## 📊 Performance

- 15-minute cache TTL for weather data
- Redis-backed distributed caching
- Async operations throughout
- Connection pooling
- Graceful degradation
- Error recovery and retry logic

## 🚦 Status Indicators

- 🟢 **Green**: System fully operational
- 🟡 **Yellow**: Limited functionality (degraded)
- 🔴 **Red**: System unavailable

## 📚 Documentation

- **[README-OPENSHIFT.md](./README-OPENSHIFT.md)** - Detailed OpenShift deployment guide
- **[CLAUDE.md](./CLAUDE.md)** - Project development guidelines
- **[ui/README.md](./ui/README.md)** - UI-specific documentation

## 🔄 Scripts

- `scripts/deploy-openshift.sh` - Full OpenShift deployment
- `scripts/apply-secret.sh` - Update secrets from .env
- `scripts/rebuild-openshift.sh` - Quick rebuild for code changes
- `scripts/verify-deployment.sh` - Verify deployment health
- `ui/run.sh` - Launch Streamlit UI

## 📈 Future Enhancements

- [ ] Historical weather data
- [ ] Weather alerts and warnings
- [ ] Multi-language support
- [ ] Weather maps integration
- [ ] Predictive analytics
- [ ] Mobile app
- [ ] GraphQL API
- [ ] WebSocket support for real-time updates

## 🤝 Contributing

1. Follow existing code patterns
2. Add tests for new features (aim for 80%+ coverage)
3. Update documentation
4. Use type hints
5. Follow security best practices
6. Run linters and tests before committing

## 📝 License

[Your License Here]

## 🆘 Troubleshooting

### API Issues

```bash
# Check API logs
oc logs deployment/weather-agent-api -n weather-agent

# Test health endpoint
curl http://localhost:8000/health
```

### Redis Issues

```bash
# Test Redis connection
redis-cli ping

# Check Redis logs (OpenShift)
oc logs deployment/weather-agent-redis -n weather-agent
```

### MCP Connection Issues

1. Verify `MCP_URL` in `.env`
2. Check MCP server is accessible
3. Review API logs for connection errors

### Common Solutions

- **500 Errors**: Check LLM credentials in `.env`
- **Cache Issues**: Verify Redis is running
- **MCP Failures**: Confirm MCP server URL and accessibility
- **CrashLoopBackOff**: Check pod logs for missing dependencies

For detailed troubleshooting, see [README-OPENSHIFT.md](./README-OPENSHIFT.md#troubleshooting).

## 💬 Support

- Check logs in API console
- Review status indicators in UI
- Verify configuration in `.env`
- See troubleshooting sections in documentation
- File issues in repository
