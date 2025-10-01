"""LangGraph workflow with state management for weather agent."""

import logging
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
import hashlib
import json

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
# Tool execution handled directly

from ..lib.agent_state import (
    WeatherAgentState,
    create_initial_agent_state,
    validate_agent_state,
    merge_states,
    get_state_summary
)
from ..lib.mcp_client import get_mcp_client
from ..services.elicitation import ElicitationManager
from ..services.conversation_memory import ConversationContextAnalyzer

logger = logging.getLogger(__name__)


class WeatherWorkflow:
    """LangGraph workflow for processing weather queries with state management."""

    def __init__(self, session_id: str, user_id: str):
        """Initialize weather workflow.

        Args:
            session_id: Session identifier
            user_id: User identifier
        """
        self.session_id = session_id
        self.user_id = user_id
        self.elicitation_manager = ElicitationManager()
        self.context_analyzer = ConversationContextAnalyzer()

        # Create workflow graph
        self.workflow = self._build_workflow()

        # Memory saver for checkpointing
        self.memory = MemorySaver()

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow.

        Returns:
            Configured StateGraph for weather processing
        """
        # Create workflow with WeatherAgentState
        workflow = StateGraph(WeatherAgentState)

        # Add nodes
        workflow.add_node("extract_context", self.extract_context_node)
        workflow.add_node("check_elicitation", self.check_elicitation_node)
        workflow.add_node("elicit_information", self.elicit_information_node)
        workflow.add_node("check_cache", self.check_cache_node)
        workflow.add_node("call_mcp", self.call_mcp_node)
        workflow.add_node("process_response", self.process_response_node)
        workflow.add_node("format_output", self.format_output_node)
        workflow.add_node("handle_error", self.handle_error_node)

        # Set entry point
        workflow.set_entry_point("extract_context")

        # Add edges
        workflow.add_edge("extract_context", "check_elicitation")

        # Conditional routing from check_elicitation
        workflow.add_conditional_edges(
            "check_elicitation",
            self._route_after_elicitation_check,
            {
                "needs_elicitation": "elicit_information",
                "check_cache": "check_cache"
            }
        )

        workflow.add_edge("elicit_information", END)

        # Conditional routing from check_cache
        workflow.add_conditional_edges(
            "check_cache",
            self._route_after_cache_check,
            {
                "cache_hit": "process_response",
                "call_mcp": "call_mcp"
            }
        )

        workflow.add_edge("call_mcp", "process_response")
        workflow.add_edge("process_response", "format_output")
        workflow.add_edge("format_output", END)
        workflow.add_edge("handle_error", END)

        return workflow.compile(checkpointer=self.memory)

    # Node implementations

    async def extract_context_node(self, state: WeatherAgentState) -> Dict[str, Any]:
        """Extract context from query and conversation history.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        try:
            query = state["query"]

            # Extract location from query
            location = self.elicitation_manager.location_elicitor.extract_location_from_query(query)

            # Extract temporal context
            temporal = self.elicitation_manager.temporal_elicitor.extract_temporal_context(query)

            # Analyze query intent
            intent = self.context_analyzer.analyze_query_intent(query)

            # Get location from context if not in query
            if not location and state["conversation_history"]:
                # Check if this is a follow-up query
                if intent["is_follow_up"] and state["previous_locations"]:
                    location = state["previous_locations"][-1]

            return {
                "location": location,
                "temporal_context": temporal,
                "state": "extracting_context",
                "response_metadata": {"intent": intent}
            }

        except Exception as e:
            logger.error(f"Error extracting context: {e}")
            return {
                "state": "error",
                "error": str(e),
                "error_type": "context_extraction"
            }

    async def check_elicitation_node(self, state: WeatherAgentState) -> Dict[str, Any]:
        """Check if elicitation is needed.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        try:
            # Check if location elicitation is needed
            if not state["location"]:
                elicitation = self.elicitation_manager.location_elicitor.create_elicitation_request(
                    state["query"],
                    {"recent_locations": state["previous_locations"]}
                )
                return {
                    "needs_elicitation": True,
                    "elicitation_type": "location",
                    "elicitation_message": elicitation.message,
                    "elicitation_options": elicitation.options,
                    "state": "eliciting_location"
                }

            # Check if location is ambiguous
            if self.elicitation_manager.location_elicitor.is_ambiguous_location(state["location"]):
                elicitation = self.elicitation_manager.location_elicitor.create_disambiguation_request(
                    state["location"]
                )
                return {
                    "needs_elicitation": True,
                    "elicitation_type": "clarification",
                    "elicitation_message": elicitation.message,
                    "elicitation_options": elicitation.options,
                    "state": "eliciting_location"
                }

            # Check if temporal clarification is needed (for certain queries)
            if state["response_metadata"] and state["response_metadata"].get("intent", {}).get("is_forecast"):
                if not state["temporal_context"]:
                    if self.elicitation_manager.temporal_elicitor.needs_temporal_clarification(state["query"]):
                        elicitation = self.elicitation_manager.temporal_elicitor.create_temporal_elicitation()
                        return {
                            "needs_elicitation": True,
                            "elicitation_type": "temporal",
                            "elicitation_message": elicitation.message,
                            "elicitation_options": elicitation.options,
                            "state": "eliciting_temporal"
                        }

            # No elicitation needed
            return {
                "needs_elicitation": False,
                "state": "checking_cache"
            }

        except Exception as e:
            logger.error(f"Error checking elicitation: {e}")
            return {
                "state": "error",
                "error": str(e),
                "error_type": "elicitation_check"
            }

    async def elicit_information_node(self, state: WeatherAgentState) -> Dict[str, Any]:
        """Handle elicitation response.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        # This node formats the elicitation response
        # In actual use, the user's response would be processed in a new workflow run
        return {
            "response": state["elicitation_message"],
            "state": "complete"
        }

    async def check_cache_node(self, state: WeatherAgentState) -> Dict[str, Any]:
        """Check cache for weather data.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(
                state["location"],
                state["temporal_context"]
            )

            # For now, simulate cache miss (Redis integration in next phase)
            # In production, would check Redis cache here
            cache_hit = False
            cached_data = None

            return {
                "cache_key": cache_key,
                "cache_hit": cache_hit,
                "cached_data": cached_data,
                "state": "checking_cache"
            }

        except Exception as e:
            logger.error(f"Error checking cache: {e}")
            return {
                "state": "error",
                "error": str(e),
                "error_type": "cache_check"
            }

    async def call_mcp_node(self, state: WeatherAgentState) -> Dict[str, Any]:
        """Call MCP server for weather data.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        try:
            mcp_client = await get_mcp_client()

            # Determine what type of weather data to fetch
            intent = state.get("response_metadata", {}).get("intent", {})

            # Get weather data - MCP server provides current + forecast in one call
            weather_data = await mcp_client.get_weather_smart(state["location"])

            # Check for alerts in the forecast text if requested
            if intent.get("is_alert"):
                alerts = await mcp_client.extract_alerts_from_forecast(weather_data)
                weather_data["alerts"] = alerts

            # Add temporal context to help format response
            weather_data["temporal_context"] = state.get("temporal_context", "current")
            weather_data["is_forecast_request"] = intent.get("is_forecast", False)

            return {
                "mcp_response": weather_data,
                "weather_data": weather_data,
                "data_freshness": datetime.utcnow(),
                "state": "calling_mcp"
            }

        except Exception as e:
            logger.error(f"Error calling MCP: {e}")

            # Check if we should retry
            if state["retry_count"] < 3:
                return {
                    "retry_count": state["retry_count"] + 1,
                    "error": str(e),
                    "state": "calling_mcp"  # Will retry
                }

            return {
                "state": "error",
                "error": str(e),
                "error_type": "mcp_call"
            }

    async def process_response_node(self, state: WeatherAgentState) -> Dict[str, Any]:
        """Process weather data into response.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        try:
            weather_data = state["cached_data"] if state["cache_hit"] else state["weather_data"]

            if not weather_data:
                return {
                    "state": "error",
                    "error": "No weather data available",
                    "error_type": "no_data"
                }

            # Extract relevant information
            response_parts = []
            location_display = state["location"]

            # Process based on data type
            if "alerts" in weather_data:
                alerts = weather_data["alerts"]
                if alerts:
                    response_parts.append(f"Weather alerts for {location_display}:")
                    for alert in alerts:
                        response_parts.append(
                            f"• {alert.get('severity', 'Alert')}: {alert.get('headline', 'Weather alert')}"
                        )
                else:
                    response_parts.append(f"No active weather alerts for {location_display}.")

            elif "forecasts" in weather_data:
                response_parts.append(f"Weather forecast for {location_display}:")
                for forecast in weather_data.get("forecasts", [])[:5]:
                    date = forecast.get("date", "Unknown")
                    high = forecast.get("high_temp", "?")
                    low = forecast.get("low_temp", "?")
                    conditions = forecast.get("conditions", "Unknown")
                    response_parts.append(f"• {date}: {conditions}, High {high}°F, Low {low}°F")

            else:
                # Current weather
                temp = weather_data.get("temperature", "Unknown")
                conditions = weather_data.get("conditions", "Unknown")
                humidity = weather_data.get("humidity", "Unknown")
                response_parts.append(
                    f"Current weather in {location_display}: {temp}°F, {conditions}, "
                    f"Humidity: {humidity}%"
                )

            # Check for severe alerts
            if "alerts" in weather_data:
                severe_alerts = [
                    a for a in weather_data["alerts"]
                    if a.get("severity") in ["Severe", "Extreme"]
                ]
                if severe_alerts:
                    response_parts.append("\n⚠️ SEVERE WEATHER ALERT ⚠️")

            response = "\n".join(response_parts)

            return {
                "response": response,
                "state": "processing_response"
            }

        except Exception as e:
            logger.error(f"Error processing response: {e}")
            return {
                "state": "error",
                "error": str(e),
                "error_type": "response_processing"
            }

    async def format_output_node(self, state: WeatherAgentState) -> Dict[str, Any]:
        """Format final output.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        try:
            # Add metadata to response
            metadata = {
                "query_id": state["query_id"],
                "session_id": state["session_id"],
                "cache_hit": state["cache_hit"],
                "data_freshness": state["data_freshness"].isoformat() if state["data_freshness"] else None,
                "location_resolved": state["location"]
            }

            # Update conversation history
            conversation_turn = {
                "user": state["query"],
                "assistant": state["response"]
            }

            updated_history = list(state["conversation_history"])
            updated_history.append(conversation_turn)

            # Update previous locations
            updated_locations = list(state["previous_locations"])
            if state["location"] and state["location"] not in updated_locations:
                updated_locations.append(state["location"])
                if len(updated_locations) > 5:
                    updated_locations = updated_locations[-5:]

            return {
                "response_metadata": metadata,
                "conversation_history": updated_history,
                "previous_locations": updated_locations,
                "conversation_turn": state["conversation_turn"] + 1,
                "state": "complete"
            }

        except Exception as e:
            logger.error(f"Error formatting output: {e}")
            return {
                "state": "error",
                "error": str(e),
                "error_type": "output_formatting"
            }

    async def handle_error_node(self, state: WeatherAgentState) -> Dict[str, Any]:
        """Handle errors in workflow.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        error_messages = {
            "context_extraction": "I had trouble understanding your query. Please try rephrasing.",
            "elicitation_check": "I couldn't determine what information you need. Please be more specific.",
            "cache_check": "There was an issue checking cached data.",
            "mcp_call": "I couldn't fetch weather data at the moment. Please try again.",
            "response_processing": "I had trouble processing the weather information.",
            "output_formatting": "There was an issue formatting the response.",
            "no_data": "No weather data is available for that location."
        }

        error_type = state.get("error_type", "unknown")
        error_message = error_messages.get(
            error_type,
            "I encountered an error processing your request. Please try again."
        )

        return {
            "response": error_message,
            "state": "complete"
        }

    # Routing functions

    def _route_after_elicitation_check(self, state: WeatherAgentState) -> str:
        """Route after elicitation check.

        Args:
            state: Current workflow state

        Returns:
            Next node name
        """
        if state["needs_elicitation"]:
            return "needs_elicitation"
        return "check_cache"

    def _route_after_cache_check(self, state: WeatherAgentState) -> str:
        """Route after cache check.

        Args:
            state: Current workflow state

        Returns:
            Next node name
        """
        if state["cache_hit"]:
            return "cache_hit"
        return "call_mcp"

    # Utility methods

    def _generate_cache_key(self, location: str, temporal: Optional[str]) -> str:
        """Generate cache key for weather data.

        Args:
            location: Location string
            temporal: Temporal context

        Returns:
            Cache key string
        """
        key_parts = [location.lower()]
        if temporal:
            key_parts.append(temporal)

        key_string = ":".join(key_parts)
        return f"weather:{hashlib.md5(key_string.encode()).hexdigest()}"

    # Public methods

    async def process_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a weather query through the workflow.

        Args:
            query: User's weather query
            context: Optional context information

        Returns:
            Workflow result
        """
        # Create initial state
        initial_state = create_initial_agent_state(
            query=query,
            session_id=self.session_id,
            user_id=self.user_id
        )

        # Add context if provided
        if context:
            if "conversation_history" in context:
                initial_state["conversation_history"] = context["conversation_history"]
            if "previous_locations" in context:
                initial_state["previous_locations"] = context["previous_locations"]
            if "conversation_turn" in context:
                initial_state["conversation_turn"] = context["conversation_turn"]

        # Run workflow
        try:
            result = await self.workflow.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": self.session_id}}
            )

            # Validate final state
            validation = validate_agent_state(result)
            if not validation["is_valid"]:
                logger.warning(f"Invalid final state: {validation['validation_errors']}")

            return {
                "success": result["state"] == "complete",
                "response": result["response"],
                "metadata": result.get("response_metadata", {}),
                "state_summary": get_state_summary(result)
            }

        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            return {
                "success": False,
                "response": "I encountered an error processing your request.",
                "error": str(e)
            }