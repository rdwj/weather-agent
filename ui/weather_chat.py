#!/usr/bin/env python3
"""
Modern Chat Interface for Weather Agent
A sleek Streamlit app for interacting with the Weather Assistant
"""

import streamlit as st
import httpx
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import os
import asyncio
import time

# Configuration
API_URL = os.getenv("WEATHER_API_URL", "http://localhost:8000")

# Page configuration
st.set_page_config(
    page_title="Weather Assistant",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern chat interface
st.markdown("""
<style>
    /* Main container styling */
    .main {
        padding-top: 0rem;
    }

    /* Chat container */
    .chat-container {
        height: calc(100vh - 200px);
        overflow-y: auto;
        padding: 20px;
        background: linear-gradient(to bottom, #f7f7f7, #ffffff);
        border-radius: 10px;
        margin-bottom: 20px;
    }

    /* Message bubbles */
    .user-message {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white;
        padding: 12px 18px;
        border-radius: 18px;
        margin: 10px 0;
        max-width: 70%;
        margin-left: auto;
        margin-right: 0;
        word-wrap: break-word;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        animation: slideInRight 0.3s ease-out;
    }

    .assistant-message {
        background: white;
        color: #333;
        padding: 12px 18px;
        border-radius: 18px;
        margin: 10px 0;
        max-width: 70%;
        margin-left: 0;
        margin-right: auto;
        word-wrap: break-word;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        border: 1px solid #e0e0e0;
        animation: slideInLeft 0.3s ease-out;
    }

    /* Animations */
    @keyframes slideInRight {
        from {
            transform: translateX(20px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideInLeft {
        from {
            transform: translateX(-20px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    /* Message metadata */
    .message-time {
        font-size: 0.75em;
        color: #999;
        margin-top: 4px;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #2b2d42;
    }

    section[data-testid="stSidebar"] .stMarkdown {
        color: #e0e0e0;
    }

    section[data-testid="stSidebar"] label {
        color: #e0e0e0 !important;
    }

    /* Button styling */
    .stButton > button {
        border-radius: 25px;
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white;
        border: none;
        padding: 10px 24px;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(99, 102, 241, 0.3);
    }

    /* Status indicators */
    .status-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 8px;
    }

    .status-online {
        background: #4caf50;
        animation: pulse 2s infinite;
    }

    .status-offline {
        background: #f44336;
    }

    .status-warning {
        background: #ff9800;
    }

    @keyframes pulse {
        0% {
            box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.4);
        }
        70% {
            box-shadow: 0 0 0 10px rgba(76, 175, 80, 0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(76, 175, 80, 0);
        }
    }

    /* Weather card styling */
    .weather-card {
        background: white;
        border-radius: 10px;
        padding: 15px;
        margin-top: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }

    /* Header styling */
    .header-container {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []
if 'thread_id' not in st.session_state:
    st.session_state.thread_id = None
if 'system_status' not in st.session_state:
    st.session_state.system_status = {}
if 'llm_params' not in st.session_state:
    st.session_state.llm_params = {
        'temperature': 0.7,
        'top_k': 50,
        'top_p': 0.9,
        'max_tokens': 500
    }

def call_api(endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> Dict[str, Any]:
    """Call the Weather Agent API."""
    try:
        url = f"{API_URL}{endpoint}"

        with httpx.Client(timeout=timeout) as client:
            if method == "POST":
                response = client.post(url, json=data)
            else:
                response = client.get(url)

            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        return {"error": "Cannot connect to Weather Agent API. Please ensure the service is running."}
    except httpx.ReadTimeout:
        return {"error": "Request timed out. The query might be too complex. Please try again with a simpler question."}
    except httpx.HTTPStatusError as e:
        return {"error": f"API error: {e.response.status_code}"}
    except Exception as e:
        return {"error": f"API call failed: {str(e)}"}

def check_system_status():
    """Check system status and update state."""
    health = call_api("/health")

    if "error" not in health:
        st.session_state.system_status = {
            "api": health.get("status") == "healthy",
            "mcp": health.get("mcp_connected", False),
            "llm": health.get("llm_available", False),
            "cache_entries": health.get("cache_stats", {}).get("entries", 0)
        }
    else:
        st.session_state.system_status = {
            "api": False,
            "mcp": False,
            "llm": False,
            "cache_entries": 0
        }

def send_chat_message(message: str) -> Dict[str, Any]:
    """Send a message to the chat endpoint."""

    # Check for comparison keywords that require LLM
    comparison_keywords = ['colder', 'warmer', 'hotter', 'cooler', 'compare', 'versus', ' vs ', ' or ', 'difference', 'better', 'worse']
    is_comparison = any(keyword in message.lower() for keyword in comparison_keywords)

    # Check if it's a weather query
    weather_keywords = ['weather', 'temperature', 'forecast', 'rain', 'sunny', 'cloudy', 'wind', 'humidity', 'cold', 'hot', 'warm']
    is_weather_query = any(keyword in message.lower() for keyword in weather_keywords)

    # If LLM is available and it's either a comparison or complex query, use chat endpoint
    if st.session_state.system_status.get("llm", False) and (is_comparison or is_weather_query):
        # Use chat endpoint for all weather queries when LLM is available
        with st.spinner("Analyzing your question..."):
            # Build request with thread_id for conversation memory
            request_data = {"message": message}
            if st.session_state.thread_id:
                request_data["thread_id"] = st.session_state.thread_id

            response = call_api("/chat", "POST", request_data, timeout=120.0)

            # Store thread_id from response for future messages
            if response.get("thread_id"):
                st.session_state.thread_id = response["thread_id"]

        # Process the response to add tool information if available
        if response.get("success") and response.get("intent") == "comparison":
            # Add comparison tool info
            if response.get("locations"):
                response["tool_call"] = {
                    "tool": "compare_locations",
                    "input": {"locations": response["locations"]},
                    "timestamp": datetime.now().isoformat(),
                    "output": {"comparison": "See detailed analysis above"}
                }

        return response

    # Fallback to simple pattern matching for basic queries when LLM not available
    elif is_weather_query and not is_comparison:
        # Extract location from message (simple extraction)
        locations = extract_locations(message)

        if locations:
            # Get weather for the first location
            location = locations[0]

            # Store tool call information
            tool_call = {
                "tool": "get_weather",
                "input": {"location": location},
                "timestamp": datetime.now().isoformat()
            }

            weather_data = call_api(f"/weather?location={location}")

            # Add tool call info to response
            if "error" not in weather_data:
                weather_data["tool_call"] = tool_call
                weather_data["tool_call"]["output"] = weather_data.get("data", {})

            return weather_data
        else:
            return {"error": "Please specify a location for weather information."}
    else:
        # Default response when no LLM or not a weather query
        if not st.session_state.system_status.get("llm", False):
            return {
                "response": "I can help you with weather information! Just ask me about the weather in any city. For comparisons between cities, I need the LLM to be configured.",
                "needs_input": True
            }
        else:
            # LLM is available but not a weather query
            request_data = {"message": message}
            if st.session_state.thread_id:
                request_data["thread_id"] = st.session_state.thread_id

            response = call_api("/chat", "POST", request_data)

            # Store thread_id from response
            if response.get("thread_id"):
                st.session_state.thread_id = response["thread_id"]

            return response

def extract_locations(text: str) -> List[str]:
    """Simple location extraction from text."""
    # Common city patterns
    import re

    # Pattern for "in <city>" or "for <city>" or "at <city>"
    patterns = [
        r'(?:in|for|at|of)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
        r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+weather',
        r'weather\s+(?:in|for|at)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)'
    ]

    locations = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        locations.extend(matches)

    # Clean up and deduplicate
    locations = list(set([loc.strip() for loc in locations if len(loc) > 2]))

    # Add state abbreviations if mentioned
    state_pattern = r',\s*([A-Z]{2})\b'
    states = re.findall(state_pattern, text)

    # Combine city with state if both found
    if locations and states:
        locations[0] = f"{locations[0]}, {states[0]}"

    return locations

def format_timestamp(timestamp: Optional[str] = None) -> str:
    """Format timestamp for display."""
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except:
            dt = datetime.now()
    else:
        dt = datetime.now()
    return dt.strftime("%I:%M %p")

def display_weather_data(data: Dict[str, Any]):
    """Display weather data in a nice format."""
    if "data" in data:
        weather = data["data"]

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("🌡️ Temperature", weather.get("temperature", "N/A"))

        with col2:
            st.metric("☁️ Conditions", weather.get("conditions", "N/A"))

        with col3:
            st.metric("💧 Humidity", weather.get("humidity", "N/A"))

        if "wind" in weather:
            st.metric("💨 Wind", weather.get("wind"))

        if "forecast" in weather:
            with st.expander("📅 Forecast", expanded=True):
                st.write(weather.get("forecast"))

        if data.get("cached"):
            st.caption(f"📦 Cached data from {data.get('cached_at', 'unknown time')}")

def main():
    # Check system status on load
    check_system_status()

    # Sidebar with controls
    with st.sidebar:
        # Logo/Header
        st.markdown('''
            <div style="text-align: center; padding: 20px 0;">
                <h1 style="color: white; font-size: 2.5em;">🌤️</h1>
                <h2 style="color: white; margin: 0;">Weather Assistant</h2>
                <p style="color: #aaa; font-size: 0.9em; margin-top: 5px;">Powered by MCP</p>
            </div>
        ''', unsafe_allow_html=True)

        st.divider()

        # System Status with Preflight Checks
        st.markdown("### 📊 System Status")

        # Preflight check button
        if st.button("🔄 Run Preflight Checks", use_container_width=True):
            with st.spinner("Checking systems..."):
                check_system_status()
                time.sleep(1)  # Give visual feedback

        # Status indicators
        status_items = [
            ("API", st.session_state.system_status.get("api", False), "Weather Agent API"),
            ("MCP", st.session_state.system_status.get("mcp", False), "MCP Server Connection"),
            ("LLM", st.session_state.system_status.get("llm", False), "Language Model")
        ]

        for name, is_online, description in status_items:
            if is_online:
                status_class = "status-online"
                status_text = "Connected"
                icon = "✅"
            else:
                status_class = "status-offline"
                status_text = "Disconnected"
                icon = "❌"

            st.markdown(f'''
                <div style="color: white; margin: 10px 0;">
                    <span class="status-indicator {status_class}"></span>
                    <strong>{name}</strong>: {status_text}
                    <div style="font-size: 0.8em; color: #aaa; margin-left: 20px;">{description}</div>
                </div>
            ''', unsafe_allow_html=True)

        # Cache info
        cache_entries = st.session_state.system_status.get("cache_entries", 0)
        st.markdown(f'''
            <div style="color: white; margin: 10px 0;">
                <span>📦 Cache: {cache_entries} entries</span>
            </div>
        ''', unsafe_allow_html=True)

        st.divider()

        # LLM Parameters (only show if LLM is available)
        if st.session_state.system_status.get("llm", False):
            st.markdown("### 🎛️ LLM Parameters")

            st.session_state.llm_params['temperature'] = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                value=st.session_state.llm_params['temperature'],
                step=0.1,
                help="Controls randomness. Lower = more focused, Higher = more creative"
            )

            st.session_state.llm_params['top_k'] = st.slider(
                "Top K",
                min_value=1,
                max_value=100,
                value=st.session_state.llm_params['top_k'],
                step=1,
                help="Limits vocabulary to top K tokens"
            )

            st.session_state.llm_params['top_p'] = st.slider(
                "Top P",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.llm_params['top_p'],
                step=0.05,
                help="Nucleus sampling threshold"
            )

            st.session_state.llm_params['max_tokens'] = st.slider(
                "Max Tokens",
                min_value=50,
                max_value=2000,
                value=st.session_state.llm_params['max_tokens'],
                step=50,
                help="Maximum response length"
            )

            st.divider()

        # Quick Actions
        st.markdown("### ⚡ Quick Actions")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Clear Chat", use_container_width=True):
                st.session_state.messages = []
                st.session_state.conversation_history = []
                st.session_state.thread_id = None  # Clear thread to start new conversation
                st.rerun()

        with col2:
            if st.button("📦 Clear Cache", use_container_width=True):
                result = call_api("/cache/clear", "POST")
                if "success" in result:
                    st.success("Cache cleared!")
                    check_system_status()
                    st.rerun()

        # Example queries
        st.markdown("### 💡 Example Queries")
        examples = [
            "What's the weather in Seattle?",
            "How's the weather in New York?",
            "Tell me about Miami weather",
            "Is it raining in Portland?"
        ]

        for example in examples:
            if st.button(example, use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": example})
                st.rerun()

    # Main chat interface
    st.markdown('''
        <div class="header-container">
            <h1 style="margin: 0;">Weather Assistant Chat</h1>
            <p style="margin: 5px 0 0 0; opacity: 0.9;">Ask me about weather anywhere in the world!</p>
        </div>
    ''', unsafe_allow_html=True)

    # Display system warnings if needed
    if not st.session_state.system_status.get("api", False):
        st.error("⚠️ Weather Agent API is not connected. Please ensure the API server is running on port 8000.")
    elif not st.session_state.system_status.get("mcp", False):
        st.warning("⚠️ MCP Server is not connected. Weather data may be unavailable.")
    elif not st.session_state.system_status.get("llm", False):
        st.info("ℹ️ LLM is not configured. Natural language processing is limited. You can still get weather data by mentioning city names.")

    # Chat messages container
    chat_container = st.container()

    # Display chat messages
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                # Show tool usage if tools were used
                if message["role"] == "assistant" and "tool_calls" in message:
                    for tool_call in message["tool_calls"]:
                        tool_name = tool_call.get("tool_name", "unknown")
                        success = tool_call.get("success", False)
                        icon = "✅" if success else "❌"

                        if tool_name == "get-weather":
                            location = tool_call.get("arguments", {}).get("location", "unknown")
                            st.info(f"🔧 Used tool: **{tool_name}** for {location} {icon}")
                        else:
                            st.info(f"🔧 Used tool: **{tool_name}** {icon}")

                st.markdown(message["content"])

                # Display weather data if present
                if "weather_data" in message:
                    display_weather_data(message["weather_data"])

                    # Show tool call details expander for historical messages
                    if "tool_call" in message:
                        with st.expander("🔍 Tool Call Details", expanded=False):
                            col1, col2 = st.columns(2)

                            with col1:
                                st.markdown("**📥 Input:**")
                                st.json(message["tool_call"]["input"])

                            with col2:
                                st.markdown("**📤 Output:**")
                                output_display = {
                                    "location": message["tool_call"]["output"].get("location"),
                                    "temperature": message["tool_call"]["output"].get("temperature"),
                                    "conditions": message["tool_call"]["output"].get("conditions"),
                                    "humidity": message["tool_call"]["output"].get("humidity"),
                                    "wind": message["tool_call"]["output"].get("wind"),
                                    "source": message["tool_call"]["output"].get("source")
                                }
                                st.json(output_display)

                            st.caption(f"⏰ Tool called at: {message['tool_call']['timestamp']}")

    # Chat input
    if prompt := st.chat_input("Ask about weather in any city..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.conversation_history.append({"role": "user", "content": prompt})

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = send_chat_message(prompt)

            # Display MCP operations (tools and prompts)
            mcp_ops = response.get("mcp_operations", {})
            tool_calls = mcp_ops.get("tools", [])
            prompt_calls = mcp_ops.get("prompts", [])

            # Show tool usage notifications
            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = tool_call.get("tool_name", "unknown")
                    success = tool_call.get("success", False)
                    icon = "✅" if success else "❌"

                    # Format the tool usage message based on the tool
                    if tool_name == "get_weather":
                        location = tool_call.get("arguments", {}).get("location", "unknown location")
                        st.info(f"🔧 Using tool: **{tool_name}** for {location} {icon}")
                    else:
                        st.info(f"🔧 Using tool: **{tool_name}** {icon}")

            # Show prompt usage notifications
            if prompt_calls:
                for prompt_call in prompt_calls:
                    prompt_name = prompt_call.get("prompt_name", "unknown")
                    success = prompt_call.get("success", False)
                    icon = "✅" if success else "❌"
                    st.info(f"📝 Using prompt: **{prompt_name}** {icon}")

            if "error" in response:
                st.error(response["error"])
                assistant_message = f"I encountered an error: {response['error']}"
            elif "success" in response and response.get("response"):
                # Chat/comparison response from LLM
                assistant_message = response["response"]
                st.markdown(assistant_message)

                # Add expandable section for detailed MCP tool information
                if tool_calls:
                    with st.expander(f"🔍 Tool Call Details ({len(tool_calls)} MCP calls)", expanded=False):
                        for i, tool_call in enumerate(tool_calls, 1):
                            st.markdown(f"### Tool Call {i}: **{tool_call.get('tool_name', 'unknown')}**")

                            # Tool call metadata
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Status", "✅ Success" if tool_call.get("success") else "❌ Failed")
                            with col2:
                                duration = tool_call.get("duration", 0)
                                st.metric("Duration", f"{duration:.2f}s")
                            with col3:
                                timestamp = tool_call.get("timestamp", "N/A")
                                st.metric("Time", timestamp.split("T")[1][:8] if "T" in timestamp else timestamp[:8])

                            # Tool inputs and outputs
                            col1, col2 = st.columns(2)

                            with col1:
                                st.markdown("##### 📥 Input Arguments:")
                                arguments = tool_call.get("arguments", {})
                                if arguments:
                                    st.json(arguments)
                                else:
                                    st.text("No arguments")

                            with col2:
                                st.markdown("##### 📤 Output:")
                                if tool_call.get("success"):
                                    result = tool_call.get("result", {})
                                    if result:
                                        # Format the result based on content
                                        if isinstance(result, dict):
                                            # For weather data, show key fields
                                            if "content" in result and isinstance(result["content"], list):
                                                # FastMCP response format
                                                content = result["content"][0] if result["content"] else {}
                                                if hasattr(content, "text"):
                                                    try:
                                                        weather_data = json.loads(content.text)
                                                        # Show key weather fields
                                                        display_data = {
                                                            "location": weather_data.get("location"),
                                                            "temperature": weather_data.get("temperature"),
                                                            "conditions": weather_data.get("conditions"),
                                                            "humidity": weather_data.get("humidity")
                                                        }
                                                        st.json(display_data)
                                                    except:
                                                        st.text(content.text[:200] + "..." if len(content.text) > 200 else content.text)
                                                else:
                                                    st.json(content)
                                            else:
                                                st.json(result)
                                        else:
                                            st.code(str(result))
                                    else:
                                        st.text("No output data")
                                else:
                                    error = tool_call.get("error", "Unknown error")
                                    st.error(f"Error: {error}")

                            if i < len(tool_calls):
                                st.divider()
            elif "data" in response:
                # Direct weather data response
                # Check if we have a narrative (formatted text) first
                if "narrative" in response:
                    # Display the narrative instead of raw data
                    assistant_message = response["narrative"]
                    st.markdown(assistant_message)
                else:
                    # Fallback to old display if no narrative
                    weather = response["data"]
                    assistant_message = f"Here's the weather for **{weather.get('location', 'your location')}**:"
                    st.markdown(assistant_message)
                    display_weather_data(response)


            elif "response" in response:
                # Chat response
                assistant_message = response["response"]
                st.markdown(assistant_message)
            else:
                assistant_message = "I'm not sure how to respond to that. Try asking about weather in a specific city!"
                st.markdown(assistant_message)

            # Save assistant message
            message_data = {"role": "assistant", "content": assistant_message}
            if "data" in response:
                message_data["weather_data"] = response
            if tool_calls:
                message_data["tool_calls"] = tool_calls

            st.session_state.messages.append(message_data)
            st.session_state.conversation_history.append({"role": "assistant", "content": assistant_message})

if __name__ == "__main__":
    main()