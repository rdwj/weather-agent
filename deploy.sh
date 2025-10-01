#!/bin/bash

# Weather Agent Deployment Script
set -e

echo "================================"
echo "Weather Agent Deployment"
echo "================================"

# Check if logged into OpenShift
if ! oc whoami &>/dev/null; then
    echo "Error: Not logged into OpenShift. Please run 'oc login' first."
    exit 1
fi

# Get current context
CURRENT_PROJECT=$(oc project -q 2>/dev/null || echo "")
echo "Current project: ${CURRENT_PROJECT:-none}"

# Prompt for project name
read -p "Enter OpenShift project name [weather-agent]: " PROJECT_NAME
PROJECT_NAME=${PROJECT_NAME:-weather-agent}

# Prompt for MCP server URL
echo ""
echo "Enter the MCP Weather Server URL"
echo "Example: https://mcp-server-weather-mcp-3.apps.cluster-nl55d.nl55d.sandbox1207.opentlc.com"
read -p "MCP Server URL: " MCP_SERVER_URL

if [ -z "$MCP_SERVER_URL" ]; then
    echo "Error: MCP Server URL is required"
    exit 1
fi

# Create or switch to project
echo ""
echo "Setting up project: $PROJECT_NAME"
if oc get project "$PROJECT_NAME" &>/dev/null; then
    oc project "$PROJECT_NAME"
else
    oc new-project "$PROJECT_NAME" --display-name="Weather Agent" --description="Cloud-native weather agent with MCP integration"
fi

# Update ConfigMap with MCP server URL
echo ""
echo "Updating MCP server configuration..."
sed -i.bak "s|MCP_SERVER_URL:.*|MCP_SERVER_URL: $MCP_SERVER_URL|" manifests/base/configmap.yaml

# Apply Redis deployment
echo ""
echo "Deploying Redis..."
oc apply -f manifests/base/redis-deployment.yaml -n "$PROJECT_NAME"

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
oc wait --for=condition=Ready pod -l app=redis -n "$PROJECT_NAME" --timeout=60s || true

# Build container image
echo ""
echo "Building Weather Agent container..."
read -p "Build container locally with podman? (y/n) [y]: " BUILD_LOCAL
BUILD_LOCAL=${BUILD_LOCAL:-y}

if [[ "$BUILD_LOCAL" =~ ^[Yy]$ ]]; then
    echo "Building container image..."
    podman build --platform linux/amd64 -t weather-agent:latest -f Containerfile . --no-cache

    # Push to OpenShift internal registry
    echo ""
    echo "Pushing to OpenShift registry..."
    REGISTRY_URL=$(oc get route default-route -n openshift-image-registry -o jsonpath='{.spec.host}' 2>/dev/null || echo "image-registry.openshift-image-registry.svc:5000")

    # Tag and push
    podman tag weather-agent:latest "$REGISTRY_URL/$PROJECT_NAME/weather-agent:latest"
    podman login -u $(oc whoami) -p $(oc whoami -t) "$REGISTRY_URL" --tls-verify=false
    podman push "$REGISTRY_URL/$PROJECT_NAME/weather-agent:latest" --tls-verify=false
fi

# Apply all manifests
echo ""
echo "Applying Kubernetes manifests..."
oc apply -k manifests/base/ -n "$PROJECT_NAME"

# Update deployment to trigger rollout
echo ""
echo "Triggering deployment rollout..."
oc rollout restart deployment/weather-agent -n "$PROJECT_NAME"

# Wait for deployment
echo "Waiting for deployment to complete..."
oc rollout status deployment/weather-agent -n "$PROJECT_NAME" --timeout=300s

# Get route URL
echo ""
echo "================================"
echo "Deployment Complete!"
echo "================================"
ROUTE_URL=$(oc get route weather-agent -n "$PROJECT_NAME" -o jsonpath='{.spec.host}')
echo "Weather Agent URL: https://$ROUTE_URL"
echo ""
echo "Test endpoints:"
echo "  Health: curl -k https://$ROUTE_URL/health"
echo "  Ready:  curl -k https://$ROUTE_URL/ready"
echo ""
echo "To test weather queries:"
echo "  curl -X POST https://$ROUTE_URL/api/v1/weather/query \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"query\": \"What is the weather in San Francisco?\"}'"
echo ""
echo "To view logs:"
echo "  oc logs -f deployment/weather-agent -n $PROJECT_NAME"
echo ""
echo "To scale deployment:"
echo "  oc scale deployment/weather-agent --replicas=5 -n $PROJECT_NAME"
echo ""