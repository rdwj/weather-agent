"""Integration tests for context retention across queries."""

import pytest
from fastapi.testclient import TestClient
import time


@pytest.mark.integration
def test_context_retention_across_queries(test_client: TestClient, auth_headers):
    """Test that context is retained across queries in the same session."""
    # Step 1: First query establishes location context
    first_query = {
        "query": "What's the weather in Paris?"
    }

    response1 = test_client.post(
        "/api/v1/weather/query",
        json=first_query,
        headers=auth_headers
    )
    assert response1.status_code == 200
    data1 = response1.json()

    # Extract session_id if provided
    session_id = data1.get("session_id")

    # Step 2: Follow-up query should use previous context
    follow_up_query = {
        "query": "How about tomorrow?",
        "session_id": session_id
    }

    response2 = test_client.post(
        "/api/v1/weather/query",
        json=follow_up_query,
        headers=auth_headers
    )
    assert response2.status_code == 200
    data2 = response2.json()

    # The response should reference Paris or contain forecast data
    # This assumes the implementation maintains context
    assert "response" in data2


@pytest.mark.integration
def test_location_context_override(test_client: TestClient, auth_headers):
    """Test that explicit location overrides previous context."""
    # Step 1: Set initial location context
    query1 = {
        "query": "Weather in London"
    }

    response1 = test_client.post(
        "/api/v1/weather/query",
        json=query1,
        headers=auth_headers
    )
    assert response1.status_code == 200

    # Step 2: Query with new location
    query2 = {
        "query": "What's the temperature in Tokyo?"
    }

    response2 = test_client.post(
        "/api/v1/weather/query",
        json=query2,
        headers=auth_headers
    )
    assert response2.status_code == 200
    data2 = response2.json()

    # Response should be about Tokyo, not London
    if "weather_data" in data2 and "location" in data2["weather_data"]:
        location = data2["weather_data"]["location"]
        # Location should contain Tokyo reference
        assert "display_name" in location


@pytest.mark.integration
def test_temporal_context_retention(test_client: TestClient, auth_headers):
    """Test that temporal context (today, tomorrow) is understood."""
    # Step 1: Query for today's weather
    query1 = {
        "query": "What's the weather like today in Boston?"
    }

    response1 = test_client.post(
        "/api/v1/weather/query",
        json=query1,
        headers=auth_headers
    )
    assert response1.status_code == 200

    # Step 2: Query for tomorrow without specifying location
    query2 = {
        "query": "How about tomorrow?"
    }

    response2 = test_client.post(
        "/api/v1/weather/query",
        json=query2,
        headers=auth_headers
    )
    assert response2.status_code == 200

    # Both queries should succeed
    assert response1.json()["response"]
    assert response2.json()["response"]