"""Workflow nodes and edges implementation for LangGraph weather workflow."""

import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
import asyncio

from langgraph.graph import END
from langgraph.prebuilt import ToolExecutor

from ..lib.agent_state import WeatherAgentState
from ..models.weather_alert import AlertSeverity

logger = logging.getLogger(__name__)


class WeatherWorkflowNodes:
    """Collection of reusable nodes for weather workflow."""

    @staticmethod
    async def validate_input_node(state: WeatherAgentState) -> Dict[str, Any]:
        """Validate input query and initial state.

        Args:
            state: Current workflow state

        Returns:
            State updates with validation results
        """
        try:
            query = state["query"]

            # Basic validation
            if not query or len(query.strip()) == 0:
                return {
                    "state": "error",
                    "error": "Empty query provided",
                    "error_type": "invalid_input"
                }

            if len(query) > 500:
                return {
                    "state": "error",
                    "error": "Query too long (max 500 characters)",
                    "error_type": "invalid_input"
                }

            # Check for PII patterns (simple check)
            sensitive_patterns = ["ssn", "social security", "credit card", "password"]
            query_lower = query.lower()
            for pattern in sensitive_patterns:
                if pattern in query_lower:
                    return {
                        "state": "error",
                        "error": "Query appears to contain sensitive information",
                        "error_type": "sensitive_content"
                    }

            return {
                "state": "validating_input",
                "query": query.strip()
            }

        except Exception as e:
            logger.error(f"Error validating input: {e}")
            return {
                "state": "error",
                "error": str(e),
                "error_type": "validation_error"
            }

    @staticmethod
    async def enrich_context_node(state: WeatherAgentState) -> Dict[str, Any]:
        """Enrich state with additional context.

        Args:
            state: Current workflow state

        Returns:
            State updates with enriched context
        """
        try:
            updates = {}

            # Add query ID if not present
            if not state["query_id"]:
                import uuid
                updates["query_id"] = str(uuid.uuid4())

            # Set default temporal context if not extracted
            if not state["temporal_context"]:
                # Check if query implies current conditions
                query_lower = state["query"].lower()
                if any(word in query_lower for word in ["current", "now", "right now"]):
                    updates["temporal_context"] = "now"
                else:
                    updates["temporal_context"] = "today"

            # Add timestamp if not present
            if not state["timestamp"]:
                updates["timestamp"] = datetime.utcnow()

            updates["state"] = "enriching_context"
            return updates

        except Exception as e:
            logger.error(f"Error enriching context: {e}")
            return {
                "state": "error",
                "error": str(e),
                "error_type": "context_enrichment"
            }

    @staticmethod
    async def rate_limit_check_node(state: WeatherAgentState) -> Dict[str, Any]:
        """Check rate limiting status.

        Args:
            state: Current workflow state

        Returns:
            State updates with rate limit info
        """
        try:
            # In production, this would check Redis for rate limiting
            # For now, simulate rate limit check

            # Simulate rate limit (would be from Redis in production)
            rate_limit_remaining = 100
            rate_limit_reset = datetime.utcnow() + timedelta(minutes=1)

            if rate_limit_remaining <= 0:
                return {
                    "state": "error",
                    "error": "Rate limit exceeded. Please try again later.",
                    "error_type": "rate_limited",
                    "rate_limit_remaining": 0,
                    "rate_limit_reset": rate_limit_reset
                }

            return {
                "rate_limit_remaining": rate_limit_remaining,
                "rate_limit_reset": rate_limit_reset,
                "state": "checking_rate_limit"
            }

        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            # Don't block on rate limit errors
            return {"state": "checking_rate_limit"}

    @staticmethod
    async def filter_alerts_node(state: WeatherAgentState) -> Dict[str, Any]:
        """Filter weather alerts by severity.

        Args:
            state: Current workflow state

        Returns:
            State updates with filtered alerts
        """
        try:
            if not state["alerts"]:
                return {"state": "filtering_alerts"}

            # Filter for severe and extreme alerts only
            filtered_alerts = [
                alert for alert in state["alerts"]
                if alert.get("severity") in ["Severe", "Extreme"]
            ]

            return {
                "alerts": filtered_alerts,
                "state": "filtering_alerts"
            }

        except Exception as e:
            logger.error(f"Error filtering alerts: {e}")
            return {"state": "filtering_alerts"}

    @staticmethod
    async def fallback_response_node(state: WeatherAgentState) -> Dict[str, Any]:
        """Generate fallback response when MCP is unavailable.

        Args:
            state: Current workflow state

        Returns:
            State updates with fallback response
        """
        try:
            location = state["location"] or "your location"
            fallback_message = (
                f"I'm currently unable to fetch live weather data for {location}. "
                "Please try again in a few moments, or check a weather website directly."
            )

            if state["cache_hit"] and state["cached_data"]:
                # Use cached data if available
                data_age = datetime.utcnow() - state["data_freshness"]
                age_minutes = int(data_age.total_seconds() / 60)
                fallback_message = (
                    f"Using cached weather data from {age_minutes} minutes ago. "
                    "Live data is temporarily unavailable."
                )

            return {
                "response": fallback_message,
                "state": "fallback"
            }

        except Exception as e:
            logger.error(f"Error generating fallback response: {e}")
            return {
                "response": "Weather data is temporarily unavailable.",
                "state": "fallback"
            }


