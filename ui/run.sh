#!/bin/bash

# Weather Assistant UI Launch Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🌤️  Weather Assistant UI${NC}"
echo "=================================="
echo ""

# Check if virtual environment exists and activate it
if [ -d ".venv" ]; then
    echo -e "${GREEN}✓${NC} Activating virtual environment..."
    source .venv/bin/activate
elif [ -d "../.venv" ]; then
    echo -e "${GREEN}✓${NC} Activating virtual environment..."
    source ../.venv/bin/activate
else
    echo -e "${YELLOW}⚠${NC} No virtual environment found. Using system Python."
fi

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo -e "${RED}✗${NC} Streamlit is not installed!"
    echo "Please install it with: pip install streamlit"
    exit 1
fi

echo -e "${GREEN}✓${NC} Streamlit found"

# Check if API is running
API_URL="${WEATHER_API_URL:-http://localhost:8000}"
echo -e "\n${YELLOW}ℹ${NC} Checking API at $API_URL..."

if curl -s -f -o /dev/null "$API_URL/health" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} API is running"

    # Get API status details
    HEALTH=$(curl -s "$API_URL/health")
    echo ""
    echo "API Status:"
    echo "  • MCP Connected: $(echo $HEALTH | grep -o '"mcp_connected":[^,}]*' | cut -d: -f2)"
    echo "  • LLM Available: $(echo $HEALTH | grep -o '"llm_available":[^,}]*' | cut -d: -f2)"
else
    echo -e "${YELLOW}⚠${NC} API is not running or not accessible"
    echo ""
    echo "To start the API, run:"
    echo "  python -m uvicorn src.api.weather_api:app --reload --port 8000"
    echo ""
    echo -e "${YELLOW}Continuing anyway...${NC}"
fi

# Set Streamlit configuration
export STREAMLIT_SERVER_PORT="${STREAMLIT_PORT:-8501}"
export STREAMLIT_SERVER_ADDRESS="${STREAMLIT_ADDRESS:-localhost}"
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

echo ""
echo "=================================="
echo -e "${GREEN}Starting Streamlit UI...${NC}"
echo "=================================="
echo ""
echo "Configuration:"
echo "  • Port: $STREAMLIT_SERVER_PORT"
echo "  • Address: $STREAMLIT_SERVER_ADDRESS"
echo "  • API URL: $API_URL"
echo ""
echo -e "${GREEN}➜${NC} Opening browser at http://$STREAMLIT_SERVER_ADDRESS:$STREAMLIT_SERVER_PORT"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run Streamlit
streamlit run "$DIR/weather_chat.py" \
    --server.port "$STREAMLIT_SERVER_PORT" \
    --server.address "$STREAMLIT_SERVER_ADDRESS" \
    --theme.primaryColor="#6366f1" \
    --theme.backgroundColor="#ffffff" \
    --theme.secondaryBackgroundColor="#f7f7f7" \
    --theme.textColor="#333333"