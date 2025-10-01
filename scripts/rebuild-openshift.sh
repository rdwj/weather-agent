#!/bin/bash

# Quick rebuild script for OpenShift deployment
# Use this after fixing build issues

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NAMESPACE="${NAMESPACE:-weather-agent}"

echo -e "${BLUE}🔨 Rebuilding Weather Agent for OpenShift${NC}"
echo "====================================="

# Delete existing BuildConfig to start fresh
echo -e "${YELLOW}Cleaning up existing BuildConfig...${NC}"
oc delete buildconfig weather-agent -n "$NAMESPACE" 2>/dev/null || true
oc delete imagestream weather-agent -n "$NAMESPACE" 2>/dev/null || true

# Create new BuildConfig using the production Containerfile
echo -e "${BLUE}Creating new BuildConfig...${NC}"
cat <<EOF | oc apply -f - -n "$NAMESPACE"
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: weather-agent
  labels:
    app: weather-agent
spec:
  output:
    to:
      kind: ImageStreamTag
      name: weather-agent:latest
  source:
    type: Binary
    binary: {}
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: Containerfile.prod
  triggers: []
EOF

# Create ImageStream
cat <<EOF | oc apply -f - -n "$NAMESPACE"
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: weather-agent
  labels:
    app: weather-agent
spec:
  lookupPolicy:
    local: true
EOF

# Start the build
echo -e "${BLUE}Starting build...${NC}"
oc start-build weather-agent --from-dir=. --follow -n "$NAMESPACE"

# Tag images for API and UI
echo -e "${BLUE}Tagging images...${NC}"
oc tag weather-agent:latest weather-agent-api:latest -n "$NAMESPACE"
oc tag weather-agent:latest weather-agent-ui:latest -n "$NAMESPACE"

echo -e "${GREEN}✅ Build complete!${NC}"

# Now redeploy
echo -e "${BLUE}Redeploying components...${NC}"

# Delete existing deployments
oc delete deployment weather-agent-redis -n "$NAMESPACE" 2>/dev/null || true
oc delete deployment weather-agent-api -n "$NAMESPACE" 2>/dev/null || true
oc delete deployment weather-agent-ui -n "$NAMESPACE" 2>/dev/null || true

sleep 5

# Reapply deployments
oc apply -f manifests/openshift/redis/deployment.yaml -n "$NAMESPACE"
oc apply -f manifests/openshift/api/deployment.yaml -n "$NAMESPACE"
oc apply -f manifests/openshift/ui/deployment.yaml -n "$NAMESPACE"

# Wait for rollouts
echo -e "${YELLOW}Waiting for deployments...${NC}"
oc rollout status deployment/weather-agent-redis -n "$NAMESPACE" --timeout=300s
oc rollout status deployment/weather-agent-api -n "$NAMESPACE" --timeout=300s
oc rollout status deployment/weather-agent-ui -n "$NAMESPACE" --timeout=300s

# Get URLs
API_URL=$(oc get route weather-agent-api -n "$NAMESPACE" -o jsonpath='https://{.spec.host}')
UI_URL=$(oc get route weather-agent-ui -n "$NAMESPACE" -o jsonpath='https://{.spec.host}')

echo -e "${GREEN}✨ Deployment Complete!${NC}"
echo -e "${GREEN}API: $API_URL${NC}"
echo -e "${GREEN}UI: $UI_URL${NC}"