class WorkflowEdges:
    """Edge conditions for workflow routing."""

    @staticmethod
    def should_retry(state: WeatherAgentState) -> bool:
        """Determine if operation should be retried.

        Args:
            state: Current workflow state

        Returns:
            True if should retry
        """
        return (
            state["retry_count"] < 3 and
            state["error_type"] in ["mcp_call", "network_error", "timeout"]
        )

    @staticmethod
    def has_required_context(state: WeatherAgentState) -> bool:
        """Check if state has required context to proceed.

        Args:
            state: Current workflow state

        Returns:
            True if has required context
        """
        return state["location"] is not None

    @staticmethod
    def needs_user_input(state: WeatherAgentState) -> bool:
        """Check if user input is needed.

        Args:
            state: Current workflow state

        Returns:
            True if user input needed
        """
        return state["needs_elicitation"]

    @staticmethod
    def should_use_cache(state: WeatherAgentState) -> bool:
        """Determine if cache should be used.

        Args:
            state: Current workflow state

        Returns:
            True if cache should be used
        """
        # Check if caching is appropriate for the query
        if state["temporal_context"] in ["now", "current"]:
            # Current weather can use cache
            return True
        elif state["temporal_context"] in ["forecast", "tomorrow", "week"]:
            # Forecasts can use longer cache
            return True
        return False


