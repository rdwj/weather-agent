# Weather Agent - Current Deployment

## 📍 Deployment Information

**Date:** October 1, 2025
**Cluster:** cluster-sdzgj.sdzgj.sandbox319.opentlc.com
**Namespace:** weather-agent
**Status:** 🟢 Production Ready

---

## 🌐 Deployed Resources

### Pods (All Running)
- **weather-agent-api** (2 replicas) - API service with MCP integration
- **weather-agent-redis** (1 replica) - Redis cache backend
- **weather-agent-ui** (1 replica) - Streamlit chat interface

### Services
- **weather-agent-api:** ClusterIP 172.30.211.180:8000
- **weather-agent-redis:** ClusterIP 172.30.243.190:6379
- **weather-agent-ui:** ClusterIP 172.30.182.228:8501

### Routes (HTTPS)
- **API:** https://weather-agent-api-weather-agent.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com
- **UI:** https://weather-agent-ui-weather-agent.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com

---

## ✅ Health Status

```json
{
    "status": "healthy",
    "mcp_connected": true,
    "llm_available": true,
    "cache_stats": {
        "backend": "MemoryCacheBackend",
        "initialized": true,
        "type": "redis",
        "entries": 0
    }
}
```

### System Status
- ✅ **MCP Connected:** Successfully connected to weather-mcp server
- ✅ **LLM Available:** LLM client configured and operational
- ✅ **Cache Ready:** Redis cache backend initialized
- ✅ **API Responsive:** All endpoints returning successfully

---

## 🔗 Access Information

### API Endpoints

**Base URL:** `https://weather-agent-api-weather-agent.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health check |
| `/weather` | GET | Get weather for location |
| `/weather/compare` | POST | Compare multiple locations |
| `/forecast` | GET | Get weather forecast |
| `/chat` | POST | Natural language chat |
| `/tools` | GET | List available MCP tools |
| `/docs` | GET | Interactive API documentation |

### Example API Calls

```bash
# Health check
curl https://weather-agent-api-weather-agent.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com/health

# Get weather for a location
curl "https://weather-agent-api-weather-agent.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com/weather?location=Seattle,%20WA"

# Compare multiple locations
curl -X POST https://weather-agent-api-weather-agent.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com/weather/compare \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Seattle, WA", "Austin, TX", "Miami, FL"]}'

