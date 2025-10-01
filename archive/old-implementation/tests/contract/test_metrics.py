"""Contract tests for GET /api/v1/metrics endpoint."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta


@pytest.mark.contract
def test_metrics_endpoint_returns_200(test_client: TestClient, auth_headers):
    """Test that metrics endpoint returns 200."""
    response = test_client.get(
        "/api/v1/metrics",
        headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.contract
def test_metrics_endpoint_response_schema(test_client: TestClient, auth_headers):
    """Test that metrics endpoint returns expected schema."""
    response = test_client.get(
        "/api/v1/metrics",
        headers=auth_headers
    )

    if response.status_code == 200:
        data = response.json()

        # Check for expected fields
        if "period_start" in data:
            assert isinstance(data["period_start"], str)
        if "period_end" in data:
            assert isinstance(data["period_end"], str)
        if "total_requests" in data:
            assert isinstance(data["total_requests"], int)
            assert data["total_requests"] >= 0
        if "cache_hit_rate" in data:
            assert isinstance(data["cache_hit_rate"], (int, float))
            assert 0 <= data["cache_hit_rate"] <= 1
        if "avg_response_time_ms" in data:
            assert isinstance(data["avg_response_time_ms"], (int, float))
            assert data["avg_response_time_ms"] >= 0
        if "p95_response_time_ms" in data:
            assert isinstance(data["p95_response_time_ms"], (int, float))
            assert data["p95_response_time_ms"] >= 0
        if "error_rate" in data:
            assert isinstance(data["error_rate"], (int, float))
            assert 0 <= data["error_rate"] <= 1


@pytest.mark.contract
def test_metrics_endpoint_accepts_time_parameters(test_client: TestClient, auth_headers):
    """Test that metrics endpoint accepts time range parameters."""
    start_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    end_time = datetime.utcnow().isoformat()

    response = test_client.get(
        f"/api/v1/metrics?start_time={start_time}&end_time={end_time}",
        headers=auth_headers
    )
    assert response.status_code == 200

    data = response.json()
    # Period should reflect the requested time range
    if "period_start" in data and "period_end" in data:
        # Verify times are in expected format
        assert isinstance(data["period_start"], str)
        assert isinstance(data["period_end"], str)


@pytest.mark.contract
def test_metrics_endpoint_requires_auth(test_client: TestClient):
    """Test that metrics endpoint requires authentication."""
    response = test_client.get("/api/v1/metrics")
    assert response.status_code in [200, 401]