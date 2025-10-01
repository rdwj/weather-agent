"""Cache service with TTL using Redis."""

import json
import hashlib
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta

from ..lib.redis_client import (
    RedisConnectionManager,
    RedisKeyBuilder,
    RedisOperations,
    get_redis_connection
)

logger = logging.getLogger(__name__)


class CacheService:
    """Service for caching weather data in Redis with TTL."""

    # Default TTL values (in seconds)
    DEFAULT_WEATHER_TTL = 900  # 15 minutes
    DEFAULT_FORECAST_TTL = 1800  # 30 minutes
    DEFAULT_ALERTS_TTL = 300  # 5 minutes

    def __init__(self, connection_manager: Optional[RedisConnectionManager] = None):
        """Initialize cache service.

        Args:
            connection_manager: Optional Redis connection manager
        """
        self.connection_manager = connection_manager
        self.operations: Optional[RedisOperations] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the service."""
        if self._initialized:
            return

        if not self.connection_manager:
            self.connection_manager = await get_redis_connection()

        self.operations = RedisOperations(self.connection_manager)
        self._initialized = True

    def generate_cache_key(self, cache_type: str, location: str,
                          temporal: Optional[str] = None) -> str:
        """Generate a cache key for weather data.

        Args:
            cache_type: Type of cache (weather, forecast, alerts)
            location: Location string
            temporal: Optional temporal context

        Returns:
            Cache key string
        """
        # Create identifier from location and temporal context
        parts = [location.lower().strip()]
        if temporal:
            parts.append(temporal.lower())

        identifier = ":".join(parts)
        hash_id = hashlib.md5(identifier.encode()).hexdigest()[:12]

        return RedisKeyBuilder.cache_key(cache_type, hash_id)

    async def get(self, key: str) -> Optional[Any]:
        """Get cached data by key.

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found or expired
        """
        await self.initialize()
        return await self.operations.get_json(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set cached data with optional TTL.

        Args:
            key: Cache key
            value: Data to cache
            ttl: Optional TTL in seconds

        Returns:
            True if successful
        """
        await self.initialize()
        ttl = ttl or self.DEFAULT_WEATHER_TTL
        return await self.operations.set_json(key, value, ttl)

    async def get_raw(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached data without checking TTL (for fallback scenarios).

        Args:
            key: Cache key

        Returns:
            Cached data even if stale, None if not found
        """
        await self.initialize()
        # Get data directly without TTL validation
        cached_data = await self.operations.get_json(key)
        if cached_data and "timestamp" not in cached_data and "cached_at" in cached_data:
            cached_data["timestamp"] = cached_data["cached_at"]
        return cached_data

    async def get_weather(self, location: str,
                         temporal: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get cached weather data.

        Args:
            location: Location string
            temporal: Optional temporal context

        Returns:
            Cached weather data or None
        """
        await self.initialize()

        key = self.generate_cache_key("weather", location, temporal)
        cached_data = await self.operations.get_json(key)

        if cached_data:
            # Check if data is still fresh
            cached_at = cached_data.get("cached_at")
            if cached_at:
                age = datetime.utcnow() - datetime.fromisoformat(cached_at)
                if age.total_seconds() > self.DEFAULT_WEATHER_TTL:
                    logger.debug(f"Cache expired for key {key}")
                    return None

            logger.debug(f"Cache hit for key {key}")
            return cached_data.get("data")

        logger.debug(f"Cache miss for key {key}")
        return None

    async def set_weather(self, location: str, data: Dict[str, Any],
                         temporal: Optional[str] = None,
                         ttl: Optional[int] = None) -> bool:
        """Cache weather data.

        Args:
            location: Location string
            data: Weather data to cache
            temporal: Optional temporal context
            ttl: Optional custom TTL in seconds

        Returns:
            True if successful
        """
        await self.initialize()

        key = self.generate_cache_key("weather", location, temporal)
        ttl = ttl or self.DEFAULT_WEATHER_TTL

        cache_entry = {
            "data": data,
            "cached_at": datetime.utcnow().isoformat(),
            "location": location,
            "temporal": temporal
        }

        success = await self.operations.set_json(key, cache_entry, ttl)

        if success:
            logger.debug(f"Cached weather data for {location} with TTL {ttl}s")
            await self._record_cache_write("weather")

        return success

    async def get_weather_cached(self, location: str) -> Optional[Dict[str, Any]]:
        """Get cached forecast data.

        Args:
            location: Location string
            days: Number of forecast days

        Returns:
            Cached forecast data or None
        """
        await self.initialize()

        key = self.generate_cache_key("forecast", location, f"{days}day")
        cached_data = await self.operations.get_json(key)

        if cached_data:
            logger.debug(f"Cache hit for forecast {key}")
            return cached_data.get("data")

        logger.debug(f"Cache miss for forecast {key}")
        return None

    async def set_forecast(self, location: str, data: Dict[str, Any],
                          days: int = 5, ttl: Optional[int] = None) -> bool:
        """Cache forecast data.

        Args:
            location: Location string
            data: Forecast data to cache
            days: Number of forecast days
            ttl: Optional custom TTL in seconds

        Returns:
            True if successful
        """
        await self.initialize()

        key = self.generate_cache_key("forecast", location, f"{days}day")
        ttl = ttl or self.DEFAULT_FORECAST_TTL

        cache_entry = {
            "data": data,
            "cached_at": datetime.utcnow().isoformat(),
            "location": location,
            "days": days
        }

        success = await self.operations.set_json(key, cache_entry, ttl)

        if success:
            logger.debug(f"Cached forecast data for {location} with TTL {ttl}s")
            await self._record_cache_write("forecast")

        return success

    async def extract_alerts_cached(self, weather_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Get cached weather alerts.

        Args:
            location: Location string

        Returns:
            Cached alerts or None
        """
        await self.initialize()

        key = self.generate_cache_key("alerts", location)
        cached_data = await self.operations.get_json(key)

        if cached_data:
            logger.debug(f"Cache hit for alerts {key}")
            return cached_data.get("data", [])

        logger.debug(f"Cache miss for alerts {key}")
        return None

    async def set_alerts(self, location: str, alerts: List[Dict[str, Any]],
                        ttl: Optional[int] = None) -> bool:
        """Cache weather alerts.

        Args:
            location: Location string
            alerts: List of weather alerts
            ttl: Optional custom TTL in seconds

        Returns:
            True if successful
        """
        await self.initialize()

        key = self.generate_cache_key("alerts", location)
        ttl = ttl or self.DEFAULT_ALERTS_TTL

        cache_entry = {
            "data": alerts,
            "cached_at": datetime.utcnow().isoformat(),
            "location": location
        }

        success = await self.operations.set_json(key, cache_entry, ttl)

        if success:
            logger.debug(f"Cached {len(alerts)} alerts for {location} with TTL {ttl}s")
            await self._record_cache_write("alerts")

        return success

    async def invalidate_location(self, location: str) -> int:
        """Invalidate all cached data for a location.

        Args:
            location: Location string

        Returns:
            Number of keys deleted
        """
        await self.initialize()

        # Generate all possible cache keys for location
        keys_to_delete = []

        # Weather caches
        for temporal in [None, "now", "today", "tomorrow"]:
            keys_to_delete.append(self.generate_cache_key("weather", location, temporal))

        # Forecast caches
        for days in [1, 3, 5, 7]:
            keys_to_delete.append(self.generate_cache_key("forecast", location, f"{days}day"))

        # Alerts cache
        keys_to_delete.append(self.generate_cache_key("alerts", location))

        # Delete all keys
        deleted = await self.operations.delete(*keys_to_delete)

        if deleted:
            logger.info(f"Invalidated {deleted} cache entries for {location}")

        return deleted

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        await self.initialize()

        try:
            client = await self.connection_manager.get_client()

            # Count cache keys by type
            weather_count = 0
            forecast_count = 0
            alerts_count = 0
            total_size = 0

            cursor = 0
            pattern = f"{RedisKeyBuilder.CACHE_PREFIX}:*"

            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)

                for key in keys:
                    if ":weather:" in key:
                        weather_count += 1
                    elif ":forecast:" in key:
                        forecast_count += 1
                    elif ":alerts:" in key:
                        alerts_count += 1

                    # Get memory usage (approximate)
                    try:
                        value = await client.get(key)
                        if value:
                            total_size += len(value)
                    except Exception:
                        pass

                if cursor == 0:
                    break

            # Get hit/miss metrics from stored metrics
            hits = await self._get_metric_count("cache_hits")
            misses = await self._get_metric_count("cache_misses")
            hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 0.0

            return {
                "total_keys": weather_count + forecast_count + alerts_count,
                "weather_keys": weather_count,
                "forecast_keys": forecast_count,
                "alerts_keys": alerts_count,
                "total_size_bytes": total_size,
                "cache_hits": hits,
                "cache_misses": misses,
                "hit_rate": hit_rate
            }

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}

    async def clear_expired(self) -> int:
        """Clear expired cache entries.

        Redis handles TTL expiration automatically, but this can be used
        for manual cleanup if needed.

        Returns:
            Number of expired entries cleared
        """
        await self.initialize()

        # Redis handles TTL automatically, so this is mostly informational
        try:
            client = await self.connection_manager.get_client()
            expired = 0

            cursor = 0
            pattern = f"{RedisKeyBuilder.CACHE_PREFIX}:*"

            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)

                for key in keys:
                    ttl = await client.ttl(key)
                    if ttl == -2:  # Key doesn't exist
                        expired += 1

                if cursor == 0:
                    break

            if expired > 0:
                logger.info(f"Found {expired} expired cache entries")

            return expired

        except Exception as e:
            logger.error(f"Failed to clear expired cache: {e}")
            return 0

    async def warm_cache(self, locations: List[str]) -> int:
        """Pre-warm cache for specified locations.

        This is a placeholder - actual implementation would call MCP
        to fetch and cache data for these locations.

        Args:
            locations: List of locations to warm cache for

        Returns:
            Number of locations warmed
        """
        warmed = 0

        for location in locations:
            # In production, this would:
            # 1. Call MCP to get current weather
            # 2. Call MCP to get forecast
            # 3. Call MCP to get alerts
            # 4. Cache all the data

            logger.debug(f"Would warm cache for {location}")
            warmed += 1

        return warmed

    async def _record_cache_write(self, cache_type: str) -> None:
        """Record cache write metric.

        Args:
            cache_type: Type of cache written
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H")
        key = RedisKeyBuilder.metrics_key("cache_writes", timestamp)
        await self.operations.hincrby(key, cache_type, 1)
        await self.operations.expire(key, 86400)  # 24 hour TTL

    async def _get_metric_count(self, metric_type: str) -> int:
        """Get count for a specific metric.

        Args:
            metric_type: Type of metric

        Returns:
            Total count
        """
        # Get metrics for last 24 hours
        count = 0
        now = datetime.utcnow()

        for hours_ago in range(24):
            timestamp = (now - timedelta(hours=hours_ago)).strftime("%Y-%m-%d-%H")
            key = RedisKeyBuilder.metrics_key(metric_type, timestamp)

            try:
                client = await self.connection_manager.get_client()
                values = await client.hvals(key)
                count += sum(int(v) for v in values if v)
            except Exception:
                pass

        return count


class CacheManager:
    """High-level cache manager with strategies."""

    def __init__(self, cache_service: CacheService):
        """Initialize cache manager.

        Args:
            cache_service: Cache service instance
        """
        self.cache_service = cache_service

    async def get_or_fetch(self,
                          cache_type: str,
                          location: str,
                          fetch_func,
                          temporal: Optional[str] = None,
                          ttl: Optional[int] = None) -> Tuple[Dict[str, Any], bool]:
        """Get from cache or fetch and cache.

        Args:
            cache_type: Type of cache
            location: Location string
            fetch_func: Async function to fetch data if not cached
            temporal: Optional temporal context
            ttl: Optional custom TTL

        Returns:
            Tuple of (data, cache_hit)
        """
        # Try cache first
        if cache_type == "weather":
            cached = await self.cache_service.get_weather(location, temporal)
        elif cache_type == "forecast":
            cached = await self.cache_service.get_weather_cached(location)
        elif cache_type == "alerts":
            # For alerts, get weather first then extract
            weather_data = await self.cache_service.get_weather_cached(location)
            cached = await self.cache_service.extract_alerts_cached(weather_data) if weather_data else None
        else:
            cached = None

        if cached:
            return cached, True

        # Fetch fresh data
        try:
            fresh_data = await fetch_func()

            # Cache the fresh data
            if fresh_data:
                if cache_type == "weather":
                    await self.cache_service.set_weather(location, fresh_data, temporal, ttl)
                elif cache_type == "forecast":
                    await self.cache_service.set_forecast(location, fresh_data, ttl=ttl)
                elif cache_type == "alerts":
                    await self.cache_service.set_alerts(location, fresh_data, ttl)

            return fresh_data, False

        except Exception as e:
            logger.error(f"Failed to fetch data for caching: {e}")
            # Return cached data even if expired as fallback
            return cached or {}, cached is not None

    async def invalidate_on_alert(self, location: str, alert_severity: str) -> None:
        """Invalidate cache when severe weather alert detected.

        Args:
            location: Location with alert
            alert_severity: Severity of alert
        """
        if alert_severity in ["Severe", "Extreme"]:
            logger.info(f"Invalidating cache for {location} due to {alert_severity} alert")
            await self.cache_service.invalidate_location(location)