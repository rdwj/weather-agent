#!/usr/bin/env python3
"""
Production Weather Agent with full MCP capabilities.

This agent provides intelligent weather services using MCP tools, prompts,
and LLM analysis.
"""

import json
import logging
from datetime import datetime
from typing import Any

from ..core.base_agent import BaseAgent
from ..core.conversation_memory import get_memory_manager
from ..utilities.cache_manager import cache_manager
from ..utilities.prompt_loader import get_prompt_loader

logger = logging.getLogger(__name__)


class WeatherAgent(BaseAgent):
    """
    Production weather agent with comprehensive capabilities.
    """

    def __init__(self, mcp_url: str | None = None):
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

        # Initialize prompt loader
        self._prompt_loader = get_prompt_loader()

        # Load system prompt from YAML
        system_prompt = self._prompt_loader.load_prompt("system_prompt")

        super().__init__(
            name="WeatherAgent",
            description="Intelligent weather assistant with real-time data and analysis",
            system_prompt=system_prompt,
            temperature=0.7,  # Slightly higher for more natural language
            mcp_config=mcp_config
        )

        # Use shared cache manager (supports Redis in production)
        self._cache = cache_manager

        # Initialize conversation memory manager
        self._memory_manager = get_memory_manager()

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
                logger.info("Weather agent initialized with MCP server")

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
    ) -> dict[str, Any]:
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
                narrative = await self._format_weather_narrative(cached_data)
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
                narrative = await self._format_weather_narrative(result["data"])

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

    async def _get_weather_with_geocoding(self, location: str) -> dict[str, Any]:
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
                narrative = await self._format_weather_narrative(weather_result["data"])
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
        weather_data: dict[str, Any],
        analysis_type: str = "general"
    ) -> dict[str, Any]:
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
            narrative = await self._format_weather_narrative(weather_data)
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

    async def _format_weather_narrative(self, weather_data: dict[str, Any]) -> str:
        """
        Format weather data as a nice narrative using LLM with formatting prompt.

        Args:
            weather_data: Weather data dictionary

        Returns:
            Formatted narrative string
        """
        # If LLM is not available, use simple formatting
        if not self.llm_client.is_available():
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

        # Use LLM with formatting prompt
        try:
            # Load weather report formatting prompt
            formatting_prompt = self._prompt_loader.load_prompt(
                "weather_report_format",
                {"weather_data": json.dumps(weather_data, indent=2)}
            )

            # Get formatted narrative from LLM
            narrative = await self.call_llm(
                prompt=formatting_prompt,
                temperature=0.7
            )

            return narrative if isinstance(narrative, str) else str(narrative)

        except Exception as e:
            logger.error(f"Error formatting weather narrative: {e}")
            # Fallback to simple format on error
            location = weather_data.get("location", "the requested location")
            return f"Weather data for {location}: {json.dumps(weather_data, indent=2)}"

    async def _analyze_with_custom_prompt(
        self,
        weather_data: dict[str, Any],
        analysis_type: str
    ) -> dict[str, Any]:
        """
        Analyze weather with custom prompt when MCP prompts unavailable.
        """
        # Map analysis types to prompt files
        prompt_map = {
            "general": "general_analysis",
            "safety": "safety_analysis",
            "activity": "activity_analysis",
            "travel": "travel_analysis"
        }

        # Get the appropriate prompt name
        prompt_name = prompt_map.get(analysis_type, "general_analysis")

        # Load prompt with weather data substitution
        try:
            prompt = self._prompt_loader.load_prompt(
                prompt_name,
                {"weather_data": json.dumps(weather_data, indent=2)}
            )
        except (FileNotFoundError, KeyError) as e:
            logger.error(f"Error loading prompt '{prompt_name}': {e}")
            # Fallback to simple narrative
            return {
                "success": True,
                "analysis": await self._format_weather_narrative(weather_data),
                "type": analysis_type,
                "prompt_used": "fallback"
            }

        # Get LLM analysis
        analysis = await self.call_llm(prompt=prompt, temperature=0.7)

        return {
            "success": True,
            "analysis": analysis,
            "type": analysis_type,
            "prompt_used": prompt_name
        }

    async def compare_locations(
        self,
        locations: list[str]
    ) -> dict[str, Any]:
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
                # Load comparison prompt from YAML
                try:
                    comparison_prompt = self._prompt_loader.load_prompt(
                        "location_comparison",
                        {"weather_data": json.dumps(weather_data, indent=2)}
                    )
                except (FileNotFoundError, KeyError) as e:
                    logger.warning(f"Error loading comparison prompt: {e}, using fallback")
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
    ) -> dict[str, Any]:
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
            # Load forecast prompt from YAML
            try:
                forecast_prompt = self._prompt_loader.load_prompt(
                    "forecast_analysis",
                    {
                        "weather_data": json.dumps(weather_data, indent=2),
                        "days": str(days)
                    }
                )
            except (FileNotFoundError, KeyError) as e:
                logger.warning(f"Error loading forecast prompt: {e}, using fallback")
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
        thread_id: str | None = None,
        conversation_history: list[dict[str, str]] | None = None
    ) -> dict[str, Any]:
        """
        Chat interface for natural language weather queries with conversation memory.

        Args:
            message: User message
            thread_id: Optional thread ID for conversation persistence
            conversation_history: Previous conversation messages (deprecated, use thread_id)

        Returns:
            Agent response with weather information and thread_id
        """
        try:
            # Clear tool history for this chat operation
            self.clear_tool_call_history()

            # Get or create thread_id
            import uuid
            if not thread_id:
                thread_id = str(uuid.uuid4())

            # Get conversation context from memory
            last_location = self._memory_manager.get_last_location(thread_id)
            last_weather_data = self._memory_manager.get_last_weather_data(thread_id)

            # Extract intent and location from message
            # NOTE: Schema is intentionally forgiving - LLM might write messy JSON
            extraction_schema = {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": ["current", "forecast", "comparison", "analysis", "general", "follow_up"]
                    },
                    "locations": {
                        "type": ["array", "null"],
                        "items": {"type": "string"}
                    },
                    "time_context": {
                        "type": ["string", "null"],
                        "enum": ["now", "today", "tomorrow", "week", "weekend", None]
                    },
                    "needs_clarification": {
                        "type": ["boolean", "null"]
                    },
                    "references_previous": {
                        "type": ["boolean", "null"]
                    }
                },
                "required": ["intent"]
            }

            # Extract information from user message
            extraction_instructions = f"""Extract weather query details from the user's message.

IMPORTANT: Look carefully for location names in the query. Cities, states, countries - anything that indicates WHERE.
Examples:
- "weather in Boston" → locations: ["Boston"]
- "what's it like in Paris, France?" → locations: ["Paris, France"]
- "how's Scranton, NJ today?" → locations: ["Scranton, NJ"]
- "weather forecast for Seattle" → locations: ["Seattle"], intent: "forecast"

Previous location context: {last_location or 'none'}

Only set needs_clarification to true if there is ABSOLUTELY NO location mentioned and no previous context."""

            extracted = await self.extract(
                text=message,
                extraction_schema=extraction_schema,
                instructions=extraction_instructions
            )

            # Handle based on intent
            if extracted.get("needs_clarification"):
                clarification_msg = "I'd be happy to help with weather information. Could you please specify a location?"
                # Update memory with clarification
                self._memory_manager.update_conversation_state(
                    thread_id=thread_id,
                    user_message=message,
                    assistant_response=clarification_msg,
                    intent=extracted
                )
                return {
                    "success": True,
                    "response": clarification_msg,
                    "needs_input": True,
                    "thread_id": thread_id
                }

            locations = extracted.get("locations") or []
            intent = extracted.get("intent", "general")

            # Handle follow-up queries or time-based queries that reference previous context
            # If there's no location but we have context, use the previous location
            if not locations and last_location:
                if extracted.get("references_previous") or intent in ["follow_up", "forecast"]:
                    locations = [last_location]
                    logger.info(f"Using previous location from context: {last_location}")

            # Process based on intent
            weather_data = None
            response = ""

            if intent == "comparison" and len(locations) > 1:
                result = await self.compare_locations(locations)
                response = result.get("comparison", "Comparison completed")
                weather_data = result.get("weather_data")

            elif intent == "forecast" and locations:
                result = await self.get_forecast(locations[0])
                response = result.get("forecast_analysis", result.get("forecast_text"))
                weather_data = result.get("current")

            elif locations:
                # Get weather for first location
                weather_result = await self.get_weather(locations[0])

                if weather_result["success"]:
                    weather_data = weather_result["data"]
                    # Use the narrative response (already formatted nicely)
                    response = weather_result.get("narrative", "Weather data retrieved")
                else:
                    response = f"I couldn't get weather for {locations[0]}. Please check the location name."

            elif last_weather_data and ("format" in message.lower() or "report" in message.lower()):
                # User is asking to format previous weather data
                response = await self._format_weather_narrative(last_weather_data)
                weather_data = last_weather_data
                locations = [last_location] if last_location else []

            else:
                response = "I can help you with weather information. Please specify a location like 'Seattle, WA' or 'London'."

            # Update conversation memory
            current_location = locations[0] if locations else last_location
            logger.info(f"💾 Updating memory: thread={thread_id[:20]}, location={current_location}, locations={locations}")
            self._memory_manager.update_conversation_state(
                thread_id=thread_id,
                user_message=message,
                assistant_response=response,
                location=current_location,
                weather_data=weather_data,
                intent=extracted
            )

            return {
                "success": True,
                "response": response,
                "intent": intent,
                "locations": locations,
                "thread_id": thread_id,
                "tool_calls": self.get_tool_call_history()
            }

        except Exception as e:
            logger.error(f"Chat processing failed: {e}")
            error_response = "I encountered an error processing your request. Please try again."

            # Update memory with error
            if thread_id:
                self._memory_manager.update_conversation_state(
                    thread_id=thread_id,
                    user_message=message,
                    assistant_response=error_response
                )

            return {
                "success": False,
                "response": error_response,
                "error": str(e),
                "thread_id": thread_id,
                "tool_calls": self.get_tool_call_history()
            }

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
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
            thread_id = input_data.get("thread_id")
            history = input_data.get("history", [])
            return await self.chat(message, thread_id, history)

        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}"
            }

    async def clear_cache(self):
        """Clear the weather cache."""
        await self._cache.clear()
        logger.info("Weather cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
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
