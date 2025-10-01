#!/usr/bin/env python3
"""
Modern Chat Interface for Weather Agent - Similar to AnythingLLM/OpenWebUI
"""

import streamlit as st
import httpx
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import os
import time

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
# When running in OpenShift, use the service name
if os.getenv("KUBERNETES_SERVICE_HOST"):
    API_URL = "http://weather-agent:8000"

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
    .css-1d391kg {
        background: #2b2d42;
    }

    .sidebar .sidebar-content {
        background: #2b2d42;
        color: white;
    }

    /* Fix sidebar text colors */
    section[data-testid="stSidebar"] {
        background-color: #2b2d42;
    }

    section[data-testid="stSidebar"] .stMarkdown {
        color: #e0e0e0;
    }

    section[data-testid="stSidebar"] label {
        color: #e0e0e0 !important;
    }

    /* Input area styling */
    .stTextInput > div > div > input {
        border-radius: 25px;
        border: 2px solid #e0e0e0;
        padding: 12px 20px;
        font-size: 16px;
    }

    .stTextInput > div > div > input:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
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

    /* Slider styling - improved contrast */
    .stSlider > div > div > div > div {
        background-color: #8b5cf6 !important;
    }

    .stSlider > div > div > div[role="slider"] {
        background-color: #a78bfa !important;
        border: 2px solid #ffffff;
    }

    section[data-testid="stSidebar"] .stSlider > div > div {
        background-color: #4a4a6a !important;
    }

    section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] {
        margin-top: 10px;
    }

    /* Slider track */
    section[data-testid="stSidebar"] [data-baseweb="slider"] > div > div {
        background: linear-gradient(to right, #4a4a6a, #6366f1) !important;
        height: 6px !important;
    }

    /* Slider value text */
    section[data-testid="stSidebar"] .stSlider div[data-testid="stMarkdownContainer"] p {
        color: #e0e0e0 !important;
    }

    /* Dark theme compatibility */
    @media (prefers-color-scheme: dark) {
        .assistant-message {
            background: #2d2d2d;
            color: #f0f0f0;
            border-color: #444;
        }
    }

    /* Typing indicator */
    .typing-indicator {
        display: inline-block;
        padding: 12px 18px;
        background: white;
        border-radius: 18px;
        border: 1px solid #e0e0e0;
    }

    .typing-indicator span {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #999;
        margin: 0 2px;
        animation: typing 1.4s infinite ease-in-out;
    }

    .typing-indicator span:nth-child(1) {
        animation-delay: -0.32s;
    }

    .typing-indicator span:nth-child(2) {
        animation-delay: -0.16s;
    }

    @keyframes typing {
        0%, 60%, 100% {
            transform: scale(1);
            opacity: 0.5;
        }
        30% {
            transform: scale(1.3);
            opacity: 1;
        }
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

    .header-title {
        font-size: 2em;
        font-weight: bold;
        margin: 0;
    }

    .header-subtitle {
        font-size: 1em;
        opacity: 0.9;
        margin-top: 5px;
    }

    /* Weather data display */
    .weather-card {
        background: white;
        border-radius: 10px;
        padding: 15px;
        margin-top: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }

    .weather-card h4 {
        color: #667eea;
        margin-top: 0;
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
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'suggestions' not in st.session_state:
    st.session_state.suggestions = []
if 'model_params' not in st.session_state:
    st.session_state.model_params = {
        'temperature': 0.7,
        'top_k': 50,
        'top_p': 0.9,
        'max_tokens': 500
    }
if 'system_status' not in st.session_state:
    st.session_state.system_status = {}

def call_api(endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Call the Weather Agent API."""
    try:
        url = f"{API_URL}{endpoint}"

        if method == "POST":
            response = httpx.post(url, json=data, timeout=30.0)
        else:
            response = httpx.get(url, timeout=30.0)

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API returned status {response.status_code}: {response.text}"}
    except httpx.ConnectError:
        return {"error": "Cannot connect to Weather Agent API. Please ensure the service is running."}
    except Exception as e:
        return {"error": f"API call failed: {str(e)}"}

def send_message(message: str) -> Dict[str, Any]:
    """Send a message to the chat API with model parameters."""
    data = {
        "message": message,
        "session_id": st.session_state.session_id,
        "model_params": st.session_state.model_params
    }

    response = call_api("/api/v1/chat", "POST", data)

    if "session_id" in response:
        st.session_state.session_id = response["session_id"]

    return response

def format_timestamp(timestamp: Optional[str] = None) -> str:
    """Format timestamp for display."""
    if timestamp:
        dt = datetime.fromisoformat(timestamp)
    else:
        dt = datetime.now()
    return dt.strftime("%I:%M %p")

def display_message(role: str, content: str, metadata: Optional[Dict] = None, timestamp: Optional[str] = None):
    """Display a chat message with modern styling."""
    if role == "user":
        st.markdown(f'''
            <div class="user-message">
                {content}
                <div class="message-time">{format_timestamp(timestamp)}</div>
            </div>
        ''', unsafe_allow_html=True)
    else:
        st.markdown(f'''
            <div class="assistant-message">
                {content}
                <div class="message-time">{format_timestamp(timestamp)}</div>
            </div>
        ''', unsafe_allow_html=True)

        if metadata and metadata.get("weather_data"):
            with st.expander("📊 Weather Details", expanded=False):
                st.json(metadata["weather_data"])

def display_typing_indicator():
    """Display a typing indicator."""
    st.markdown('''
        <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
        </div>
    ''', unsafe_allow_html=True)

def check_system_status():
    """Check system status and update state."""
    health = call_api("/health")
    ready = call_api("/ready")
    llm_status = call_api("/test-llm")

    st.session_state.system_status = {
        "api": health.get("status") == "healthy",
        "ready": ready.get("ready", False),
        "redis": ready.get("checks", {}).get("redis", False),
        "mcp": ready.get("checks", {}).get("mcp", False),
        "llm": llm_status.get("success", False)
    }

def main():
    # Check system status
    check_system_status()

    # Sidebar with controls
    with st.sidebar:
        # Logo/Header
        st.markdown('''
            <div style="text-align: center; padding: 20px 0;">
                <h1 style="color: white; font-size: 2.5em;">🌤️</h1>
                <h2 style="color: white; margin: 0;">Weather Assistant</h2>
                <p style="color: #aaa; font-size: 0.9em; margin-top: 5px;">Powered by AI</p>
            </div>
        ''', unsafe_allow_html=True)

        st.divider()

        # Model Parameters Section
        st.markdown("### 🎛️ Model Parameters")

        # Temperature
        st.session_state.model_params['temperature'] = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            value=st.session_state.model_params['temperature'],
            step=0.1,
            help="Controls randomness. Lower = more focused, Higher = more creative"
        )

        # Top K
        st.session_state.model_params['top_k'] = st.slider(
            "Top K",
            min_value=1,
            max_value=100,
            value=st.session_state.model_params['top_k'],
            step=1,
            help="Limits vocabulary to top K tokens"
        )

        # Top P
        st.session_state.model_params['top_p'] = st.slider(
            "Top P",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.model_params['top_p'],
            step=0.05,
            help="Nucleus sampling threshold"
        )

        # Max Tokens
        st.session_state.model_params['max_tokens'] = st.slider(
            "Max Tokens",
            min_value=50,
            max_value=2000,
            value=st.session_state.model_params.get('max_tokens', 500),
            step=50,
            help="Maximum response length"
        )

        st.divider()

        # System Status
        st.markdown("### 📊 System Status")

        status_items = [
            ("API", st.session_state.system_status.get("api", False)),
            ("Redis", st.session_state.system_status.get("redis", False)),
            ("MCP", st.session_state.system_status.get("mcp", False)),
            ("LLM", st.session_state.system_status.get("llm", False))
        ]

        for name, is_online in status_items:
            status_class = "status-online" if is_online else "status-offline"
            status_text = "Online" if is_online else "Offline"
            st.markdown(f'''
                <div style="color: white; margin: 8px 0;">
                    <span class="status-indicator {status_class}"></span>
                    {name}: {status_text}
                </div>
            ''', unsafe_allow_html=True)

        st.divider()

        # Quick Actions
        st.markdown("### ⚡ Quick Actions")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 New Chat", use_container_width=True):
                st.session_state.session_id = None
                st.session_state.messages = []
                st.session_state.suggestions = []
                st.rerun()

        with col2:
            if st.button("🗑️ Clear", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

        # Example Queries
        st.divider()
        st.markdown("### 💡 Try Asking")

        examples = [
            "What's the weather in Seattle?",
            "Will it rain tomorrow in NYC?",
            "Compare weather: LA vs SF",
            "What should I wear today?",
            "Is it good for hiking?"
        ]

        for example in examples:
            if st.button(f"→ {example}", key=f"ex_{example}", use_container_width=True):
                st.session_state.prompt = example
                st.rerun()

        # Session Info
        if st.session_state.session_id:
            st.divider()
            st.caption(f"Session: {st.session_state.session_id[:8]}...")

    # Main chat area
    main_container = st.container()

    with main_container:
        # Header
        st.markdown('''
            <div class="header-container">
                <div class="header-title">🌤️ Weather Assistant</div>
                <div class="header-subtitle">Ask me anything about weather conditions, forecasts, and recommendations!</div>
            </div>
        ''', unsafe_allow_html=True)

        # Chat messages container
        chat_container = st.container(height=500)

        with chat_container:
            # Display messages
            for message in st.session_state.messages:
                display_message(
                    message["role"],
                    message["content"],
                    message.get("metadata"),
                    message.get("timestamp")
                )

        # Suggestions
        if st.session_state.suggestions:
            st.markdown("#### 💭 Suggested Questions")
            cols = st.columns(min(len(st.session_state.suggestions), 3))
            for idx, suggestion in enumerate(st.session_state.suggestions[:3]):
                with cols[idx]:
                    if st.button(suggestion, key=f"sug_{idx}", use_container_width=True):
                        st.session_state.prompt = suggestion
                        st.rerun()

        # Input area
        col1, col2 = st.columns([6, 1])

        with col1:
            # Check for preset prompt
            prompt = st.session_state.get('prompt', '')
            if prompt:
                del st.session_state.prompt
                user_input = prompt
            else:
                user_input = st.chat_input(
                    "Ask about weather...",
                    key="chat_input"
                )

        # Handle message sending
        if user_input:
            # Add user message
            st.session_state.messages.append({
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now().isoformat()
            })

            # Show typing indicator
            with chat_container:
                display_typing_indicator()

            # Send message with model params
            with st.spinner(""):
                response = send_message(user_input)

            if "error" in response:
                st.error(f"Error: {response['error']}")
            else:
                # Add assistant response
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response.get("response", "I couldn't process that request."),
                    "metadata": response.get("metadata"),
                    "timestamp": datetime.now().isoformat()
                })

                # Update suggestions
                st.session_state.suggestions = response.get("suggestions", [])

            st.rerun()

        # Footer
        st.markdown("---")
        st.caption("Weather Assistant powered by AI | Data from MCP Weather Service")

if __name__ == "__main__":
    main()