# Weather Agent OpenShift Deployment

This directory contains all the manifests and configuration needed to deploy the Weather Agent application to Red Hat OpenShift.

## Architecture

The deployment consists of three main components:

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Redis     │────▶│  Weather API │────▶│   MCP Server │
│   Cache     │     │   (FastAPI)  │     │   (Weather)  │
└─────────────┘     └──────────────┘     └──────────────┘
                           ▲
                           │
                    ┌──────────────┐
                    │   Weather UI │
                    │  (Streamlit)  │
                    └──────────────┘
```

## Components

### 1. **Weather Agent API** (`api/`)
- FastAPI REST service
- Handles all weather operations
- Integrates with MCP server
- Uses Redis for distributed caching
- 2 replicas for high availability
- Health and readiness probes
- External route with TLS

### 2. **Weather Agent UI** (`ui/`)
- Streamlit chat interface
- Connects to internal API service
- Single replica (stateless)
- External route with TLS
- Session affinity for WebSocket

### 3. **Redis Cache** (`redis/`)
- Distributed caching layer
- Shared between API replicas
- 15-minute TTL for weather data
- Optional password protection

### 4. **Common Resources** (`common/`)
- ConfigMap for application configuration
- Secrets template for sensitive data
- Shared across all components

## Prerequisites

- OpenShift CLI (`oc`) installed
- Access to an OpenShift cluster
- Logged in to OpenShift (`oc login`)
- Podman or Docker (for local builds)

## Quick Start

### Automated Deployment

Use the provided deployment script:

```bash
# Make script executable
chmod +x scripts/deploy-openshift.sh

# Run deployment
./scripts/deploy-openshift.sh
```

The script will:
1. Create namespace
2. Build and push container images
3. Create secrets (prompts for values)
4. Deploy all components
5. Wait for readiness
6. Run smoke tests

### Manual Deployment

#### 1. Create Namespace

```bash
export NAMESPACE=weather-agent
oc new-project $NAMESPACE
```

#### 2. Build Container Image

Using OpenShift BuildConfig:
```bash
# Create build config
oc new-build --binary --name=weather-agent \
    --image-stream=openshift/python:3.11-ubi9 \
    -n $NAMESPACE

# Start build
oc start-build weather-agent --from-dir=. --follow -n $NAMESPACE

# Tag for components
oc tag weather-agent:latest weather-agent-api:latest -n $NAMESPACE
oc tag weather-agent:latest weather-agent-ui:latest -n $NAMESPACE
```

Or using Podman:
```bash
# Build image
podman build --platform linux/amd64 \
    -t weather-agent:latest \
    -f Containerfile.prod .

# Push to registry
podman push weather-agent:latest <your-registry>/weather-agent:latest
```

#### 3. Create Secrets

```bash
# Copy template
cp common/secret-template.yaml /tmp/secrets.yaml

# Edit with your values
vi /tmp/secrets.yaml

# Apply secrets
oc apply -f /tmp/secrets.yaml -n $NAMESPACE
```

Required secrets:
- `MCP_URL`: Your MCP server endpoint
- `LLM_URL`: (Optional) LLM endpoint for full features
- `LLM_API_KEY`: (Optional) LLM API key
- `API_SECRET_KEY`: Generate a secure key

#### 4. Deploy Components

Using Kustomize:
```bash
oc apply -k manifests/openshift/ -n $NAMESPACE
```

Or individually:
```bash
# Deploy ConfigMap
oc apply -f common/configmap.yaml -n $NAMESPACE

# Deploy Redis
oc apply -f redis/deployment.yaml -n $NAMESPACE

# Deploy API
oc apply -f api/deployment.yaml -n $NAMESPACE

# Deploy UI
oc apply -f ui/deployment.yaml -n $NAMESPACE
```

#### 5. Wait for Deployment

```bash
# Check pod status
oc get pods -n $NAMESPACE -l app=weather-agent

# Wait for deployments
oc rollout status deployment/weather-agent-redis -n $NAMESPACE
oc rollout status deployment/weather-agent-api -n $NAMESPACE
oc rollout status deployment/weather-agent-ui -n $NAMESPACE
```

#### 6. Get URLs

```bash
# Get routes
oc get routes -n $NAMESPACE

