#!/bin/bash

# Script to create Kubernetes secret from environment variables
# This keeps actual secrets out of git

set -e

NAMESPACE=${NAMESPACE:-weather-agent}

echo "Creating Kubernetes secret for Weather Agent"
echo "============================================="
echo ""

# Check for required environment variables
required_vars=(
    "LLM_URL"
    "LLM_API_KEY"
    "MCP_URL"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=($var)
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "ERROR: Missing required environment variables:"
    printf '  - %s\n' "${missing_vars[@]}"
    echo ""
    echo "Please set these variables in your .env file or export them:"
    echo "  export LLM_URL='your-llm-url'"
    echo "  export LLM_API_KEY='your-api-key'"
    echo "  export MCP_URL='your-mcp-server-url'"
    exit 1
fi

# Optional variables with defaults
LLM_MODEL_NAME=${LLM_MODEL_NAME:-"llama-4-scout-17b-16e-w4a16"}
MCP_TIMEOUT=${MCP_TIMEOUT:-"30"}
MCP_TRANSPORT=${MCP_TRANSPORT:-"streaming-http"}
REDIS_URL=${REDIS_URL:-"redis://redis:6379"}
ENV=${ENV:-"development"}
LOG_LEVEL=${LOG_LEVEL:-"INFO"}
CORS_ORIGINS=${CORS_ORIGINS:-"*"}

# Create the secret
echo "Creating secret 'weather-agent-secrets' in namespace '$NAMESPACE'..."

oc create secret generic weather-agent-secrets \
    --namespace=$NAMESPACE \
    --from-literal=LLM_URL="$LLM_URL" \
    --from-literal=LLM_MODEL_NAME="$LLM_MODEL_NAME" \
    --from-literal=LLM_API_KEY="$LLM_API_KEY" \
    --from-literal=MCP_URL="$MCP_URL" \
    --from-literal=MCP_TIMEOUT="$MCP_TIMEOUT" \
    --from-literal=MCP_TRANSPORT="$MCP_TRANSPORT" \
    --from-literal=REDIS_URL="$REDIS_URL" \
    --from-literal=ENV="$ENV" \
    --from-literal=LOG_LEVEL="$LOG_LEVEL" \
    --from-literal=LOG_REQUESTS="true" \
    --from-literal=LOG_REQUEST_BODY="true" \
    --from-literal=LOG_RESPONSE_BODY="false" \
    --from-literal=ACCESS_LOG="true" \
    --from-literal=CORS_ORIGINS="$CORS_ORIGINS" \
    --dry-run=client -o yaml | oc apply -f -

echo ""
echo "✅ Secret created/updated successfully!"
echo ""
echo "To verify:"
echo "  oc get secret weather-agent-secrets -n $NAMESPACE"
echo ""
echo "To view the secret (base64 encoded):"
echo "  oc get secret weather-agent-secrets -n $NAMESPACE -o yaml"