#!/bin/bash

# Script to apply the weather-agent secret with values from .env file
# Usage: ./scripts/apply-secret.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Applying Weather Agent Secret to OpenShift${NC}"
echo "=========================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please create a .env file with your configuration values"
    exit 1
fi

# Source the .env file
source .env

# Check required variables
if [ -z "$LLM_URL" ] || [ -z "$LLM_API_KEY" ] || [ -z "$LLM_MODEL_NAME" ]; then
    echo -e "${RED}Error: Missing required LLM configuration in .env file${NC}"
    echo "Required variables: LLM_URL, LLM_API_KEY, LLM_MODEL_NAME"
    exit 1
fi

# Set default values
MCP_URL="${MCP_URL:-https://mcp-server-weather-mcp.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com/mcp/}"
MCP_TIMEOUT="${MCP_TIMEOUT:-30}"
API_SECRET_KEY="${API_SECRET_KEY:-weather-agent-secret-key-2024}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

# Create temporary file with substituted values
TEMP_FILE="/tmp/weather-agent-secret-filled.yaml"

cat manifests/openshift/common/secret.yaml | \
  sed "s|\${MCP_URL}|${MCP_URL}|g" | \
  sed "s|\${MCP_TIMEOUT}|${MCP_TIMEOUT}|g" | \
  sed "s|\${LLM_URL}|${LLM_URL}|g" | \
  sed "s|\${LLM_API_KEY}|${LLM_API_KEY}|g" | \
  sed "s|\${LLM_MODEL_NAME}|${LLM_MODEL_NAME}|g" | \
  sed "s|\${REDIS_PASSWORD}|${REDIS_PASSWORD}|g" | \
  sed "s|\${API_SECRET_KEY}|${API_SECRET_KEY}|g" > "${TEMP_FILE}"

# Show configuration (hiding sensitive data)
echo -e "${YELLOW}Applying secret with configuration:${NC}"
echo "  MCP_URL: ${MCP_URL}"
echo "  MCP_TIMEOUT: ${MCP_TIMEOUT}"
echo "  LLM_URL: ${LLM_URL}"
echo "  LLM_MODEL_NAME: ${LLM_MODEL_NAME}"
echo "  LLM_API_KEY: ****${LLM_API_KEY: -4}"
echo ""

# Apply the secret
echo -e "${BLUE}Applying secret to OpenShift...${NC}"
if oc apply -f "${TEMP_FILE}" -n weather-agent; then
    echo -e "${GREEN}✅ Secret applied successfully!${NC}"

    # Restart deployments to pick up new secret (if they exist)
    if oc get deployment weather-agent-api -n weather-agent &>/dev/null; then
        echo -e "${BLUE}Restarting API deployment to pick up new secret...${NC}"
        oc rollout restart deployment weather-agent-api -n weather-agent

        echo -e "${YELLOW}Waiting for rollout to complete...${NC}"
        if oc rollout status deployment weather-agent-api -n weather-agent --timeout=120s; then
            echo -e "${GREEN}✅ API deployment restarted successfully!${NC}"
        else
            echo -e "${YELLOW}⚠️  Rollout is taking longer than expected. Check status with:${NC}"
            echo "  oc rollout status deployment weather-agent-api -n weather-agent"
        fi
    else
        echo -e "${YELLOW}ℹ️  API deployment not found yet. Secrets will be used when deployment is created.${NC}"
    fi
else
    echo -e "${RED}❌ Failed to apply secret${NC}"
    exit 1
fi

# Clean up
rm -f "${TEMP_FILE}"

echo ""
echo -e "${GREEN}✨ Secret configuration complete!${NC}"
echo -e "${BLUE}You can verify the API is working with:${NC}"
echo "  curl -sk https://weather-agent-api-weather-agent.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com/health | jq"