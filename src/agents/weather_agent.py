#!/usr/bin/env python3
"""
Production Weather Agent with full MCP capabilities.

This agent provides intelligent weather services using MCP tools, prompts,
and LLM analysis.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio

from ..core.base_agent import BaseAgent, MCPConfig
from ..utilities.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class WeatherAgent(BaseAgent):
    """
    Production weather agent with comprehensive capabilities.
    """

    def __init__(self, mcp_url: Optional[str] = None):
        """
        Initialize weather agent.

        Args:
            mcp_url: Optional MCP server URL (defaults to environment variable)
        """
        # Use provided URL or default from environment
        if mcp_url:
            mcp_config = mcp_url
        else:
            # Will use MCP_URL from environment if not provided
            mcp_config = None

        super().__init__(
            name="WeatherAgent",
            description="Intelligent weather assistant with real-time data and analysis",
            system_prompt="""You are a friendly weather assistant helping people understand the weather.

            IMPORTANT: Always respond in natural, conversational language. Write in flowing paragraphs.
            NEVER use JSON format, code blocks, or structured data in your responses.

            When providing weather information:
            - Write like you're talking to a friend
            - Use plain English paragraphs
            - Be warm and helpful
            - Include practical advice when relevant
            - Mention any safety concerns

            Keep responses concise but complete - aim for 2-3 short paragraphs.""",
            temperature=0.7,  # Slightly higher for more natural language
            mcp_config=mcp_config
        )

        # Use shared cache manager (supports Redis in production)
        self._cache = cache_manager

    async def initialize(self) -> bool:
        """
        Initialize the agent and connect to MCP server.

        Returns:
            True if initialization successful
        """
        try:
            # Initialize cache
            cache_initialized = await self._cache.initialize()
            if cache_initialized:
                logger.info(f"Cache initialized: {self._cache.get_stats()}")

            # Connect to MCP server
            connected = await self.connect_mcp()
            if connected:
                logger.info(f"Weather agent initialized with MCP server")

                # List available capabilities
                tools = await self.list_tools()
                prompts = await self.list_prompts()
                resources = await self.list_resources()

                logger.info(f"Available capabilities - Tools: {len(tools)}, "
                          f"Prompts: {len(prompts)}, Resources: {len(resources)}")

                return True
            else:
                logger.warning("Weather agent initialized without MCP server")
                return False

        except Exception as e:
            logger.error(f"Failed to initialize weather agent: {e}")
            return False

    def _get_cache_key(self, location: str) -> str:
        """Generate cache key for location."""
        return f"weather:{location.lower().strip()}"

    async def get_weather(
        self,
        location: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get weather for a location.

        Args:
            location: Location string (e.g., "Seattle, WA")
            use_cache: Whether to use cached data if available

        Returns:
            Weather data with success status
        """
        cache_key = self._get_cache_key(location)

        # Check cache if enabled
        if use_cache:
            cached_data = await self._cache.get(cache_key)
            if cached_data:
                logger.debug(f"Using cached weather for {location}")
                # Generate narrative for cached data too
                narrative = self._format_weather_narrative(cached_data)
                return {
                    "success": True,
                    "data": cached_data,
                    "narrative": narrative,
                    "cached": True,
                    "cached_at": cached_data.get("_cached_at", datetime.utcnow().isoformat())
                }

        # Fetch fresh weather data
        try:
            if not self.is_mcp_connected():
                await self.connect_mcp()

            result = await self.call_tool("get_weather", {"location": location})

            if result["success"]:
                # Cache the result
                await self._cache.set(cache_key, result["data"])

                # Generate a formatted narrative for the response
                narrative = self._format_weather_narrative(result["data"])

                return {
                    "success": True,
                    "data": result["data"],
                    "narrative": narrative,
                    "cached": False
                }
            else:
                # Try geocoding fallback
                return await self._get_weather_with_geocoding(location)

        except Exception as e:
            logger.error(f"Error getting weather for {location}: {e}")
            return {
                "success": False,
                "error": str(e),
                "location": location
            }

    async def _get_weather_with_geocoding(self, location: str) -> Dict[str, Any]:
        """
        Get weather using geocoding fallback.

        Args:
            location: Location string

        Returns:
            Weather data with success status
        """
        try:
            # Parse location
            parts = [p.strip() for p in location.split(",")]
            city = parts[0]
            state = parts[1] if len(parts) > 1 else None

            # Geocode location
            geocode_args = {"city": city}
            if state:
                geocode_args["state"] = state

            geocode_result = await self.call_tool("geocode_location", geocode_args)

            if not geocode_result["success"]:
                return {
                    "success": False,
                    "error": f"Could not find location: {location}",
                    "location": location
                }

            coords = geocode_result["data"]

            # Get weather from coordinates
            weather_result = await self.call_tool(
                "get_weather_from_coordinates",
                {"lat": coords["lat"], "lon": coords["lon"]}
            )

            if weather_result["success"]:
                # Cache the result
                cache_key = self._get_cache_key(location)
                await self._cache.set(cache_key, weather_result["data"])

                # Generate narrative
                narrative = self._format_weather_narrative(weather_result["data"])
                weather_result["narrative"] = narrative

            return weather_result

        except Exception as e:
            logger.error(f"Geocoding fallback failed for {location}: {e}")
            return {
                "success": False,
                "error": str(e),
                "location": location
            }

    async def analyze_weather(
        self,
        weather_data: Dict[str, Any],
        analysis_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Analyze weather data using LLM or formatted narrative.

        Args:
            weather_data: Weather data to analyze
            analysis_type: Type of analysis (general, safety, activity, travel)

        Returns:
            Analysis results
        """
        if not self.llm_client.is_available():
            # Use simple formatted narrative when LLM not available
            narrative = self._format_weather_narrative(weather_data)
            return {
                "success": True,
                "analysis": narrative,
                "type": analysis_type,
                "prompt_used": "fallback"
            }

        try:
            # Get appropriate prompt based on analysis type
            prompts_map = {
                "general": "weather_report",
                "safety": "severe_weather_alert",
                "brief": "daily_forecast_brief",
                "comparison": "weather_comparison"
            }

            prompt_name = prompts_map.get(analysis_type, "weather_report")

            # Get prompt template
            prompt_result = await self.get_prompt(prompt_name, {})

            if prompt_result.success and prompt_result.messages:
                # Use the prompt template
                prompt_content = prompt_result.messages[0].content

                # Replace placeholders
                prompt_content = prompt_content.replace(
                    "{weather_data}",
                    json.dumps(weather_data, indent=2)
                ).replace(
                    "{current_weather}",
                    json.dumps(weather_data, indent=2)
                ).replace(
                    "{forecast_data}",
                    weather_data.get("forecast", "No forecast available")
                ).replace(
                    "{weather_alerts}",
                    "No active alerts"
                )

                # Get LLM analysis
                analysis = await self.call_llm(
                    prompt=prompt_content,
                    temperature=0.7
                )

                return {
                    "success": True,
                    "analysis": analysis,
                    "type": analysis_type,
                    "prompt_used": prompt_name
                }

            else:
                # Fallback to custom prompt
                return await self._analyze_with_custom_prompt(weather_data, analysis_type)

        except Exception as e:
            logger.error(f"Weather analysis failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _format_weather_narrative(self, weather_data: Dict[str, Any]) -> str:
        """
        Format weather data as a nice narrative when LLM is not available.

        Args:
            weather_data: Weather data dictionary

        Returns:
            Formatted narrative string
        """
        location = weather_data.get("location", "the requested location")
        temp = weather_data.get("temperature", "N/A")
        conditions = weather_data.get("conditions", "N/A")
        humidity = weather_data.get("humidity", "N/A")
        wind = weather_data.get("wind", "N/A")
        forecast = weather_data.get("forecast", "")

        # Build narrative
        narrative = f"Here's the current weather for **{location}**:\n\n"
        narrative += f"🌡️ **Temperature:** {temp}\n"
        narrative += f"☁️ **Conditions:** {conditions}\n"
        narrative += f"💧 **Humidity:** {humidity}\n"
        narrative += f"💨 **Wind:** {wind}\n"

        if forecast and forecast != "N/A":
            narrative += f"\n📅 **Forecast:**\n{forecast}"

        return narrative

    async def _analyze_with_custom_prompt(
        self,
        weather_data: Dict[str, Any],
        analysis_type: str
    ) -> Dict[str, Any]:
        """
        Analyze weather with custom prompt when MCP prompts unavailable.
        """
        prompts = {
            "general": f"""
                You are writing a weather report for a friend. Based on this weather data:
                {json.dumps(weather_data, indent=2)}

                CRITICAL INSTRUCTIONS:
                - Write in PLAIN TEXT paragraphs - NO JSON, NO code blocks, NO structured data
                - Start directly with the weather report - don't write "Here's the report:" or similar
                - Use natural, conversational language like you're texting a friend
                - Keep it concise - 2-3 short paragraphs at most

                Write something like:
                "It's currently [temperature] and [conditions] in [location]. [Add context about how it feels]

                Looking at the forecast, [brief forecast summary]. [Add practical tip about clothing or activities].

                [Any additional helpful note about the weather]"

                Remember: Write as flowing text, not structured data. Be conversational and helpful.
            """,
            "safety": f"""
                Analyze this weather data for safety concerns and write a clear report:
                {json.dumps(weather_data, indent=2)}

                Focus on:
                1. Any dangerous conditions (extreme temps, severe weather, etc.)
                2. Health and safety impacts
                3. Travel safety considerations
                4. Specific, actionable precautions to take

                Be clear and direct about any risks. Use proper formatting with line breaks.
            """,
            "activity": f"""
                Based on this weather data, provide helpful activity recommendations:
                {json.dumps(weather_data, indent=2)}

                Include:
                1. How suitable the weather is for outdoor activities
                2. Best times for specific activities
                3. What to wear or bring
                4. Any activities to avoid

                Be conversational and helpful. Format nicely with line breaks.
            """,
            "travel": f"""
                Analyze this weather for travel planning and write a helpful report:
                {json.dumps(weather_data, indent=2)}

                Cover:
                1. Driving conditions and visibility
                2. Potential impacts on flights or other travel
                3. Best times to travel
                4. What travelers should prepare for

                Be practical and specific. Use proper formatting.
            """
        }

        prompt = prompts.get(analysis_type, prompts["general"])

        analysis = await self.call_llm(prompt=prompt, temperature=0.7)

        return {
            "success": True,
            "analysis": analysis,
            "type": analysis_type,
            "prompt_used": "custom"
        }

    async def compare_locations(
        self,
        locations: List[str]
    ) -> Dict[str, Any]:
        """
        Compare weather between multiple locations.

        Args:
            locations: List of location strings

        Returns:
            Comparison results
        """
        if len(locations) < 2:
            return {
                "success": False,
                "error": "Need at least 2 locations to compare"
            }

        if len(locations) > 5:
            return {
                "success": False,
                "error": "Maximum 5 locations for comparison"
            }

        try:
            # Clear tool history for this operation
            self.clear_tool_call_history()

            # Fetch weather for all locations
            weather_data = {}
            for location in locations:
                result = await self.get_weather(location)
                if result["success"]:
                    weather_data[location] = result["data"]
                else:
                    logger.warning(f"Failed to get weather for {location}")

            if len(weather_data) < 2:
                return {
                    "success": False,
                    "error": "Could not get weather for enough locations",
                    "tool_calls": self.get_tool_call_history()
                }

            # Analyze comparison
            if self.llm_client.is_available():
                comparison_prompt = f"""
                    Compare the weather conditions between these locations:
                    {json.dumps(weather_data, indent=2)}

                    Provide:
                    1. Temperature comparison
                    2. Condition differences
                    3. Best/worst weather location
                    4. Key differences to note
                    5. Recommendations for each location
                """

                comparison = await self.call_llm(
                    prompt=comparison_prompt,
                    temperature=0.6
                )

                return {
                    "success": True,
                    "locations": list(weather_data.keys()),
                    "weather_data": weather_data,
                    "comparison": comparison,
                    "tool_calls": self.get_tool_call_history()
                }
            else:
                # Return raw data without analysis
                return {
                    "success": True,
                    "locations": list(weather_data.keys()),
                    "weather_data": weather_data,
                    "comparison": "LLM analysis not available",
                    "tool_calls": self.get_tool_call_history()
                }

        except Exception as e:
            logger.error(f"Location comparison failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_forecast(
        self,
        location: str,
        days: int = 5
    ) -> Dict[str, Any]:
        """
        Get extended forecast for a location.

        Args:
            location: Location string
            days: Number of days to forecast (max 7)

        Returns:
            Forecast data
        """
        # For now, we get current weather which includes forecast text
        # In a real implementation, you might have a separate forecast tool
        weather_result = await self.get_weather(location)

        if not weather_result["success"]:
            return weather_result

        weather_data = weather_result["data"]

        # Extract and enhance forecast information
        result = {
            "success": True,
            "location": location,
            "current": {
                "temperature": weather_data.get("temperature"),
                "conditions": weather_data.get("conditions"),
                "humidity": weather_data.get("humidity"),
                "wind": weather_data.get("wind")
            },
            "forecast_text": weather_data.get("forecast", "No forecast available"),
            "days_requested": days
        }

        # Add LLM interpretation if available
        if self.llm_client.is_available():
            forecast_prompt = f"""
                Based on this weather data, provide a {days}-day forecast outlook:
                {json.dumps(weather_data, indent=2)}

                Include:
                1. Daily temperature trends
                2. Expected conditions
                3. Precipitation likelihood
                4. Weekend weather if applicable
                5. Planning recommendations
            """

            forecast_analysis = await self.call_llm(
                prompt=forecast_prompt,
                temperature=0.6
            )

            result["forecast_analysis"] = forecast_analysis

        return result

    async def chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Chat interface for natural language weather queries.

        Args:
            message: User message
            conversation_history: Previous conversation messages

        Returns:
            Agent response with weather information
        """
        try:
            # Clear tool history for this chat operation
            self.clear_tool_call_history()

            # Extract intent and location from message
            extraction_schema = {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": ["current", "forecast", "comparison", "analysis", "general"]
                    },
                    "locations": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "time_context": {
                        "type": "string",
                        "enum": ["now", "today", "tomorrow", "week", "weekend"]
                    },
                    "needs_clarification": {"type": "boolean"}
                },
                "required": ["intent"]
            }

            # Extract information from user message
            extracted = await self.extract(
                text=message,
                extraction_schema=extraction_schema,
                instructions="Extract weather query intent and locations"
            )

            # Handle based on intent
            if extracted.get("needs_clarification"):
                return {
                    "success": True,
                    "response": "I'd be happy to help with weather information. Could you please specify a location?",
                    "needs_input": True
                }

            locations = extracted.get("locations", [])
            intent = extracted.get("intent", "general")

            # Process based on intent
            if intent == "comparison" and len(locations) > 1:
                result = await self.compare_locations(locations)
                response = result.get("comparison", "Comparison completed")

            elif intent == "forecast" and locations:
                result = await self.get_forecast(locations[0])
                response = result.get("forecast_analysis", result.get("forecast_text"))

            elif locations:
                # Get weather for first location
                weather_result = await self.get_weather(locations[0])

                if weather_result["success"]:
                    # Analyze based on intent
                    analysis_type = "general" if intent == "current" else intent
                    analysis_result = await self.analyze_weather(
                        weather_result["data"],
                        analysis_type
                    )
                    response = analysis_result.get("analysis", "Weather data retrieved")
                else:
                    response = f"I couldn't get weather for {locations[0]}. Please check the location name."

            else:
                response = "I can help you with weather information. Please specify a location like 'Seattle, WA' or 'London'."

            return {
                "success": True,
                "response": response,
                "intent": intent,
                "locations": locations,
                "tool_calls": self.get_tool_call_history()
            }

        except Exception as e:
            logger.error(f"Chat processing failed: {e}")
            return {
                "success": False,
                "response": "I encountered an error processing your request. Please try again.",
                "error": str(e),
                "tool_calls": self.get_tool_call_history()
            }

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute weather agent tasks.

        Args:
            input_data: Task specification with 'action' and parameters

        Returns:
            Execution results
        """
        action = input_data.get("action", "weather")

        if action == "weather":
            location = input_data.get("location", "")
            return await self.get_weather(location)

        elif action == "analyze":
            weather_data = input_data.get("weather_data", {})
            analysis_type = input_data.get("type", "general")
            return await self.analyze_weather(weather_data, analysis_type)

        elif action == "compare":
            locations = input_data.get("locations", [])
            return await self.compare_locations(locations)

        elif action == "forecast":
            location = input_data.get("location", "")
            days = input_data.get("days", 5)
            return await self.get_forecast(location, days)

        elif action == "chat":
            message = input_data.get("message", "")
            history = input_data.get("history", [])
            return await self.chat(message, history)

        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}"
            }

    async def clear_cache(self):
        """Clear the weather cache."""
        await self._cache.clear()
        logger.info("Weather cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats()

    async def close(self):
        """
        Close the agent and disconnect from MCP server.

        This is called during application shutdown to cleanly disconnect
        from the MCP server and release resources.
        """
        await self.disconnect_mcp()
        logger.info("Weather agent closed")