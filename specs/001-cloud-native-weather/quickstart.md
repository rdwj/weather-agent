# Quickstart Guide: Weather Agent

## Prerequisites
- Python 3.11+
- Redis running locally or accessible
- OpenShift CLI (oc) for deployment
- Weather MCP server endpoint configured

## Local Development Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd weather-agent
git checkout 001-cloud-native-weather
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env with your configuration:
# - WEATHER_MCP_URL=<mcp-server-endpoint>
# - REDIS_URL=redis://localhost:6379
# - OPENTELEMETRY_ENDPOINT=<optional>
```

### 5. Run Tests
```bash
# Run all tests to verify setup
pytest tests/

# Run with coverage
pytest --cov=src --cov-report=html
```

### 6. Start Local Server
```bash
# Development mode with auto-reload
uvicorn src.main:app --reload --port 8000

# Or using the CLI
python -m src.cli serve
```

### 7. Verify Health
```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy", "version": "1.0.0", ...}
```

## Testing the API

### Basic Weather Query
```bash
# Get auth token (local development uses mock auth)
export TOKEN="dev-token"

# Query weather
curl -X POST http://localhost:8000/api/v1/weather/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather like in San Francisco?"}'
```

### Follow-up Query with Context
```bash
# First query establishes location context
curl -X POST http://localhost:8000/api/v1/weather/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "How about tomorrow?"}'
# Should return tomorrow's forecast for San Francisco
```

### Check Weather Alerts
```bash
curl -X GET http://localhost:8000/api/v1/weather/alerts \
  -H "Authorization: Bearer $TOKEN"
```

### Update Preferences
```bash
curl -X PATCH http://localhost:8000/api/v1/session/preferences \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"temperature_unit": "Celsius"}'
```

### Monitor Multiple Locations
```bash
curl -X PUT http://localhost:8000/api/v1/session/locations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      {"display_name": "New York", "city": "New York", "country": "US"},
      {"display_name": "London", "city": "London", "country": "GB"},
      {"display_name": "Tokyo", "city": "Tokyo", "country": "JP"}
    ]
  }'
```

## OpenShift Deployment

### 1. Build Container
```bash
podman build --platform linux/amd64 -t weather-agent:latest -f Containerfile .
```

### 2. Login to OpenShift
```bash
oc login <openshift-cluster-url>
oc new-project weather-agent
```

### 3. Deploy Application
```bash
# Apply manifests
oc apply -k manifests/base/

# Or use overlays for different environments
oc apply -k manifests/overlays/development/
```

### 4. Configure Secrets
```bash
# Create secret for MCP server connection
oc create secret generic weather-mcp-config \
  --from-literal=MCP_URL=<mcp-server-url> \
  --from-literal=MCP_TOKEN=<optional-token>
```

### 5. Verify Deployment
```bash
# Check pod status
oc get pods -l app=weather-agent

# Check logs
oc logs -l app=weather-agent -f

# Get route
oc get route weather-agent -o jsonpath='{.spec.host}'
```

### 6. Test Production Endpoint
```bash
ROUTE=$(oc get route weather-agent -o jsonpath='{.spec.host}')
curl -X POST https://$ROUTE/api/v1/weather/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in Boston?"}'
```

## Validation Scenarios

### Scenario 1: Basic Weather Query
1. Send query: "What's the weather like in New York?"
2. Verify response includes:
   - Current temperature in Fahrenheit (default)
   - Weather conditions
   - Response time < 2 seconds

### Scenario 2: Context Retention
1. Query: "Weather in Paris"
2. Follow-up: "How about tomorrow?"
3. Verify tomorrow's forecast is for Paris

### Scenario 3: Cache Behavior
1. Query same location twice within 15 minutes
2. Second response should have `cache_hit: true`
3. Response time should be faster

### Scenario 4: Alert Detection
1. Set monitored location with active severe weather
2. Query alerts endpoint
3. Verify only severe/extreme alerts returned

### Scenario 5: Rate Limiting
1. Send 1001 requests in 1 minute
2. Verify 429 response with retry_after header
3. Wait specified time and retry successfully

### Scenario 6: Session Timeout
1. Create session with initial query
2. Wait 31 minutes
3. Send follow-up query
4. Verify context is lost (new session created)

## Troubleshooting

### MCP Connection Issues
```bash
# Test MCP server connectivity
python -m src.cli test-mcp

# Check MCP server logs
oc logs -l app=weather-mcp-server
```

### Redis Connection Issues
```bash
# Test Redis connectivity
redis-cli ping

# Check Redis memory usage
redis-cli info memory
```

### Performance Issues
```bash
# Check metrics endpoint
curl http://localhost:8000/api/v1/metrics

# Enable debug logging
export LOG_LEVEL=DEBUG
```

## Monitoring

### OpenTelemetry Traces
- Traces exported to configured OTLP endpoint
- View in Jaeger or OpenShift distributed tracing

### Metrics
- Prometheus metrics at `/metrics`
- Custom metrics for weather API calls
- Rate limit usage tracked

### Logs
- Structured JSON logging
- Correlation IDs for request tracing
- Error aggregation in OpenShift logging stack

## Next Steps
- Configure production OAuth2/OIDC
- Set up alerting rules
- Customize rate limits per environment
- Enable FIPS mode if required