class WorkflowOrchestrator:
    """Orchestrates workflow execution with advanced features."""

    def __init__(self, max_parallel: int = 3):
        """Initialize workflow orchestrator.

        Args:
            max_parallel: Maximum parallel node executions
        """
        self.max_parallel = max_parallel
        self.execution_times: Dict[str, float] = {}

    async def execute_parallel_nodes(self,
                                    nodes: List[Callable],
                                    state: WeatherAgentState) -> Dict[str, Any]:
        """Execute multiple nodes in parallel.

        Args:
            nodes: List of node functions to execute
            state: Current workflow state

        Returns:
            Merged state updates from all nodes
        """
        tasks = []
        for node in nodes[:self.max_parallel]:
            tasks.append(asyncio.create_task(node(state)))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge results
        merged_updates = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Parallel node error: {result}")
                continue
            if isinstance(result, dict):
                merged_updates.update(result)

        return merged_updates

    async def execute_with_timeout(self,
                                  node: Callable,
                                  state: WeatherAgentState,
                                  timeout: float = 30.0) -> Dict[str, Any]:
        """Execute node with timeout.

        Args:
            node: Node function to execute
            state: Current workflow state
            timeout: Timeout in seconds

        Returns:
            State updates or timeout error
        """
        try:
            result = await asyncio.wait_for(
                node(state),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Node execution timed out after {timeout}s")
            return {
                "state": "error",
                "error": f"Operation timed out after {timeout} seconds",
                "error_type": "timeout"
            }

    def track_execution_time(self, node_name: str, duration: float) -> None:
        """Track node execution time.

        Args:
            node_name: Name of the node
            duration: Execution duration in seconds
        """
        self.execution_times[node_name] = duration
        if duration > 5.0:
            logger.warning(f"Slow node execution: {node_name} took {duration:.2f}s")

    def get_execution_metrics(self) -> Dict[str, Any]:
        """Get workflow execution metrics.

        Returns:
            Dictionary of execution metrics
        """
        if not self.execution_times:
            return {}

        times = list(self.execution_times.values())
        return {
            "total_time": sum(times),
            "avg_time": sum(times) / len(times),
            "max_time": max(times),
            "min_time": min(times),
            "node_count": len(times),
            "slow_nodes": [
                name for name, time in self.execution_times.items()
                if time > 5.0
            ]
        }


class ConditionalRouter:
    """Handles conditional routing in workflow."""

    @staticmethod
    def route_by_intent(state: WeatherAgentState) -> str:
        """Route based on query intent.

        Args:
            state: Current workflow state

        Returns:
            Next node name
        """
        intent = state.get("response_metadata", {}).get("intent", {})

        # MCP server provides all weather data in one call
        return "get_current"  # Always use the same endpoint

    @staticmethod
    def route_by_error(state: WeatherAgentState) -> str:
        """Route based on error type.

        Args:
            state: Current workflow state

        Returns:
            Next node name
        """
        error_type = state.get("error_type")

        error_routes = {
            "rate_limited": END,
            "invalid_input": END,
            "sensitive_content": END,
            "mcp_call": "fallback_response",
            "network_error": "retry_with_backoff",
            "timeout": "retry_with_backoff"
        }

        return error_routes.get(error_type, "handle_error")

    @staticmethod
    def route_by_cache_status(state: WeatherAgentState) -> str:
        """Route based on cache status.

        Args:
            state: Current workflow state

        Returns:
            Next node name
        """
        if state["cache_hit"]:
            # Check cache freshness
            if state["data_freshness"]:
                age = datetime.utcnow() - state["data_freshness"]
                if age.total_seconds() > 900:  # 15 minutes
                    return "refresh_cache"
            return "process_cached"
        return "fetch_fresh"


# Utility functions for workflow

def create_node_wrapper(node_func: Callable, node_name: str) -> Callable:
    """Create a wrapper for node functions with logging and timing.

    Args:
        node_func: Original node function
        node_name: Name of the node

    Returns:
        Wrapped node function
    """
    async def wrapped_node(state: WeatherAgentState) -> Dict[str, Any]:
        start_time = datetime.utcnow()
        logger.debug(f"Executing node: {node_name}")

        try:
            result = await node_func(state)
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.debug(f"Node {node_name} completed in {duration:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Error in node {node_name}: {e}")
            return {
                "state": "error",
                "error": str(e),
                "error_type": f"node_error_{node_name}"
            }

    return wrapped_node


def validate_state_transition(from_state: str, to_state: str) -> bool:
    """Validate state transition is allowed.

    Args:
        from_state: Current state
        to_state: Target state

    Returns:
        True if transition is valid
    """
    valid_transitions = {
        "initial": ["extracting_context", "error"],
        "extracting_context": ["checking_cache", "eliciting_location", "error"],
        "checking_cache": ["calling_mcp", "processing_response", "error"],
        "calling_mcp": ["processing_response", "error", "calling_mcp"],  # Allow retry
        "processing_response": ["formatting_output", "error"],
        "formatting_output": ["complete", "error"],
        "error": ["complete"],
        "complete": []  # Terminal state
    }

    allowed = valid_transitions.get(from_state, [])
    return to_state in allowed