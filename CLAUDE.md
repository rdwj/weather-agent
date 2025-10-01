# weather-agent Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-09-25

## Active Technologies

- Python 3.11 + FastAPI, LangChain, LangGraph, FastMCP v2, OpenTelemetry (001-cloud-native-weather)

## Project Structure

```text
src/
tests/
```

## Commands

```bash
# Development server
uvicorn src.main:app --reload --port 8000

# Run tests
pytest tests/
pytest --cov=src --cov-report=html

# Linting and formatting
ruff check .
black src/ tests/

# Type checking
mypy src/

# Container build
podman build --platform linux/amd64 -t weather-agent:latest -f Containerfile .
```

## Code Style

Python 3.11: Follow standard conventions

## Recent Changes

- 001-cloud-native-weather: Added Python 3.11 + FastAPI, LangChain, LangGraph, FastMCP v2, OpenTelemetry

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
- ## OpenShift/Kubernetes Namespace Usage

**IMPORTANT**: When working with OpenShift (`oc`) or Kubernetes (`kubectl`) commands, always use the `-n` or `--namespace` parameter instead of switching projects/contexts with `oc project` or `kubectl config set-context`. This prevents conflicts when multiple sessions are running concurrently.

### ❌ Avoid this approach:

```bash
oc project my-namespace
oc apply -f deployment.yaml
oc get pods
```

### ✅ Use this approach instead:

bash

```bash
oc apply -f deployment.yaml -n my-namespace
oc get pods -n my-namespace
oc logs my-pod -n my-namespace
```

### Best practices:

* Set a namespace variable at the start of scripts: `NAMESPACE="my-app"`
* Use the variable consistently: `oc get pods -n $NAMESPACE`
* Check/create namespace if needed: `oc get namespace $NAMESPACE || oc new-project $NAMESPACE`
* This applies to nearly all namespaced resources (pods, deployments, services, routes, configmaps, secrets)
* Cluster-scoped resources (nodes, PVs, cluster roles) don't need namespace parameters

This approach ensures multiple Claude Code sessions or scripts can run simultaneously without interfering with each other's namespace context.