# Get forecast
curl "https://weather-agent-api-weather-agent.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com/forecast?location=Portland,%20OR&days=5"
```

### User Interface

**URL:** https://weather-agent-ui-weather-agent.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com

The Streamlit chat interface provides:
- Natural language weather queries
- Real-time status indicators
- LLM parameter controls
- Preflight system checks
- Weather data visualization

---

## 🔍 Monitoring & Management

### Check Pod Status
```bash
oc get pods -n weather-agent -l app=weather-agent
```

### View API Logs
```bash
oc logs -n weather-agent deployment/weather-agent-api -f
```

### Check MCP Connection
```bash
oc logs -n weather-agent deployment/weather-agent-api | grep -E "(MCP|connected)"
```

### Restart Deployment
```bash
oc rollout restart deployment/weather-agent-api -n weather-agent
```

### Scale API Replicas
```bash
oc scale deployment/weather-agent-api --replicas=3 -n weather-agent
```

---

## 📊 Deployment Architecture

```
┌──────────────────────────────────────────────────────┐
│              OpenShift Cluster                        │
│                                                        │
│  ┌────────────────────────────────────────────────┐  │
│  │       weather-agent namespace                   │  │
│  │                                                  │  │
│  │  ┌─────────────┐      ┌──────────────────────┐│  │
│  │  │weather-agent│◄─────┤  weather-agent-api   ││  │
│  │  │     -ui     │      │      (x2 pods)       ││  │
│  │  │ (Streamlit) │      │     (FastAPI)        ││  │
│  │  └─────────────┘      └──────────┬───────────┘│  │
│  │                                   │            │  │
│  │                          ┌────────▼──────────┐ │  │
│  │                          │ weather-agent     │ │  │
│  │                          │     -redis        │ │  │
│  │                          │    (Cache)        │ │  │
│  │                          └───────────────────┘ │  │
│  │                                   │            │  │
│  └───────────────────────────────────┼────────────┘  │
│                                      │               │
│  ┌───────────────────────────────────▼───────────┐  │
│  │        weather-mcp namespace                   │  │
│  │                                                 │  │
│  │  ┌───────────────────────────────────────────┐│  │
│  │  │  mcp-server (FastMCP v2)                  ││  │
│  │  │  - Weather.gov API Integration            ││  │
│  │  │  - Geocoding Service                      ││  │
│  │  │  - MCP Tools, Prompts, Resources          ││  │
│  │  └───────────────────────────────────────────┘│  │
│  └─────────────────────────────────────────────────┘  │
│                                                        │
└──────────────────────────────────────────────────────┘
```

---

## 🎯 Getting Started

### Access the UI
1. Visit https://weather-agent-ui-weather-agent.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com
2. Click "Run Preflight Checks" to verify system health
3. Try example queries or enter your own weather questions

### Use the API
1. Visit https://weather-agent-api-weather-agent.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com/docs for interactive documentation
2. Test endpoints directly in the browser
3. Or use curl/httpie from the command line

### Monitor the System
1. Check health endpoint: `/health`
2. View cache stats: `/cache/stats`
3. List available tools: `/tools`

---

## 🔧 Configuration

The deployment is configured via OpenShift secrets containing:

- **LLM_URL:** LLM endpoint for analysis features
- **LLM_API_KEY:** LLM authentication
- **LLM_MODEL_NAME:** Model identifier
- **MCP_URL:** Weather MCP server endpoint
- **REDIS_PASSWORD:** Redis authentication (if configured)

To update configuration:
```bash
# Edit .env file locally
vim .env

# Apply updated secrets
./scripts/apply-secret.sh
```

---

## 📈 Performance Metrics

- **Cache TTL:** 15 minutes for weather data
- **API Replicas:** 2 (for high availability)
- **Response Time:** ~200-500ms for cached queries
- **MCP Connection:** Persistent HTTP connection with keep-alive

---

## 🚨 Troubleshooting

### API Not Responding
```bash
# Check pod status
oc get pods -n weather-agent

# View logs
oc logs -n weather-agent deployment/weather-agent-api --tail=50

# Restart if needed
oc rollout restart deployment/weather-agent-api -n weather-agent
```

### MCP Connection Issues
```bash
# Verify MCP server is accessible
curl https://mcp-server-weather-mcp.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com/mcp/

# Check API logs for connection errors
oc logs -n weather-agent deployment/weather-agent-api | grep MCP
```

### Redis Cache Issues
```bash
# Check Redis pod
oc get pods -n weather-agent -l app=weather-agent,component=redis

# View Redis logs
oc logs -n weather-agent deployment/weather-agent-redis

# Clear cache via API
curl -X POST https://weather-agent-api-weather-agent.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com/cache/clear
```

---

## 📝 Deployment Notes

- Built using OpenShift BuildConfig with Red Hat UBI9 Python 3.11 base image
- Uses OpenShift Routes for HTTPS with edge termination
- Redis provides distributed caching across API replicas
- MCP integration enables real-time weather data access
- Secrets managed via OpenShift Secrets resource

For detailed deployment instructions, see [README-OPENSHIFT.md](./README-OPENSHIFT.md).

---

## 📚 Additional Documentation

- **[README.md](./README.md)** - Main project documentation
- **[README-OPENSHIFT.md](./README-OPENSHIFT.md)** - OpenShift deployment guide
- **[CONTRIBUTING.md](./CONTRIBUTING.md)** - Contributing guidelines
- **[CLAUDE.md](./CLAUDE.md)** - Development guidelines

---

**Last Updated:** October 1, 2025
