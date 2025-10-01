#!/bin/bash

# Script to verify Weather Agent deployment status
# Usage: ./scripts/verify-deployment.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NAMESPACE="${NAMESPACE:-weather-agent}"

echo -e "${BLUE}🔍 Weather Agent Deployment Verification${NC}"
echo "========================================="
echo ""

# Check if logged in
if ! oc whoami &>/dev/null; then
    echo -e "${RED}❌ Not logged in to OpenShift${NC}"
    echo "Please login using: oc login <your-cluster-url>"
    exit 1
fi

echo -e "${GREEN}✅ Logged in as: $(oc whoami)${NC}"
echo -e "${BLUE}📍 Cluster: $(oc whoami --show-server)${NC}"
echo -e "${BLUE}📦 Namespace: $NAMESPACE${NC}"
echo ""

# Check namespace exists
if ! oc get namespace "$NAMESPACE" &>/dev/null; then
    echo -e "${RED}❌ Namespace $NAMESPACE does not exist${NC}"
    exit 1
fi

# Check pods
echo -e "${BLUE}📊 Pod Status:${NC}"
oc get pods -n "$NAMESPACE" -l app=weather-agent
echo ""

# Count ready pods
API_READY=$(oc get deployment weather-agent-api -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
UI_READY=$(oc get deployment weather-agent-ui -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
REDIS_READY=$(oc get deployment weather-agent-redis -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")

echo -e "${BLUE}🎯 Deployment Status:${NC}"

# Check API
if [ "$API_READY" -ge "1" ]; then
    echo -e "${GREEN}✅ API: $API_READY replicas ready${NC}"
else
    echo -e "${RED}❌ API: No replicas ready${NC}"
fi

# Check UI
if [ "$UI_READY" -ge "1" ]; then
    echo -e "${GREEN}✅ UI: $UI_READY replica ready${NC}"
else
    echo -e "${RED}❌ UI: No replicas ready${NC}"
fi

# Check Redis
if [ "$REDIS_READY" -ge "1" ]; then
    echo -e "${GREEN}✅ Redis: $REDIS_READY replica ready${NC}"
else
    echo -e "${RED}❌ Redis: No replicas ready${NC}"
fi

echo ""

# Check routes
echo -e "${BLUE}🌐 External Routes:${NC}"
API_ROUTE=$(oc get route weather-agent-api -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "Not found")
UI_ROUTE=$(oc get route weather-agent-ui -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "Not found")

if [ "$API_ROUTE" != "Not found" ]; then
    echo -e "${GREEN}✅ API: https://$API_ROUTE${NC}"
else
    echo -e "${RED}❌ API route not found${NC}"
fi

if [ "$UI_ROUTE" != "Not found" ]; then
    echo -e "${GREEN}✅ UI: https://$UI_ROUTE${NC}"
else
    echo -e "${RED}❌ UI route not found${NC}"
fi

echo ""

# Check secret configuration
echo -e "${BLUE}🔐 Secret Configuration:${NC}"
if oc get secret weather-agent-secrets -n "$NAMESPACE" &>/dev/null; then
    # Check if LLM is configured (not placeholder)
    LLM_URL_BASE64=$(oc get secret weather-agent-secrets -n "$NAMESPACE" -o jsonpath='{.data.LLM_URL}' 2>/dev/null)
    if [ -n "$LLM_URL_BASE64" ]; then
        LLM_URL=$(echo "$LLM_URL_BASE64" | base64 -d)
        if [[ "$LLM_URL" == *"YOUR_LLM"* ]] || [ -z "$LLM_URL" ]; then
            echo -e "${YELLOW}⚠️  LLM credentials not configured (using placeholders)${NC}"
            echo -e "${YELLOW}   Run: ./scripts/apply-secret.sh to update from .env${NC}"
        else
            echo -e "${GREEN}✅ LLM credentials configured${NC}"
        fi
    fi

    # Check MCP URL
    MCP_URL_BASE64=$(oc get secret weather-agent-secrets -n "$NAMESPACE" -o jsonpath='{.data.MCP_URL}' 2>/dev/null)
    if [ -n "$MCP_URL_BASE64" ]; then
        MCP_URL=$(echo "$MCP_URL_BASE64" | base64 -d)
        if [ -n "$MCP_URL" ]; then
            echo -e "${GREEN}✅ MCP server configured${NC}"
        else
            echo -e "${YELLOW}⚠️  MCP server not configured${NC}"
        fi
    fi
else
    echo -e "${RED}❌ Secrets not found${NC}"
    echo -e "${YELLOW}   Run: ./scripts/apply-secret.sh to create${NC}"
fi

echo ""

# Test API health
if [ "$API_ROUTE" != "Not found" ]; then
    echo -e "${BLUE}🏥 API Health Check:${NC}"
    if curl -sk "https://$API_ROUTE/health" --max-time 5 | grep -q "healthy"; then
        echo -e "${GREEN}✅ API is healthy${NC}"

        # Parse health response for more details
        HEALTH=$(curl -sk "https://$API_ROUTE/health" --max-time 5)
        if echo "$HEALTH" | grep -q '"mcp_connected":true'; then
            echo -e "${GREEN}   - MCP connected${NC}"
        else
            echo -e "${YELLOW}   - MCP not connected${NC}"
        fi

        if echo "$HEALTH" | grep -q '"llm_available":true'; then
            echo -e "${GREEN}   - LLM available${NC}"
        else
            echo -e "${YELLOW}   - LLM not available${NC}"
        fi
    else
        echo -e "${RED}❌ API health check failed${NC}"
        echo -e "${YELLOW}   Check logs: oc logs deployment/weather-agent-api -n $NAMESPACE${NC}"
    fi
fi

echo ""

# Summary
echo -e "${BLUE}📈 Deployment Summary:${NC}"
echo "========================"

TOTAL_ISSUES=0

# Check all components
if [ "$API_READY" -ge "1" ] && [ "$UI_READY" -ge "1" ] && [ "$REDIS_READY" -ge "1" ]; then
    echo -e "${GREEN}✅ All pods are running${NC}"
else
    echo -e "${RED}❌ Some pods are not ready${NC}"
    ((TOTAL_ISSUES++))
fi

if [ "$API_ROUTE" != "Not found" ] && [ "$UI_ROUTE" != "Not found" ]; then
    echo -e "${GREEN}✅ Routes are configured${NC}"
else
    echo -e "${RED}❌ Routes are missing${NC}"
    ((TOTAL_ISSUES++))
fi

if [[ "$LLM_URL" != *"YOUR_LLM"* ]] && [ -n "$LLM_URL" ]; then
    echo -e "${GREEN}✅ Secrets are configured${NC}"
else
    echo -e "${YELLOW}⚠️  Secrets need configuration${NC}"
    ((TOTAL_ISSUES++))
fi

echo ""

if [ "$TOTAL_ISSUES" -eq 0 ]; then
    echo -e "${GREEN}🎉 Deployment is fully operational!${NC}"
    echo ""
    echo -e "${BLUE}You can access the application at:${NC}"
    echo -e "  UI: ${GREEN}https://$UI_ROUTE${NC}"
    echo -e "  API: ${GREEN}https://$API_ROUTE${NC}"
else
    echo -e "${YELLOW}⚠️  Deployment needs attention ($TOTAL_ISSUES issues)${NC}"
    echo ""
    echo -e "${BLUE}Troubleshooting commands:${NC}"
    echo "  oc get pods -n $NAMESPACE"
    echo "  oc logs deployment/weather-agent-api -n $NAMESPACE"
    echo "  oc describe deployment weather-agent-api -n $NAMESPACE"
    echo "  ./scripts/apply-secret.sh  # Update secrets"
fi