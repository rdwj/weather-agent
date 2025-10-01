"""Chat service for processing weather conversations."""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json
import os

from src.models.chat import ChatSession, ChatMessage
from src.utilities.llm_client import get_llm_client
from src.lib.mcp_client import MCPClient, MCPConfig

logger = logging.getLogger(__name__)


class ChatService:
    """Service for processing chat messages with weather context."""

    def __init__(self):
        """Initialize chat service."""
        self.mcp_url = os.getenv('MCP_URL', 'https://mcp-server-weather-mcp.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com')
        self.mcp_client = None
        self.system_prompt = """You are a friendly and helpful weather assistant. You provide accurate,
        conversational weather information based on user queries. You can:
        - Answer questions about current weather conditions
        - Provide weather forecasts
        - Give weather-based recommendations (what to wear, activities, etc.)
        - Compare weather between locations
        - Remember context from the conversation

        Keep responses concise but informative. Use a friendly, conversational tone.
        When you don't have specific information, be honest about it.
        """

    async def process_message(
        self,
        message: str,
        session: ChatSession,
        context: Optional[Dict[str, Any]] = None,
        model_params: Optional[Any] = None
    ) -> Tuple[str, Optional[Dict[str, Any]], Optional[List[str]]]:
        """
        Process a chat message and generate response.

        Args:
            message: User's message
            session: Current chat session
            context: Additional context

        Returns:
            Tuple of (response_text, metadata, suggestions)
        """
        try:
            # Extract intent and entities from message
            intent_data = self._analyze_message(message, session)

            # Fetch weather data if needed
            weather_data = await self._fetch_weather_data(intent_data, session)

            # Generate response using LLM with model parameters
            response_text = await self._generate_response(
                message=message,
                session=session,
                weather_data=weather_data,
                context=context,
                model_params=model_params
            )

            # Generate follow-up suggestions
            suggestions = self._generate_suggestions(intent_data, weather_data)

            # Prepare metadata
            metadata = {
                "intent": intent_data.get("intent"),
                "weather_data": weather_data,
                "location": intent_data.get("location")
            } if weather_data else None

            return response_text, metadata, suggestions

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return (
                "I'm having trouble processing your request right now. Could you please try again?",
                None,
                ["What's the weather like today?", "Tell me the forecast"]
            )

    def _analyze_message(self, message: str, session: ChatSession) -> Dict[str, Any]:
        """
        Analyze message to extract intent and entities.

        Args:
            message: User's message
            session: Current session for context

        Returns:
            Dictionary with intent and entities
        """
        message_lower = message.lower()

        # Simple intent detection (in production, use NLP/LLM)
        weather_keywords = ["weather", "temperature", "forecast", "rain", "snow", "sunny",
                          "cloudy", "hot", "cold", "humid", "wind", "storm", "degrees"]
        comparison_keywords = ["compare", "versus", "vs", "between", "difference"]
        recommendation_keywords = ["wear", "should i", "good for", "suitable", "recommend"]

        needs_weather = any(keyword in message_lower for keyword in weather_keywords)
        is_comparison = any(keyword in message_lower for keyword in comparison_keywords)
        is_recommendation = any(keyword in message_lower for keyword in recommendation_keywords)

        # Extract location from message (simple extraction)
        location = self._extract_location(message, session)

        return {
            "needs_weather_data": needs_weather or is_recommendation,
            "intent": "comparison" if is_comparison else "recommendation" if is_recommendation else "weather_query",
            "location": location,
            "is_follow_up": not location and len(session.messages) > 0
        }

    def _extract_location(self, message: str, session: ChatSession) -> Optional[str]:
        """
        Extract location from message or use context.

        Args:
            message: User's message
            session: Session for context

        Returns:
            Location string or None
        """
        # Common location indicators
        location_preps = ["in", "at", "for", "near"]
        # Time words to exclude from location
        time_words = ["today", "tomorrow", "yesterday", "now", "tonight", "morning", "afternoon", "evening"]

        message_words = message.split()
        for i, word in enumerate(message_words):
            if word.lower() in location_preps and i + 1 < len(message_words):
                # Get the rest of the message after the preposition
                remaining_words = message_words[i + 1:]
                # Filter out time words and punctuation
                location_words = []
                for w in remaining_words:
                    clean_word = w.rstrip("?!.,")
                    if clean_word.lower() not in time_words:
                        location_words.append(clean_word)
                    else:
                        break  # Stop at the first time word

                if location_words:
                    potential_location = " ".join(location_words)
                    logger.info(f"Extracted location: {potential_location}")
                    return potential_location

        # Check for "here" or "outside" - use context
        if any(word in message.lower() for word in ["here", "outside", "today", "tomorrow"]):
            # Check session context for saved location
            if session.context.get("default_location"):
                return session.context["default_location"]

            # Check recent messages for locations
            for msg in reversed(session.messages[-5:]):  # Check last 5 messages
                if msg.metadata and msg.metadata.get("location"):
                    return msg.metadata["location"]

        return None

    async def _fetch_weather_data(
        self,
        intent_data: Dict[str, Any],
        session: ChatSession
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch weather data from MCP service.

        Args:
            intent_data: Analyzed intent data
            session: Current session

        Returns:
            Weather data dictionary or None
        """
        if not intent_data.get("needs_weather_data"):
            return None

        try:
            location = intent_data.get("location")
            if not location:
                # Try to get from session context
                location = session.context.get("default_location")
                if not location:
                    return None

            # Initialize MCP client if not already done
            if not self.mcp_client:
                config = MCPConfig(
                    url=self.mcp_url,
                    token=os.getenv("MCP_TOKEN"),
                    timeout=30
                )
                self.mcp_client = MCPClient(config)
                await self.mcp_client.initialize()

            # Fetch weather using the MCP client
            weather_data = await self.mcp_client.get_weather(location)

            if weather_data:
                logger.info(f"Retrieved weather data for {location}: {weather_data}")

                # Store location in session context
                if location and location != session.context.get("default_location"):
                    session.context["recent_locations"] = session.context.get("recent_locations", [])
                    if location not in session.context["recent_locations"]:
                        session.context["recent_locations"].append(location)
                        # Keep only last 5 locations
                        session.context["recent_locations"] = session.context["recent_locations"][-5:]

                return weather_data
            else:
                logger.warning(f"No weather data returned for {location}")
                return None

        except Exception as e:
            logger.error(f"Failed to fetch weather data: {e}")
            return None

    async def _generate_response(
        self,
        message: str,
        session: ChatSession,
        weather_data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        model_params: Optional[Any] = None
    ) -> str:
        """
        Generate response using LLM.

        Args:
            message: User's message
            session: Chat session
            weather_data: Weather data if available
            context: Additional context

        Returns:
            Generated response text
        """
        try:
            # Try to use LLM for response generation
            llm_client = get_llm_client()

            if llm_client.api_url and llm_client.api_key:
                # Build conversation history for context
                conversation_history = ""
                for msg in session.messages[-5:]:  # Include last 5 messages
                    role = "User" if msg.role == "user" else "Assistant"
                    conversation_history += f"{role}: {msg.content}\n"

                # Build prompt
                if weather_data:
                    prompt = f"""{self.system_prompt}

Previous conversation:
{conversation_history if conversation_history else "No previous conversation."}

Current user message: {message}

IMPORTANT: I have fetched current weather data for this query. You MUST use this data in your response:

Weather Data:
{json.dumps(weather_data, indent=2)}

Based on this weather data, provide a helpful and accurate response about the weather conditions. Include specific details like temperature, conditions, and forecast from the data above."""
                else:
                    prompt = f"""{self.system_prompt}

Previous conversation:
{conversation_history if conversation_history else "No previous conversation."}

Current user message: {message}

Note: No weather data is available for this query. Provide a helpful response based on the conversation context."""

                # Use model parameters if provided, otherwise use defaults
                temperature = 0.7
                max_tokens = 500
                top_k = 50
                top_p = 0.9

                if model_params:
                    # Handle both dict and object formats
                    if hasattr(model_params, 'temperature'):
                        temperature = model_params.temperature
                        max_tokens = model_params.max_tokens
                        top_k = model_params.top_k
                        top_p = model_params.top_p
                    elif isinstance(model_params, dict):
                        temperature = model_params.get('temperature', 0.7)
                        max_tokens = model_params.get('max_tokens', 500)
                        top_k = model_params.get('top_k', 50)
                        top_p = model_params.get('top_p', 0.9)

                # Get response from LLM
                llm_response = llm_client.invoke_with_metadata(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_k=top_k,
                    top_p=top_p
                )

                logger.info(f"LLM response received: {llm_response}")

                if llm_response:
                    # Check for 'response' or 'content' field
                    if llm_response.get("response"):
                        return llm_response["response"]
                    elif llm_response.get("content"):
                        return llm_response["content"]
                else:
                    logger.warning("No valid LLM response received")

            # Fallback to simple responses if LLM is not available
            if "hello" in message.lower() or "hi" in message.lower():
                response = "Hello! I'm your weather assistant. How can I help you today? You can ask me about weather conditions, forecasts, or get recommendations for any location."
            elif "help" in message.lower():
                response = ("I can help you with:\n"
                           "• Current weather conditions\n"
                           "• Weather forecasts\n"
                           "• Weather comparisons between locations\n"
                           "• Clothing recommendations\n"
                           "• Activity suggestions based on weather\n"
                           "\nJust ask me something like 'What's the weather in Seattle?'")
            else:
                response = "I'd be happy to help with weather information. Could you please specify a location? For example, 'What's the weather in New York?'"

            return response

        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return "I'm having trouble generating a response right now. Please try again."

    def _get_clothing_recommendation(self, temperature: Any, conditions: str) -> str:
        """
        Generate clothing recommendations based on weather.

        Args:
            temperature: Temperature value
            conditions: Weather conditions

        Returns:
            Clothing recommendation
        """
        try:
            temp = float(str(temperature).replace("°F", "").replace("°C", ""))

            if temp > 80:
                base = "It's quite warm! Light, breathable clothing would be perfect. Consider shorts and a t-shirt."
            elif temp > 60:
                base = "The temperature is mild. A light jacket or long sleeves would be comfortable."
            elif temp > 40:
                base = "It's cool outside. You'll want a jacket or sweater, and long pants."
            else:
                base = "It's cold! Bundle up with a warm coat, hat, and gloves."

            # Add condition-specific advice
            conditions_lower = conditions.lower()
            if "rain" in conditions_lower:
                base += " Don't forget an umbrella or raincoat!"
            elif "snow" in conditions_lower:
                base += " Wear waterproof boots and layers for the snow."
            elif "sunny" in conditions_lower and temp > 70:
                base += " Remember sunscreen and sunglasses!"
            elif "wind" in conditions_lower:
                base += " A windbreaker would be helpful for the windy conditions."

            return base

        except:
            return "Based on the current conditions, dress comfortably for the weather and check the latest forecast before heading out."

    def _generate_suggestions(
        self,
        intent_data: Dict[str, Any],
        weather_data: Optional[Dict[str, Any]]
    ) -> Optional[List[str]]:
        """
        Generate follow-up question suggestions.

        Args:
            intent_data: Intent analysis
            weather_data: Weather data if available

        Returns:
            List of suggested questions
        """
        suggestions = []

        if weather_data:
            location = weather_data.get("location", "this location")
            suggestions.extend([
                f"What's the weekend forecast for {location}?",
                f"Compare weather with another city",
                "What should I wear tomorrow?",
                "Is it good weather for outdoor activities?"
            ])
        else:
            suggestions.extend([
                "What's the weather like in New York?",
                "Show me today's forecast",
                "Will it rain this week?",
                "What's the temperature outside?"
            ])

        # Return only 3 suggestions
        return suggestions[:3] if suggestions else None