# Weather Agent - OpenShift Deployment Guide

## Overview

The Weather Agent is an intelligent weather assistant that combines MCP (Model Context Protocol) servers with LLM capabilities to provide detailed weather information and analysis. This guide covers deploying the application to Red Hat OpenShift.

## Architecture

The application consists of three main components:

- **weather-agent-api**: FastAPI backend with embedded Weather Agent logic (2 replicas)
- **weather-agent-ui**: Streamlit frontend for user interaction (1 replica)
- **weather-agent-redis**: Redis cache for distributed state management (1 replica)

## Prerequisites

Before deploying, ensure you have:

1. **OpenShift CLI (oc)** installed and configured
2. **Access to an OpenShift cluster** with appropriate permissions
3. **MCP Weather Server** deployed (or use the existing one)
4. **LLM API credentials** (OpenAI-compatible endpoint)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd weather-agent
```

### 2. Configure Environment Variables

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# Required: LLM Configuration
LLM_URL=https://your-llm-endpoint.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=your-model-name

# Optional: MCP Configuration (defaults provided)
MCP_URL=https://your-mcp-server.com/mcp/
MCP_TIMEOUT=30

# Optional: Redis Configuration
REDIS_PASSWORD=  # Leave empty for no auth

# Optional: API Security
API_SECRET_KEY=your-secret-key  # Will generate if not provided
```

### 3. Deploy to OpenShift

Run the deployment script:

```bash
./scripts/deploy-openshift.sh
```

This script will:
- Create the namespace (if needed)
- Build and push container images
- Apply all Kubernetes manifests
- Configure secrets from your `.env` file
- Set up routes for external access
- Verify deployment health

## Detailed Deployment Steps

If you prefer manual deployment or need to customize:

### Step 1: Login to OpenShift

```bash
oc login <your-cluster-url>
```

### Step 2: Create/Select Namespace

```bash
# Create new namespace
oc new-project weather-agent --display-name="Weather Agent" \
  --description="Intelligent Weather Assistant with MCP Integration"

# Or use existing namespace
oc project weather-agent
```

### Step 3: Apply Secrets

Configure and apply secrets from your `.env` file:

```bash
./scripts/apply-secret.sh
```

This script:
- Reads configuration from `.env`
- Substitutes values in the secret template
- Applies the secret to OpenShift
- Restarts deployments to pick up new values

### Step 4: Deploy Components

```bash
# Deploy common resources (ConfigMap)
oc apply -f manifests/openshift/common/configmap.yaml -n weather-agent

# Deploy Redis cache
oc apply -f manifests/openshift/redis/deployment.yaml -n weather-agent

# Deploy API
oc apply -f manifests/openshift/api/deployment.yaml -n weather-agent

# Deploy UI
oc apply -f manifests/openshift/ui/deployment.yaml -n weather-agent
```

### Step 5: Verify Deployment

Check pod status:

```bash
oc get pods -n weather-agent -l app=weather-agent
```

Get route URLs:

```bash
oc get routes -n weather-agent
```

## Configuration Reference

### Required Secrets

| Secret Key | Description | Example |
|------------|-------------|---------|
| `LLM_URL` | LLM API endpoint URL | `https://api.openai.com/v1` |
| `LLM_API_KEY` | Authentication key for LLM | `sk-...` |
| `LLM_MODEL_NAME` | Model to use for completions | `gpt-4` |
| `MCP_URL` | MCP server endpoint | `https://mcp-server/mcp/` |

### Optional Configuration

| Config Key | Description | Default |
|------------|-------------|---------|
| `MCP_TIMEOUT` | MCP request timeout (seconds) | `30` |
| `REDIS_PASSWORD` | Redis authentication | (empty) |
| `API_SECRET_KEY` | JWT signing key | (generated) |
| `LOG_LEVEL` | Application log level | `INFO` |
| `CACHE_TTL` | Cache expiration (seconds) | `3600` |

## Available Scripts

### `scripts/deploy-openshift.sh`
Full deployment script with interactive prompts. Handles everything from namespace creation to health checks.

### `scripts/apply-secret.sh`
Updates secrets from `.env` file and restarts deployments. Use this when you need to update credentials.

### `scripts/rebuild-openshift.sh`
Quick rebuild for code changes. Rebuilds images and redeploys without recreating the entire infrastructure.

## Troubleshooting

### Check Pod Logs

```bash
# API logs
oc logs deployment/weather-agent-api -n weather-agent

# UI logs
oc logs deployment/weather-agent-ui -n weather-agent

# Redis logs
oc logs deployment/weather-agent-redis -n weather-agent
```

### Common Issues

#### 1. API Returns 500 Error
- **Cause**: Usually missing or incorrect LLM credentials
- **Solution**: Run `./scripts/apply-secret.sh` after updating `.env`

#### 2. MCP Connection Failed
- **Cause**: MCP server not accessible or wrong URL
- **Solution**: Verify MCP_URL in `.env` and that the MCP server is running

#### 3. Redis Connection Issues
- **Cause**: Redis pod not ready or password mismatch
- **Solution**: Check Redis pod status and ensure REDIS_PASSWORD matches

#### 4. Pods in CrashLoopBackOff
- **Cause**: Missing dependencies or configuration
- **Solution**: Check logs with `oc logs <pod-name> -n weather-agent`

### Verify Health

```bash
# Check API health
curl -k https://<api-route>/health | jq

# Test chat functionality
curl -k -X POST https://<api-route>/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather in Seattle?"}' | jq
```

## Updating the Application

### Update Code Only

```bash
# Make code changes, then:
./scripts/rebuild-openshift.sh
```

### Update Configuration

```bash
# Edit .env file, then:
./scripts/apply-secret.sh
```

### Full Redeployment

```bash
./scripts/deploy-openshift.sh
```

## Cleanup

To remove the application:

```bash
# Delete all resources
oc delete project weather-agent

# Or keep namespace and delete resources
oc delete all -l app=weather-agent -n weather-agent
oc delete configmap weather-agent-config -n weather-agent
oc delete secret weather-agent-secrets -n weather-agent
```

## Security Considerations

1. **Never commit `.env` files** - Use `.env.example` as a template
2. **Rotate API keys regularly** - Update with `./scripts/apply-secret.sh`
3. **Use network policies** - Restrict traffic between pods
4. **Enable RBAC** - Limit permissions to necessary operations
5. **Use secure routes** - All routes use TLS edge termination

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review pod logs for detailed error messages
3. Ensure all prerequisites are met
4. Verify network connectivity to external services

## License

[Your License Here]