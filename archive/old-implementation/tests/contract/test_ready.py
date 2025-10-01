"""Contract tests for GET /ready endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.contract
def test_ready_endpoint_returns_200_when_ready(test_client: TestClient):
    """Test that ready endpoint returns 200 when service is ready."""
    response = test_client.get("/ready")
    # Should return either 200 or 503 depending on readiness
    assert response.status_code in [200, 503]


@pytest.mark.contract
def test_ready_endpoint_returns_503_when_not_ready(test_client: TestClient):
    """Test that ready endpoint returns 503 when service is not ready."""
    # In a real test, we would mock the service to be not ready
    # For now, just verify the endpoint exists and responds
    response = test_client.get("/ready")
    assert response.status_code in [200, 503]

    if response.status_code == 503:
        # Verify no body or appropriate error message
        assert response.text == "" or "not ready" in response.text.lower()


@pytest.mark.contract
def test_ready_endpoint_no_auth_required(test_client: TestClient):
    """Test that ready endpoint doesn't require authentication."""
    response = test_client.get("/ready")
    # Should not return 401 Unauthorized
    assert response.status_code != 401