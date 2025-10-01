"""Fallback service for graceful degradation when MCP is unavailable."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import structlog
import httpx

from src.lib.exceptions import MCPConnectionError, WeatherServiceError, TimeoutError
from src.services.cache_service import CacheService
from src.lib.logging_config import get_logger

logger = get_logger(__name__)


class WeatherFallbackService:
    """
    Provides fallback functionality when MCP weather server is unavailable.

    This service implements graceful degradation strategies:
    1. Return cached data if available (even if stale)
    2. Provide basic weather information from alternative sources
    3. Return helpful error messages with suggestions
    """

    def __init__(self, cache_service: Optional[CacheService] = None):
        """
        Initialize the fallback service.

        Args:
            cache_service: Cache service instance for retrieving cached data
        """
        self.cache_service = cache_service or CacheService()
        self.fallback_api_url = "https://wttr.in"  # Free weather service as fallback

    async def get_fallback_weather(
        self,
        location: str,
        user_id: str,
        include_forecast: bool = False
    ) -> Dict[str, Any]:
        """
        Get weather data from fallback sources.

        Args:
            location: Location to get weather for
            user_id: User ID for cache lookup
            include_forecast: Whether to include forecast data

        Returns:
            Weather data from fallback source or cache
        """
        logger.warning(
            "Using fallback weather service",
            location=location,
            user_id=user_id
        )

        # First, try to get any cached data (even if stale)
        cached_data = await self._get_stale_cache(location, user_id)
        if cached_data:
            logger.info(
                "Returning stale cached data",
                location=location,
                cache_age_hours=cached_data.get("cache_age_hours", 0)
            )
            return self._format_stale_cache_response(cached_data)

        # Try alternative weather API
        try:
            weather_data = await self._fetch_from_wttr(location)
            if weather_data:
                logger.info(
                    "Successfully retrieved data from fallback API",
                    location=location
                )
                return self._format_fallback_response(weather_data, location)
        except Exception as e:
            logger.error(
                "Fallback API also failed",
                error=str(e),
                location=location
            )

        # Return a helpful error response with suggestions
        return self._create_degraded_response(location)

    async def _get_stale_cache(
        self,
        location: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve stale cached data if available.

        Args:
            location: Location to search for in cache
            user_id: User ID for cache key

        Returns:
            Cached data if available, None otherwise
        """
        if not self.cache_service:
            return None

        # Try multiple cache keys
        cache_keys = [
            f"weather_query:{user_id}:{location}",
            f"weather_data:{location}",
            f"weather_cache:{location.lower()}"
        ]

        for cache_key in cache_keys:
            try:
                # Get data without checking TTL (allow stale data)
                cached_data = await self.cache_service.get_raw(cache_key)
                if cached_data:
                    # Calculate how old the cache is
                    if "timestamp" in cached_data:
                        cache_time = datetime.fromisoformat(cached_data["timestamp"])
                        age = datetime.utcnow() - cache_time
                        cached_data["cache_age_hours"] = age.total_seconds() / 3600
                    return cached_data
            except Exception as e:
                logger.debug(f"Cache lookup failed for {cache_key}: {e}")
                continue

        return None

    async def _fetch_from_wttr(
        self,
        location: str,
        timeout: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch weather from wttr.in as fallback.

        Args:
            location: Location to get weather for
            timeout: Request timeout in seconds

        Returns:
            Weather data if successful, None otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Request JSON format from wttr.in
                response = await client.get(
                    f"{self.fallback_api_url}/{location}",
                    params={"format": "j1"},
                    headers={"User-Agent": "WeatherAgent/1.0"}
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(
                        "Fallback API returned error",
                        status_code=response.status_code,
                        location=location
                    )
                    return None

        except asyncio.TimeoutError:
            logger.error("Fallback API timeout", location=location)
            return None
        except Exception as e:
            logger.error(
                "Fallback API request failed",
                error=str(e),
                location=location
            )
            return None

    def _format_stale_cache_response(
        self,
        cached_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format stale cached data for response.

        Args:
            cached_data: The cached weather data

        Returns:
            Formatted response with stale data warning
        """
        age_hours = cached_data.get("cache_age_hours", 0)

        response = {
            "response": f"⚠️ Weather service is temporarily unavailable. Showing cached data from {age_hours:.1f} hours ago.",
            "weather_data": cached_data.get("weather_data", {}),
            "data_freshness": cached_data.get("timestamp", datetime.utcnow().isoformat()),
            "cache_hit": True,
            "degraded_mode": True,
            "cache_age_hours": age_hours,
            "alerts": []
        }

        # Add warning about data staleness
        if age_hours > 24:
            response["response"] += " This data may be significantly outdated."
        elif age_hours > 6:
            response["response"] += " This data may be outdated."

        return response

    def _format_fallback_response(
        self,
        wttr_data: Dict[str, Any],
        location: str
    ) -> Dict[str, Any]:
        """
        Format wttr.in data to match our response format.

        Args:
            wttr_data: Data from wttr.in
            location: Location string

        Returns:
            Formatted weather response
        """
        try:
            current = wttr_data.get("current_condition", [{}])[0]
            weather = wttr_data.get("weather", [{}])[0]

            # Extract basic weather information
            temperature = current.get("temp_F", "Unknown")
            description = current.get("weatherDesc", [{}])[0].get("value", "Unknown conditions")
            humidity = current.get("humidity", "Unknown")
            wind_speed = current.get("windspeedMiles", "Unknown")

            weather_data = {
                "location": location,
                "temperature": f"{temperature}°F",
                "description": description,
                "humidity": f"{humidity}%",
                "wind_speed": f"{wind_speed} mph",
                "source": "fallback_service"
            }

            return {
                "response": f"Weather in {location}: {description}, {temperature}°F. (Note: Using backup weather service)",
                "weather_data": weather_data,
                "data_freshness": datetime.utcnow().isoformat(),
                "cache_hit": False,
                "degraded_mode": True,
                "alerts": []
            }

        except Exception as e:
            logger.error(
                "Failed to parse fallback weather data",
                error=str(e)
            )
            return self._create_degraded_response(location)

    def _create_degraded_response(
        self,
        location: str
    ) -> Dict[str, Any]:
        """
        Create a degraded response when no data is available.

        Args:
            location: Location that was requested

        Returns:
            Degraded response with helpful message
        """
        return {
            "response": (
                f"I'm unable to retrieve weather information for {location} at the moment. "
                "The weather service is temporarily unavailable. Please try again in a few minutes, "
                "or check a weather website directly."
            ),
            "weather_data": None,
            "data_freshness": datetime.utcnow().isoformat(),
            "cache_hit": False,
            "degraded_mode": True,
            "alerts": [],
            "suggestions": [
                "Try again in a few minutes",
                "Check weather.gov for official forecasts",
                "Use a weather app on your device"
            ]
        }


class MCPHealthMonitor:
    """
    Monitors MCP server health and implements circuit breaker pattern.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: int = 60,
        check_interval: int = 30
    ):
        """
        Initialize health monitor.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            check_interval: Seconds between health checks
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.check_interval = check_interval

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.circuit_open = False
        self.last_check_time: Optional[datetime] = None

    def record_success(self):
        """Record a successful MCP call."""
        self.failure_count = 0
        self.circuit_open = False
        self.last_failure_time = None
        logger.debug("MCP call succeeded, circuit closed")

    def record_failure(self):
        """Record a failed MCP call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.circuit_open = True
            logger.warning(
                "Circuit breaker opened",
                failure_count=self.failure_count,
                threshold=self.failure_threshold
            )

    def is_available(self) -> bool:
        """
        Check if MCP should be attempted.

        Returns:
            True if MCP calls should be attempted, False otherwise
        """
        if not self.circuit_open:
            return True

        # Check if recovery timeout has passed
        if self.last_failure_time:
            time_since_failure = (datetime.utcnow() - self.last_failure_time).total_seconds()
            if time_since_failure > self.recovery_timeout:
                logger.info(
                    "Attempting circuit recovery",
                    time_since_failure=time_since_failure
                )
                self.circuit_open = False
                self.failure_count = 0
                return True

        return False

    async def check_health(self, mcp_client) -> bool:
        """
        Perform health check on MCP server.

        Args:
            mcp_client: MCP client instance

        Returns:
            True if healthy, False otherwise
        """
        # Rate limit health checks
        if self.last_check_time:
            time_since_check = (datetime.utcnow() - self.last_check_time).total_seconds()
            if time_since_check < self.check_interval:
                return not self.circuit_open

        self.last_check_time = datetime.utcnow()

        try:
            # Perform health check (ping or simple query)
            result = await mcp_client.check_connection()
            if result:
                self.record_success()
                return True
            else:
                self.record_failure()
                return False
        except Exception as e:
            logger.error(
                "Health check failed",
                error=str(e)
            )
            self.record_failure()
            return False