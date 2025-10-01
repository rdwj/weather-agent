"""Shared test fixtures and configuration."""

import pytest
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock, AsyncMock
from httpx import AsyncClient
from fastapi.testclient import TestClient
import os

# Set testing environment variables
os.environ["TESTING"] = "true"
os.environ["MOCK_MCP_SERVER"] = "true"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["ENABLE_AUTH"] = "false"


@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    # Import here to avoid circular imports
    from src.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    from src.main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = MagicMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.expire = AsyncMock(return_value=True)
    redis_mock.incr = AsyncMock(return_value=1)
    redis_mock.ttl = AsyncMock(return_value=60)
    return redis_mock


@pytest.fixture
def mock_mcp_client():
    """Mock MCP client."""
    mcp_mock = MagicMock()
    mcp_mock.call_tool = AsyncMock(return_value={
        "weather": {
            "temperature": 72,
            "conditions": "Sunny",
            "humidity": 45,
            "wind_speed": 10,
            "wind_direction": "NW"
        }
    })
    return mcp_mock


@pytest.fixture
def auth_headers():
    """Get authorization headers for testing."""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def sample_weather_query():
    """Sample weather query request."""
    return {
        "query": "What's the weather like in New York?",
        "session_id": "550e8400-e29b-41d4-a716-446655440000"
    }


@pytest.fixture
def sample_location():
    """Sample location data."""
    return {
        "display_name": "New York, NY",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "city": "New York",
        "country": "US"
    }


@pytest.fixture
def sample_weather_alert():
    """Sample weather alert."""
    return {
        "id": "NWS-2024-001",
        "severity": "Severe",
        "headline": "Severe Thunderstorm Warning",
        "description": "Severe thunderstorms expected",
        "effective_from": "2024-01-01T12:00:00Z",
        "expires_at": "2024-01-01T18:00:00Z"
    }