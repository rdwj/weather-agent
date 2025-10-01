"""Integration tests for basic weather query scenario."""

import pytest
from fastapi.testclient import TestClient
import json


@pytest.mark.integration
def test_basic_weather_query_flow(test_client: TestClient, auth_headers):
    """Test complete flow of querying weather."""
    # Step 1: Query weather for a specific location
    query_request = {
        "query": "What's the weather like in San Francisco?"
    }

    response = test_client.post(
        "/api/v1/weather/query",
        json=query_request,
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "query_id" in data
    assert "response" in data
    assert "data_freshness" in data

    # Response should contain weather information
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0

    # If weather data is included, verify structure
    if "weather_data" in data:
        weather = data["weather_data"]
        assert "location" in weather or "current" in weather


@pytest.mark.integration
def test_weather_query_with_session(test_client: TestClient, auth_headers):
    """Test weather query with session tracking."""
    # Step 1: Get initial session info
    session_response = test_client.get(
        "/api/v1/session",
        headers=auth_headers
    )
    assert session_response.status_code == 200
    initial_session = session_response.json()

    # Step 2: Make a weather query
    query_request = {
        "query": "What's the temperature in New York?",
        "session_id": initial_session.get("session_id")
    }

    response = test_client.post(
        "/api/v1/weather/query",
        json=query_request,
        headers=auth_headers
    )
    assert response.status_code == 200

    # Step 3: Check session was updated
    session_response = test_client.get(
        "/api/v1/session",
        headers=auth_headers
    )
    assert session_response.status_code == 200
    updated_session = session_response.json()

    # Conversation count should increase if tracking is enabled
    if "conversation_count" in initial_session and "conversation_count" in updated_session:
        assert updated_session["conversation_count"] >= initial_session["conversation_count"]


@pytest.mark.integration
def test_weather_query_error_handling(test_client: TestClient, auth_headers):
    """Test weather query error handling."""
    # Test with empty query
    response = test_client.post(
        "/api/v1/weather/query",
        json={"query": ""},
        headers=auth_headers
    )
    assert response.status_code == 400

    # Test with missing query field
    response = test_client.post(
        "/api/v1/weather/query",
        json={},
        headers=auth_headers
    )
    assert response.status_code in [400, 422]  # 422 for validation error

    # Test with overly long query
    long_query = "a" * 501
    response = test_client.post(
        "/api/v1/weather/query",
        json={"query": long_query},
        headers=auth_headers
    )
    assert response.status_code == 400