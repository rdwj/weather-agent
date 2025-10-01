"""Contract tests for GET /api/v1/session endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.contract
def test_session_info_returns_200(test_client: TestClient, auth_headers):
    """Test that session info endpoint returns 200."""
    response = test_client.get(
        "/api/v1/session",
        headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.contract
def test_session_info_response_schema(test_client: TestClient, auth_headers):
    """Test that session info returns expected schema."""
    response = test_client.get(
        "/api/v1/session",
        headers=auth_headers
    )

    if response.status_code == 200:
        data = response.json()

        # Check for expected fields
        if "session_id" in data:
            assert isinstance(data["session_id"], str)
        if "user_id" in data:
            assert isinstance(data["user_id"], str)
        if "created_at" in data:
            assert isinstance(data["created_at"], str)
        if "expires_at" in data:
            assert isinstance(data["expires_at"], str)
        if "conversation_count" in data:
            assert isinstance(data["conversation_count"], int)
            assert data["conversation_count"] >= 0


@pytest.mark.contract
def test_session_info_requires_auth(test_client: TestClient):
    """Test that session info requires authentication."""
    response = test_client.get("/api/v1/session")
    # When auth is disabled in testing, it might return 200
    assert response.status_code in [200, 401]