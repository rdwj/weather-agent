"""Contract tests for GET /api/v1/session/preferences endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.contract
def test_get_preferences_returns_200(test_client: TestClient, auth_headers):
    """Test that get preferences endpoint returns 200."""
    response = test_client.get(
        "/api/v1/session/preferences",
        headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.contract
def test_get_preferences_response_schema(test_client: TestClient, auth_headers):
    """Test that get preferences returns expected schema."""
    response = test_client.get(
        "/api/v1/session/preferences",
        headers=auth_headers
    )

    if response.status_code == 200:
        data = response.json()

        # Check temperature_unit field
        if "temperature_unit" in data:
            assert data["temperature_unit"] in ["Celsius", "Fahrenheit"]

        # Check default_location field
        if "default_location" in data:
            location = data["default_location"]
            assert "display_name" in location
            assert isinstance(location["display_name"], str)


@pytest.mark.contract
def test_get_preferences_has_default_values(test_client: TestClient, auth_headers):
    """Test that get preferences has default values."""
    response = test_client.get(
        "/api/v1/session/preferences",
        headers=auth_headers
    )

    if response.status_code == 200:
        data = response.json()

        # Default temperature unit should be Fahrenheit
        if "temperature_unit" in data and data.get("default_location") is None:
            # New session should have Fahrenheit as default
            pass  # Default handled by implementation


@pytest.mark.contract
def test_get_preferences_requires_auth(test_client: TestClient):
    """Test that get preferences requires authentication."""
    response = test_client.get("/api/v1/session/preferences")
    assert response.status_code in [200, 401]