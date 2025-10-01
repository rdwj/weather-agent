# Weather Assistant UI

A modern, sleek Streamlit-based chat interface for the Weather Agent.

## Features

✨ **Modern Chat Interface**
- Beautiful message bubbles with animations
- Real-time weather data display
- Responsive design

🎛️ **LLM Controls** (when LLM is configured)
- Temperature control (0.0 - 2.0)
- Top-K sampling (1 - 100)
- Top-P (nucleus) sampling (0.0 - 1.0)
- Max tokens control (50 - 2000)

📊 **System Status Dashboard**
- Real-time API connection status
- MCP server connection indicator
- LLM availability check
- Cache statistics
- Preflight checks button

⚡ **Quick Actions**
- Clear chat history
- Clear weather cache
- Example query buttons
- New chat session

## Prerequisites

1. Weather Agent API running on port 8000:
```bash
python -m uvicorn src.api.weather_api:app --reload --port 8000
```

2. Install Streamlit:
```bash
pip install streamlit
```

## Running the UI

### Option 1: Direct Python
```bash
streamlit run ui/weather_chat.py
```

### Option 2: Using the launch script
```bash
./ui/run.sh
```

### Option 3: Custom port
```bash
streamlit run ui/weather_chat.py --server.port 8501
```

## Environment Variables

```bash
# API endpoint (default: http://localhost:8000)
export WEATHER_API_URL=http://localhost:8000
```

## Usage

1. **Preflight Checks**: Click "Run Preflight Checks" in the sidebar to verify all systems are operational

2. **System Status**: Monitor the status indicators:
   - 🟢 Green = Connected/Available
   - 🔴 Red = Disconnected/Unavailable

3. **Ask Questions**: Type weather queries in the chat input:
   - "What's the weather in Seattle?"
   - "How's the temperature in New York?"
   - "Is it raining in London?"

4. **LLM Parameters**: When LLM is configured, adjust parameters for response generation:
   - Lower temperature = more focused responses
   - Higher temperature = more creative responses

## Features in Detail

### Preflight Checks
The app performs automatic checks on startup and can be manually triggered:
- API connectivity test
- MCP server connection verification
- LLM availability check
- Cache status retrieval

### Weather Data Display
When weather data is retrieved:
- Temperature, conditions, and humidity shown as metrics
- Wind information displayed when available
- Forecast shown in expandable section
- Cache status indicated for cached responses

### Smart Location Extraction
The app attempts to extract location names from natural language queries:
- Recognizes patterns like "weather in [city]"
- Handles state abbreviations (e.g., "Seattle, WA")
- Provides helpful prompts when location is unclear

### Error Handling
Graceful handling of various error conditions:
- API connection failures
- Missing LLM configuration
- MCP server unavailability
- Invalid location queries

## Troubleshooting

### "Cannot connect to Weather Agent API"
- Ensure the API is running on port 8000
- Check the WEATHER_API_URL environment variable
- Verify no firewall is blocking the connection

### "MCP Server Disconnected"
- Check the MCP server URL in the API configuration
- Verify the MCP server is accessible
- Review API logs for connection errors

### "LLM Not Available"
- This is normal if LLM is not configured
- Weather queries will still work using keyword matching
- To enable full chat: configure LLM_URL and LLM_API_KEY in .env

## UI Customization

The interface uses custom CSS for styling. Key style elements:
- Gradient purple theme for user messages and buttons
- Clean white assistant messages with subtle borders
- Animated status indicators with pulse effect
- Responsive layout that works on various screen sizes

## Development

To modify the UI:
1. Edit `ui/weather_chat.py`
2. Streamlit will auto-reload on save
3. Custom CSS is embedded in the markdown section

## Screenshots

The UI features:
- Clean, modern chat interface
- Sidebar with controls and status
- Weather data cards with metrics
- Example query buttons
- Real-time status indicators