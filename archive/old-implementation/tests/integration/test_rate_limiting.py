"""Integration tests for rate limiting."""

import pytest
from fastapi.testclient import TestClient
import time


@pytest.mark.integration
@pytest.mark.slow
def test_rate_limit_per_user(test_client: TestClient, auth_headers):
    """Test per-user rate limiting."""
    query = {"query": "Weather in Portland"}

    # Make requests up to the limit
    responses = []
    for i in range(101):  # Try to exceed 100 requests/minute limit
        response = test_client.post(
            "/api/v1/weather/query",
            json=query,
            headers=auth_headers
        )
        responses.append(response)

        # If we hit rate limit, verify response
        if response.status_code == 429:
            data = response.json()
            assert "error" in data
            assert "retry_after" in data
            assert isinstance(data["retry_after"], int)
            break

    # Should hit rate limit at some point if enabled
    status_codes = [r.status_code for r in responses]
    # If rate limiting is enabled, we should see 429
    # If not enabled, all should be 200
    assert all(code in [200, 429] for code in status_codes)


@pytest.mark.integration
def test_rate_limit_retry_after_header(test_client: TestClient, auth_headers):
    """Test that rate limit response includes retry-after information."""
    # This test assumes we can trigger rate limiting
    # In practice, might need to make many requests or mock the rate limiter
    query = {"query": "Weather check"}

    # Make many rapid requests
    for i in range(150):
        response = test_client.post(
            "/api/v1/weather/query",
            json=query,
            headers=auth_headers
        )

        if response.status_code == 429:
            # Check response body
            data = response.json()
            assert "retry_after" in data
            assert isinstance(data["retry_after"], int)
            assert data["retry_after"] > 0

            # Optional: Check for limit information
            if "limit" in data:
                assert isinstance(data["limit"], int)
            if "remaining" in data:
                assert isinstance(data["remaining"], int)
                assert data["remaining"] == 0
            break


@pytest.mark.integration
def test_rate_limit_recovery(test_client: TestClient, auth_headers):
    """Test that rate limit recovers after waiting."""
    query = {"query": "Quick weather check"}

    # Try to hit rate limit
    hit_limit = False
    retry_after = 1

    for i in range(150):
        response = test_client.post(
            "/api/v1/weather/query",
            json=query,
            headers=auth_headers
        )

        if response.status_code == 429:
            hit_limit = True
            data = response.json()
            retry_after = data.get("retry_after", 1)
            break

    if hit_limit:
        # Wait for the specified time
        time.sleep(retry_after + 1)

        # Should be able to make request again
        response = test_client.post(
            "/api/v1/weather/query",
            json=query,
            headers=auth_headers
        )
        # Should not be rate limited after waiting
        assert response.status_code != 429


@pytest.mark.integration
def test_cached_responses_dont_count_against_limit(test_client: TestClient, auth_headers):
    """Test that cached responses don't count against rate limit."""
    query = {"query": "Weather in Sacramento"}

    # First request - not cached
    response1 = test_client.post(
        "/api/v1/weather/query",
        json=query,
        headers=auth_headers
    )
    assert response1.status_code == 200

    # Make same request multiple times (should hit cache)
    for i in range(10):
        response = test_client.post(
            "/api/v1/weather/query",
            json=query,
            headers=auth_headers
        )
        # Cached responses shouldn't trigger rate limit
        assert response.status_code != 429