# Get specific URLs
API_URL=$(oc get route weather-agent-api -n $NAMESPACE -o jsonpath='https://{.spec.host}')
UI_URL=$(oc get route weather-agent-ui -n $NAMESPACE -o jsonpath='https://{.spec.host}')

echo "API: $API_URL"
echo "UI: $UI_URL"
```

## Configuration

### Environment Variables

Configure via `common/configmap.yaml`:
- `API_PORT`: API server port (8000)
- `STREAMLIT_SERVER_PORT`: UI port (8501)
- `CACHE_TYPE`: Cache backend (redis/memory)
- `CACHE_TTL`: Cache TTL in seconds (900)
- `LOG_LEVEL`: Logging level (INFO)
- `CORS_ORIGINS`: CORS allowed origins

### Scaling

```bash
# Scale API replicas
oc scale deployment/weather-agent-api --replicas=3 -n $NAMESPACE

# Scale UI (not recommended >1 due to sessions)
oc scale deployment/weather-agent-ui --replicas=1 -n $NAMESPACE
```

### Resource Limits

Adjust in deployment files:
- API: 512Mi-1Gi memory, 250m-1000m CPU
- UI: 256Mi-512Mi memory, 100m-500m CPU
- Redis: 256Mi-512Mi memory, 100m-500m CPU

## Monitoring

### Health Checks

```bash
# Check API health
curl https://<api-route>/health

# Check cache stats
curl https://<api-route>/cache/stats
```

### Logs

```bash
# API logs
oc logs -f deployment/weather-agent-api -n $NAMESPACE

# UI logs
oc logs -f deployment/weather-agent-ui -n $NAMESPACE

# Redis logs
oc logs -f deployment/weather-agent-redis -n $NAMESPACE
```

### Metrics

The API exposes Prometheus metrics at `/metrics`:
- Request counts
- Response times
- Cache hit rates
- Error rates

## Troubleshooting

### Pods Not Starting

```bash
# Check pod events
oc describe pod <pod-name> -n $NAMESPACE

# Check logs
oc logs <pod-name> -n $NAMESPACE
```

### Connection Issues

1. Check services:
```bash
oc get svc -n $NAMESPACE
```

2. Test internal connectivity:
```bash
oc exec -it <api-pod> -n $NAMESPACE -- curl http://weather-agent-redis:6379
```

3. Check routes:
```bash
oc describe route weather-agent-api -n $NAMESPACE
```

### Redis Connection Failed

1. Check Redis pod:
```bash
oc get pod -l component=redis -n $NAMESPACE
```

2. Test Redis:
```bash
oc exec -it <redis-pod> -n $NAMESPACE -- redis-cli ping
```

### MCP Server Unavailable

1. Verify MCP_URL in secrets:
```bash
oc get secret weather-agent-secrets -n $NAMESPACE -o yaml
```

2. Test connectivity:
```bash
oc exec -it <api-pod> -n $NAMESPACE -- curl -v $MCP_URL/health
```

## Production Considerations

### Security

- [ ] Use network policies to restrict traffic
- [ ] Enable RBAC for service accounts
- [ ] Rotate secrets regularly
- [ ] Use sealed secrets or external secret management
- [ ] Enable audit logging

### High Availability

- [ ] Deploy across multiple availability zones
- [ ] Use PodDisruptionBudgets
- [ ] Configure HorizontalPodAutoscaler
- [ ] Implement circuit breakers
- [ ] Set up health monitoring alerts

### Persistence

- [ ] Use PersistentVolume for Redis data
- [ ] Configure Redis persistence (AOF/RDB)
- [ ] Set up regular backups
- [ ] Test disaster recovery

### Performance

- [ ] Enable Redis clustering for large scale
- [ ] Configure connection pooling
- [ ] Optimize container images
- [ ] Use CDN for static assets
- [ ] Implement rate limiting

## GitOps with ArgoCD

To deploy using ArgoCD:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: weather-agent
  namespace: argocd
spec:
  destination:
    namespace: weather-agent
    server: https://kubernetes.default.svc
  project: default
  source:
    path: manifests/openshift
    repoURL: https://github.com/your-org/weather-agent
    targetRevision: main
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

## Support

For issues or questions:
1. Check pod logs
2. Review events: `oc get events -n $NAMESPACE`
3. Check route status
4. Verify secret configuration
5. Test API endpoints directly