# Weather Agent - Customer Deployment Guide

## Pre-built FIPS-Compliant Image

This repository is configured to use a pre-built, FIPS-compliant container image from Quay.io:

```
quay.io/wjackson/agent-demos:weather-agent
```

## Why Pre-built Image?

The image is pre-built to ensure FIPS compliance and avoid "crypto circus" issues common with Python cryptography packages. The build process includes:

- **Red Hat UBI9** with FIPS-enabled OpenSSL 3.2.2
- **Cryptography library** built from source against FIPS OpenSSL
- **Removed unused dependencies** (python-jose) to simplify FIPS compliance
- **Tested FIPS mode** before distribution

## Quick Deployment

### Prerequisites

1. OpenShift cluster access with `oc` CLI logged in
2. Create a `.env` file with your credentials:

```bash
cp .env.example .env
# Edit .env with your MCP and LLM endpoints
```

### Deploy to OpenShift

```bash
# Create namespace
oc new-project weather-agent

# Apply secrets from .env
./scripts/apply-secret.sh

# Deploy all components
oc apply -f manifests/openshift/common/configmap.yaml
oc apply -f manifests/openshift/redis/deployment.yaml
oc apply -f manifests/openshift/api/deployment.yaml
oc apply -f manifests/openshift/ui/deployment.yaml

# Wait for deployment
oc rollout status deployment/weather-agent-api -n weather-agent

# Get route
oc get route weather-agent-api -n weather-agent
```

### Verify FIPS Mode

To verify the deployed image is running in FIPS mode:

```bash
oc exec -it deployment/weather-agent-api -n weather-agent -- \
  python -c "from cryptography.hazmat.backends.openssl import backend; \
  print(f'OpenSSL: {backend.openssl_version_text()}'); \
  print(f'FIPS enabled: {backend._fips_enabled}')"
```

Expected output:
```
OpenSSL: OpenSSL 3.2.2 6 Aug 2024
FIPS enabled: True
```

## Configuration

### Required Environment Variables

Set these in your `.env` file:

```bash
# MCP Server (required)
MCP_URL=https://your-weather-mcp-server.com/mcp/

# LLM (required for natural language features)
LLM_URL=https://your-llm-endpoint.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=your-model-name
```

### Optional Configuration

```bash
# Redis (optional, falls back to in-memory cache)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Logging
LOG_LEVEL=INFO

# Cache
CACHE_TTL=900
CACHE_TYPE=redis
```

## Image Details

### Tags Available

- `quay.io/wjackson/agent-demos:weather-agent` - Production image (recommended)
- `quay.io/wjackson/agent-demos:weather-agent-fips` - Same image with explicit FIPS tag

### Image Contents

- Base: `registry.access.redhat.com/ubi9/python-311:latest`
- Python: 3.11
- OpenSSL: 3.2.2 (FIPS-enabled)
- Cryptography: Built from source with FIPS support
- Dependencies: All from `requirements.txt` (python-jose removed)

### Security Features

- Non-root user (1001)
- Read-only root filesystem compatible
- Health checks included
- Minimal attack surface (no unnecessary packages)

## Updating the Image

When a new version is released, simply restart the deployment:

```bash
# Restart to pull latest image
oc rollout restart deployment/weather-agent-api -n weather-agent
oc rollout restart deployment/weather-agent-ui -n weather-agent

# Watch rollout
oc rollout status deployment/weather-agent-api -n weather-agent
```

## Troubleshooting

### Image Pull Failures

If OpenShift can't pull from Quay:

```bash
# Verify image exists and is public
podman pull quay.io/wjackson/agent-demos:weather-agent

# Check OpenShift can reach Quay
oc run test --image=quay.io/wjackson/agent-demos:weather-agent --restart=Never -n weather-agent
oc logs test -n weather-agent
oc delete pod test -n weather-agent
```

### FIPS Errors

If you see FIPS-related errors:

1. Ensure your OpenShift cluster has FIPS mode enabled at the node level
2. Check pod logs: `oc logs deployment/weather-agent-api -n weather-agent`
3. Verify OPENSSL_FIPS=1 is set (should be in image)

### Application Health

```bash
# Check health endpoint
API_ROUTE=$(oc get route weather-agent-api -n weather-agent -o jsonpath='{.spec.host}')
curl https://$API_ROUTE/health

# Expected response includes:
# - status: "healthy"
# - mcp_connected: true
# - llm_available: true (if LLM configured)
# - redis_connected: true (if Redis configured)
```

## Support

For issues with the pre-built image or deployment:

1. Check the main README.md for application details
2. Review OpenShift deployment logs
3. Verify all required environment variables are set
4. Ensure MCP server is accessible from OpenShift

## Building Your Own Image

If you need to customize the image or build locally, see `Containerfile.fips` for the FIPS-compliant build process.

```bash
# Build locally (requires Mac with --platform flag)
podman build --platform linux/amd64 \
  -t your-registry/weather-agent:custom \
  -f Containerfile.fips . \
  --no-cache

# Push to your registry
podman push your-registry/weather-agent:custom

# Update deployment to use your image
oc set image deployment/weather-agent-api \
  weather-agent-api=your-registry/weather-agent:custom \
  -n weather-agent
```
