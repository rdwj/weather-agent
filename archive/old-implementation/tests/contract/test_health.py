"""Contract tests for GET /health endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.contract
def test_health_endpoint_returns_200(test_client: TestClient):
    """Test that health endpoint returns 200 status."""
    response = test_client.get("/health")
    assert response.status_code == 200


@pytest.mark.contract
def test_health_endpoint_response_schema(test_client: TestClient):
    """Test that health endpoint returns expected schema."""
    response = test_client.get("/health")
    data = response.json()

    # Required fields
    assert "status" in data
    assert "version" in data

    # Status should be healthy or degraded
    assert data["status"] in ["healthy", "degraded"]

    # Optional fields
    if "mcp_server_connected" in data:
        assert isinstance(data["mcp_server_connected"], bool)
    if "redis_connected" in data:
        assert isinstance(data["redis_connected"], bool)


@pytest.mark.contract
def test_health_endpoint_no_auth_required(test_client: TestClient):
    """Test that health endpoint doesn't require authentication."""
    # Should work without auth headers
    response = test_client.get("/health")
    assert response.status_code == 200

    # Should also work with auth headers
    response = test_client.get("/health", headers={"Authorization": "Bearer test"})
    assert response.status_code == 200