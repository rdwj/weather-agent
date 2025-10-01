#!/usr/bin/env python3
"""
Cache manager for Weather Agent with Redis support.

Supports both in-memory and Redis caching for production deployments.
"""

import os
import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Dict[str, Any], ttl: int = 900) -> None:
        """Set value in cache with TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close cache connection."""
        pass


class MemoryCacheBackend(CacheBackend):
    """In-memory cache backend for development."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl = timedelta(seconds=900)  # 15 minutes default

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from memory cache."""
        if key in self._cache:
            entry = self._cache[key]
            if datetime.utcnow() < entry["expires"]:
                logger.debug(f"Cache hit for key: {key}")
                return entry["data"]
            else:
                # Remove expired entry
                del self._cache[key]
                logger.debug(f"Cache expired for key: {key}")
        return None

    async def set(self, key: str, value: Dict[str, Any], ttl: int = 900) -> None:
        """Set value in memory cache."""
        self._cache[key] = {
            "data": value,
            "expires": datetime.utcnow() + timedelta(seconds=ttl),
            "cached_at": datetime.utcnow()
        }
        logger.debug(f"Cached key: {key} with TTL: {ttl}s")

    async def delete(self, key: str) -> None:
        """Delete value from memory cache."""
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Deleted cache key: {key}")

    async def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        logger.info("Memory cache cleared")

    async def close(self) -> None:
        """No cleanup needed for memory cache."""
        pass


class RedisCacheBackend(CacheBackend):
    """Redis cache backend for production."""

    def __init__(self, host: str = "localhost", port: int = 6379,
                 db: int = 0, password: Optional[str] = None):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self._client = None
        self._connected = False

    async def _ensure_connected(self):
        """Ensure Redis connection is established."""
        if not self._connected:
            try:
                import aioredis

                redis_url = f"redis://{self.host}:{self.port}/{self.db}"
                if self.password:
                    redis_url = f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"

                self._client = await aioredis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                self._connected = True
                logger.info(f"Connected to Redis at {self.host}:{self.port}")
            except ImportError:
                logger.error("aioredis not installed. Falling back to memory cache.")
                raise
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from Redis."""
        try:
            await self._ensure_connected()
            value = await self._client.get(key)
            if value:
                logger.debug(f"Redis cache hit for key: {key}")
                return json.loads(value)
        except Exception as e:
            logger.warning(f"Redis get failed for {key}: {e}")
        return None

    async def set(self, key: str, value: Dict[str, Any], ttl: int = 900) -> None:
        """Set value in Redis with TTL."""
        try:
            await self._ensure_connected()

            # Add metadata
            cache_data = {
                **value,
                "_cached_at": datetime.utcnow().isoformat()
            }

            await self._client.set(
                key,
                json.dumps(cache_data),
                ex=ttl
            )
            logger.debug(f"Redis cached key: {key} with TTL: {ttl}s")
        except Exception as e:
            logger.warning(f"Redis set failed for {key}: {e}")

    async def delete(self, key: str) -> None:
        """Delete value from Redis."""
        try:
            await self._ensure_connected()
            await self._client.delete(key)
            logger.debug(f"Deleted Redis key: {key}")
        except Exception as e:
            logger.warning(f"Redis delete failed for {key}: {e}")

    async def clear(self) -> None:
        """Clear all cache entries (flush DB)."""
        try:
            await self._ensure_connected()
            await self._client.flushdb()
            logger.info("Redis cache cleared")
        except Exception as e:
            logger.warning(f"Redis clear failed: {e}")

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._connected = False
            logger.info("Redis connection closed")


class CacheManager:
    """
    Main cache manager that selects appropriate backend.
    """

    def __init__(self):
        self._backend: Optional[CacheBackend] = None
        self._initialized = False

    async def initialize(self) -> bool:
        """
        Initialize cache backend based on environment configuration.

        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True

        cache_type = os.getenv("CACHE_TYPE", "memory").lower()

        try:
            if cache_type == "redis":
                # Try Redis first
                redis_host = os.getenv("REDIS_HOST", "localhost")
                redis_port = int(os.getenv("REDIS_PORT", "6379"))
                redis_db = int(os.getenv("REDIS_DB", "0"))
                redis_password = os.getenv("REDIS_PASSWORD")

                logger.info(f"Initializing Redis cache at {redis_host}:{redis_port}")
                self._backend = RedisCacheBackend(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    password=redis_password
                )

                # Test connection
                await self._backend._ensure_connected()
                logger.info("Redis cache initialized successfully")
            else:
                # Default to memory cache
                logger.info("Using in-memory cache")
                self._backend = MemoryCacheBackend()

            self._initialized = True
            return True

        except Exception as e:
            logger.warning(f"Failed to initialize {cache_type} cache: {e}")
            logger.info("Falling back to in-memory cache")

            # Fallback to memory cache
            self._backend = MemoryCacheBackend()
            self._initialized = True
            return True

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from cache."""
        if not self._initialized:
            await self.initialize()

        if self._backend:
            return await self._backend.get(key)
        return None

    async def set(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        if not self._initialized:
            await self.initialize()

        if self._backend:
            ttl = ttl or int(os.getenv("CACHE_TTL", "900"))
            await self._backend.set(key, value, ttl)

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        if not self._initialized:
            await self.initialize()

        if self._backend:
            await self._backend.delete(key)

    async def clear(self) -> None:
        """Clear all cache entries."""
        if not self._initialized:
            await self.initialize()

        if self._backend:
            await self._backend.clear()

    async def close(self) -> None:
        """Close cache connections."""
        if self._backend:
            await self._backend.close()
            self._initialized = False

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            "backend": type(self._backend).__name__ if self._backend else "None",
            "initialized": self._initialized,
            "type": os.getenv("CACHE_TYPE", "memory")
        }

        if isinstance(self._backend, MemoryCacheBackend):
            stats["entries"] = len(self._backend._cache)
        elif isinstance(self._backend, RedisCacheBackend):
            stats["host"] = self._backend.host
            stats["port"] = self._backend.port
            stats["connected"] = self._backend._connected

        return stats


# Global cache manager instance
cache_manager = CacheManager()