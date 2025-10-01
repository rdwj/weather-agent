"""Rate limiting service with token bucket implementation using Redis."""

import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
import time

from ..lib.redis_client import (
    RedisConnectionManager,
    RedisKeyBuilder,
    RedisOperations,
    get_redis_connection
)

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """Token bucket rate limiter implementation using Redis."""

    def __init__(self,
                 rate: int = 100,  # Tokens per minute
                 capacity: int = 100,  # Max tokens in bucket
                 window: int = 60):  # Time window in seconds
        """Initialize token bucket rate limiter.

        Args:
            rate: Number of tokens to add per window
            capacity: Maximum number of tokens in bucket
            window: Time window in seconds
        """
        self.rate = rate
        self.capacity = capacity
        self.window = window
        self.tokens_per_second = rate / window

    async def check_rate_limit(self,
                              key: str,
                              operations: RedisOperations,
                              tokens_requested: int = 1) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is within rate limit.

        Args:
            key: Redis key for rate limit
            operations: Redis operations instance
            tokens_requested: Number of tokens to consume

        Returns:
            Tuple of (allowed, info dict)
        """
        try:
            client = await operations.connection_manager.get_client()

            # Lua script for atomic token bucket operations
            lua_script = """
                local key = KEYS[1]
                local capacity = tonumber(ARGV[1])
                local tokens_requested = tonumber(ARGV[2])
                local fill_rate = tonumber(ARGV[3])
                local window = tonumber(ARGV[4])
                local now = tonumber(ARGV[5])

                local bucket = redis.call('HGETALL', key)
                local tokens = capacity
                local last_refill = now

                if #bucket > 0 then
                    -- Parse existing bucket
                    for i = 1, #bucket, 2 do
                        if bucket[i] == 'tokens' then
                            tokens = tonumber(bucket[i + 1])
                        elseif bucket[i] == 'last_refill' then
                            last_refill = tonumber(bucket[i + 1])
                        end
                    end

                    -- Calculate tokens to add based on time passed
                    local time_passed = now - last_refill
                    local tokens_to_add = time_passed * fill_rate
                    tokens = math.min(capacity, tokens + tokens_to_add)
                end

                -- Check if enough tokens available
                if tokens >= tokens_requested then
                    -- Consume tokens
                    tokens = tokens - tokens_requested
                    redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
                    redis.call('EXPIRE', key, window)
                    return {1, tokens, capacity}
                else
                    -- Not enough tokens
                    redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
                    redis.call('EXPIRE', key, window)
                    return {0, tokens, capacity}
                end
            """

            # Execute script
            result = await client.eval(
                lua_script,
                1,  # Number of keys
                key,  # KEYS[1]
                self.capacity,  # ARGV[1]
                tokens_requested,  # ARGV[2]
                self.tokens_per_second,  # ARGV[3]
                self.window,  # ARGV[4]
                time.time()  # ARGV[5]
            )

            allowed = bool(result[0])
            tokens_remaining = int(result[1])
            capacity = int(result[2])

            # Calculate when tokens will be available
            retry_after = 0
            if not allowed:
                tokens_needed = tokens_requested - tokens_remaining
                retry_after = int(tokens_needed / self.tokens_per_second)

            return allowed, {
                "allowed": allowed,
                "tokens_remaining": tokens_remaining,
                "capacity": capacity,
                "retry_after": retry_after,
                "rate": self.rate,
                "window": self.window
            }

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # On error, allow request but log warning
            return True, {
                "allowed": True,
                "error": str(e),
                "tokens_remaining": -1,
                "capacity": self.capacity
            }


class RateLimitService:
    """Service for managing rate limiting across different scopes."""

    # Default rate limits
    GLOBAL_RATE = 1000  # Per minute
    USER_RATE = 100  # Per minute
    BURST_CAPACITY = 150  # Max tokens for burst

    def __init__(self, connection_manager: Optional[RedisConnectionManager] = None):
        """Initialize rate limit service.

        Args:
            connection_manager: Optional Redis connection manager
        """
        self.connection_manager = connection_manager
        self.operations: Optional[RedisOperations] = None
        self._initialized = False

        # Create rate limiters
        self.global_limiter = TokenBucketRateLimiter(
            rate=self.GLOBAL_RATE,
            capacity=self.BURST_CAPACITY,
            window=60
        )
        self.user_limiter = TokenBucketRateLimiter(
            rate=self.USER_RATE,
            capacity=min(self.BURST_CAPACITY, int(self.USER_RATE * 1.5)),
            window=60
        )

    async def initialize(self) -> None:
        """Initialize the service."""
        if self._initialized:
            return

        if not self.connection_manager:
            self.connection_manager = await get_redis_connection()

        self.operations = RedisOperations(self.connection_manager)
        self._initialized = True

    async def check_rate_limit(self,
                              user_id: str,
                              tokens: int = 1,
                              check_global: bool = True) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is within rate limits.

        Args:
            user_id: User identifier
            tokens: Number of tokens to consume
            check_global: Whether to check global rate limit

        Returns:
            Tuple of (allowed, info dict)
        """
        await self.initialize()

        info = {
            "user_id": user_id,
            "tokens_requested": tokens,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Check global rate limit first
        if check_global:
            global_key = RedisKeyBuilder.rate_limit_key("global")
            global_allowed, global_info = await self.global_limiter.check_rate_limit(
                global_key, self.operations, tokens
            )

            info["global"] = global_info

            if not global_allowed:
                info["limited_by"] = "global"
                info["retry_after"] = global_info["retry_after"]
                return False, info

        # Check user rate limit
        user_key = RedisKeyBuilder.rate_limit_key(user_id)
        user_allowed, user_info = await self.user_limiter.check_rate_limit(
            user_key, self.operations, tokens
        )

        info["user"] = user_info

        if not user_allowed:
            info["limited_by"] = "user"
            info["retry_after"] = user_info["retry_after"]
            return False, info

        info["allowed"] = True
        return True, info

    async def check_cached_request(self,
                                  user_id: str,
                                  cache_key: str) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit for cached request (doesn't consume tokens).

        Args:
            user_id: User identifier
            cache_key: Cache key to check

        Returns:
            Tuple of (is_cached, info dict)
        """
        await self.initialize()

        # Check if cache exists
        cache_exists = await self.operations.exists(cache_key)

        if cache_exists:
            # Don't consume tokens for cached responses
            logger.debug(f"Cached response for user {user_id}, no rate limit consumed")
            return True, {
                "cached": True,
                "tokens_consumed": 0,
                "cache_key": cache_key
            }

        # Not cached, will need to consume tokens
        return False, {
            "cached": False,
            "cache_key": cache_key
        }

    async def get_limit_status(self, user_id: str) -> Dict[str, Any]:
        """Get current rate limit status for a user.

        Args:
            user_id: User identifier

        Returns:
            Status dictionary
        """
        await self.initialize()

        status = {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            # Get user limit status
            user_key = RedisKeyBuilder.rate_limit_key(user_id)
            user_data = await self.operations.get_json(user_key) or {}

            tokens = user_data.get("tokens", self.user_limiter.capacity)
            status["user_limit"] = {
                "tokens_remaining": tokens,
                "capacity": self.user_limiter.capacity,
                "rate": self.user_limiter.rate,
                "window_seconds": self.user_limiter.window,
                "percent_remaining": (tokens / self.user_limiter.capacity) * 100
            }

            # Get global limit status
            global_key = RedisKeyBuilder.rate_limit_key("global")
            global_data = await self.operations.get_json(global_key) or {}

            global_tokens = global_data.get("tokens", self.global_limiter.capacity)
            status["global_limit"] = {
                "tokens_remaining": global_tokens,
                "capacity": self.global_limiter.capacity,
                "rate": self.global_limiter.rate,
                "window_seconds": self.global_limiter.window,
                "percent_remaining": (global_tokens / self.global_limiter.capacity) * 100
            }

        except Exception as e:
            logger.error(f"Failed to get limit status: {e}")
            status["error"] = str(e)

        return status

    async def reset_user_limit(self, user_id: str) -> bool:
        """Reset rate limit for a specific user.

        Args:
            user_id: User identifier

        Returns:
            True if reset successful
        """
        await self.initialize()

        try:
            user_key = RedisKeyBuilder.rate_limit_key(user_id)
            deleted = await self.operations.delete(user_key)
            logger.info(f"Reset rate limit for user {user_id}")
            return bool(deleted)
        except Exception as e:
            logger.error(f"Failed to reset user limit: {e}")
            return False

    async def set_custom_limit(self,
                              user_id: str,
                              rate: int,
                              capacity: Optional[int] = None) -> bool:
        """Set custom rate limit for a specific user.

        Args:
            user_id: User identifier
            rate: Custom rate (tokens per minute)
            capacity: Optional custom capacity

        Returns:
            True if successful
        """
        await self.initialize()

        try:
            # Store custom limit configuration
            config_key = f"ratelimit:config:{user_id}"
            config_data = {
                "rate": rate,
                "capacity": capacity or int(rate * 1.5),
                "configured_at": datetime.utcnow().isoformat()
            }

            success = await self.operations.set_json(config_key, config_data)
            if success:
                logger.info(f"Set custom rate limit for user {user_id}: {rate}/min")

            return success

        except Exception as e:
            logger.error(f"Failed to set custom limit: {e}")
            return False

    async def get_rate_limit_metrics(self) -> Dict[str, Any]:
        """Get rate limiting metrics.

        Returns:
            Metrics dictionary
        """
        await self.initialize()

        try:
            # Count rate limited requests in last hour
            limited_count = 0
            allowed_count = 0

            now = datetime.utcnow()
            for minutes_ago in range(60):
                timestamp = (now - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%d-%H-%M")

                limited_key = RedisKeyBuilder.metrics_key("rate_limited", timestamp)
                allowed_key = RedisKeyBuilder.metrics_key("rate_allowed", timestamp)

                client = await self.connection_manager.get_client()
                limited = await client.get(limited_key)
                allowed = await client.get(allowed_key)

                if limited:
                    limited_count += int(limited)
                if allowed:
                    allowed_count += int(allowed)

            total_requests = limited_count + allowed_count
            limit_rate = (limited_count / total_requests * 100) if total_requests > 0 else 0

            return {
                "total_requests": total_requests,
                "allowed_requests": allowed_count,
                "limited_requests": limited_count,
                "limit_rate_percent": limit_rate,
                "time_window": "last_hour",
                "global_capacity": self.global_limiter.capacity,
                "user_capacity": self.user_limiter.capacity
            }

        except Exception as e:
            logger.error(f"Failed to get rate limit metrics: {e}")
            return {}

    async def record_rate_limit_hit(self, user_id: str, limited_by: str) -> None:
        """Record a rate limit hit for metrics.

        Args:
            user_id: User identifier
            limited_by: What caused the limit (user/global)
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H-%M")
        key = RedisKeyBuilder.metrics_key("rate_limited", timestamp)
        await self.operations.incr(key)
        await self.operations.expire(key, 3600)  # 1 hour TTL

        # Record per-user metrics
        user_key = RedisKeyBuilder.metrics_key(f"rate_limited_user:{user_id}", timestamp)
        await self.operations.incr(user_key)
        await self.operations.expire(user_key, 3600)

    async def record_allowed_request(self, user_id: str) -> None:
        """Record an allowed request for metrics.

        Args:
            user_id: User identifier
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H-%M")
        key = RedisKeyBuilder.metrics_key("rate_allowed", timestamp)
        await self.operations.incr(key)
        await self.operations.expire(key, 3600)  # 1 hour TTL