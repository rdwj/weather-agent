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

### `./scripts/deploy-openshift.sh`
**Purpose:** Full deployment to OpenShift

**What it does:**
- Creates namespace if it doesn't exist
- Applies all manifests (deployments, services, routes, etc.)
- Creates BuildConfig and builds container image
- Applies secrets from `.env` file
- Sets up everything from scratch
- Verifies deployment health

**When to use:**
- ✅ First time deploying the project
- ✅ You've made changes to manifests (YAML files in `manifests/`)
- ✅ You want to ensure everything is properly configured
- ✅ Something is broken and you want to start fresh
- ✅ Setting up a new environment (dev/staging/prod)

**Example:**
```bash
./scripts/deploy-openshift.sh
```

### `./scripts/rebuild-openshift.sh`
**Purpose:** Quick rebuild for code changes

**What it does:**
- Deletes existing BuildConfig and ImageStream
- Creates new BuildConfig
- Triggers a fresh build from local code
- **Note:** Does NOT restart deployments automatically

**When to use:**
- ✅ You modified Python code (src/, agents/, ui/, etc.)
- ✅ You updated application logic
- ✅ You want the latest code deployed without touching infrastructure
- ❌ Don't use if you only changed environment variables (use `apply-secret.sh` instead)

**Important:** After running this script, you must restart the deployments:
```bash
./scripts/rebuild-openshift.sh

# Then restart deployments
oc rollout restart deployment weather-agent-api -n weather-agent
oc rollout restart deployment weather-agent-ui -n weather-agent

# Wait for rollout to complete
oc rollout status deployment weather-agent-api -n weather-agent
oc rollout status deployment weather-agent-ui -n weather-agent
```

### `./scripts/apply-secret.sh`
**Purpose:** Update secrets/environment variables only

**What it does:**
- Reads configuration from `.env` file
- Updates the `weather-agent-secret` in OpenShift
- Automatically restarts both API and UI deployments
- No code rebuild

**When to use:**
- ✅ You changed API keys (LLM_API_KEY, etc.)
- ✅ You updated MCP_URL
- ✅ You modified any environment variables in `.env`
- ✅ Rotating credentials
- ❌ Don't use if you also changed code (you'll need to rebuild)

**Example:**
```bash
# Edit your .env file
vim .env

# Apply the changes
./scripts/apply-secret.sh
```

### `./scripts/verify-deployment.sh`
**Purpose:** Verify deployment health and status

**What it does:**
- Checks namespace existence
- Verifies all pods are running
- Tests API health endpoint
- Shows routes and URLs
- Displays pod status and resource usage

**When to use:**
- ✅ After running any deployment script
- ✅ Troubleshooting deployment issues
- ✅ Verifying system is healthy
- ✅ Getting route URLs
- ✅ Checking pod status

**Example:**
```bash
./scripts/verify-deployment.sh
```

## Common Workflows

### Workflow 1: Code Changes Only

When you've modified Python code, UI code, or application logic:

```bash
# Step 1: Rebuild the container with new code
./scripts/rebuild-openshift.sh

# Step 2: Restart API deployment
oc rollout restart deployment weather-agent-api -n weather-agent

# Step 3: Restart UI deployment
oc rollout restart deployment weather-agent-ui -n weather-agent

# Step 4: Wait for rollout to complete
oc rollout status deployment weather-agent-api -n weather-agent
oc rollout status deployment weather-agent-ui -n weather-agent

# Step 5: Verify deployment
./scripts/verify-deployment.sh
```

### Workflow 2: Environment Variable Changes Only

When you've changed API keys, URLs, or other configuration:

```bash
# Step 1: Edit your .env file
vim .env

# Step 2: Apply secrets (restarts deployments automatically)
./scripts/apply-secret.sh

# Step 3: Verify deployment
./scripts/verify-deployment.sh
```

### Workflow 3: Code AND Environment Changes

When you've changed both code and configuration:

```bash
# Step 1: Rebuild container
./scripts/rebuild-openshift.sh

# Step 2: Apply updated secrets (restarts deployments automatically)
./scripts/apply-secret.sh

# Step 3: Verify deployment
./scripts/verify-deployment.sh
```

### Workflow 4: Complete Redeployment

When you need to deploy everything from scratch:

```bash
# Step 1: Full deployment (does everything)
./scripts/deploy-openshift.sh

# Step 2: Verify deployment (optional, deploy script does this)
./scripts/verify-deployment.sh
```

### Workflow 5: Manifest Changes

When you've modified Kubernetes manifests (YAML files):

```bash
# Apply specific manifest
oc apply -f manifests/openshift/api/deployment.yaml -n weather-agent

# Or redeploy everything
./scripts/deploy-openshift.sh
```

## Quick Reference

| Scenario | Script to Use | Additional Steps |
|----------|--------------|------------------|
| **First deployment** | `deploy-openshift.sh` | None |
| **Code changes** | `rebuild-openshift.sh` | Restart deployments manually |
| **Config changes** | `apply-secret.sh` | None (auto-restarts) |
| **Code + Config** | `rebuild-openshift.sh` + `apply-secret.sh` | None |
| **Manifest changes** | `deploy-openshift.sh` | None |
| **Check health** | `verify-deployment.sh` | None |

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

See the [Common Workflows](#common-workflows) section above for detailed instructions on:

- **Code changes only** - See Workflow 1
- **Environment variable changes** - See Workflow 2
- **Code AND environment changes** - See Workflow 3
- **Full redeployment** - See Workflow 4
- **Manifest changes** - See Workflow 5

Or reference the [Quick Reference](#quick-reference) table for a quick decision guide.

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