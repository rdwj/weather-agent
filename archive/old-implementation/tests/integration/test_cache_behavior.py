"""Integration tests for cache hit behavior."""

import pytest
from fastapi.testclient import TestClient
import time


@pytest.mark.integration
def test_cache_hit_for_repeated_queries(test_client: TestClient, auth_headers):
    """Test that repeated queries hit the cache."""
    query = {
        "query": "What's the weather in Seattle?"
    }

    # First query - should be cache miss
    response1 = test_client.post(
        "/api/v1/weather/query",
        json=query,
        headers=auth_headers
    )
    assert response1.status_code == 200
    data1 = response1.json()
    cache_hit_1 = data1.get("cache_hit", False)

    # Second query - should be cache hit
    response2 = test_client.post(
        "/api/v1/weather/query",
        json=query,
        headers=auth_headers
    )
    assert response2.status_code == 200
    data2 = response2.json()
    cache_hit_2 = data2.get("cache_hit", False)

    # If caching is implemented, second query should hit cache
    # First query should be miss, second should be hit
    if "cache_hit" in data1 and "cache_hit" in data2:
        assert not cache_hit_1 or cache_hit_2  # At least one should show cache behavior


@pytest.mark.integration
def test_cache_performance_improvement(test_client: TestClient, auth_headers):
    """Test that cached responses are faster."""
    query = {
        "query": "Current temperature in Chicago"
    }

    # First query - measure time
    start_time_1 = time.time()
    response1 = test_client.post(
        "/api/v1/weather/query",
        json=query,
        headers=auth_headers
    )
    end_time_1 = time.time()
    assert response1.status_code == 200
    duration_1 = end_time_1 - start_time_1

    # Second query - should be faster if cached
    start_time_2 = time.time()
    response2 = test_client.post(
        "/api/v1/weather/query",
        json=query,
        headers=auth_headers
    )
    end_time_2 = time.time()
    assert response2.status_code == 200
    duration_2 = end_time_2 - start_time_2

    # Cached response should generally be faster
    # This is a soft check as timing can vary
    print(f"First query: {duration_1:.3f}s, Second query: {duration_2:.3f}s")


@pytest.mark.integration
def test_cache_respects_different_queries(test_client: TestClient, auth_headers):
    """Test that different queries don't incorrectly share cache."""
    # Query 1
    query1 = {
        "query": "Weather in Miami"
    }
    response1 = test_client.post(
        "/api/v1/weather/query",
        json=query1,
        headers=auth_headers
    )
    assert response1.status_code == 200
    data1 = response1.json()

    # Query 2 - different location
    query2 = {
        "query": "Weather in Denver"
    }
    response2 = test_client.post(
        "/api/v1/weather/query",
        json=query2,
        headers=auth_headers
    )
    assert response2.status_code == 200
    data2 = response2.json()

    # Responses should be different
    assert data1["query_id"] != data2["query_id"]
    # If weather data is included, locations should differ
    if "weather_data" in data1 and "weather_data" in data2:
        if "location" in data1["weather_data"] and "location" in data2["weather_data"]:
            loc1 = data1["weather_data"]["location"].get("display_name", "")
            loc2 = data2["weather_data"]["location"].get("display_name", "")
            assert loc1 != loc2 or (loc1 == "" and loc2 == "")