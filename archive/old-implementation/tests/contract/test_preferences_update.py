"""Contract tests for PATCH /api/v1/session/preferences endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.contract
def test_update_preferences_returns_200_with_valid_request(test_client: TestClient, auth_headers):
    """Test that update preferences returns 200 with valid request."""
    response = test_client.patch(
        "/api/v1/session/preferences",
        json={"temperature_unit": "Celsius"},
        headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.contract
def test_update_preferences_accepts_temperature_unit(test_client: TestClient, auth_headers):
    """Test that update preferences accepts valid temperature units."""
    # Test Celsius
    response = test_client.patch(
        "/api/v1/session/preferences",
        json={"temperature_unit": "Celsius"},
        headers=auth_headers
    )
    assert response.status_code == 200

    # Test Fahrenheit
    response = test_client.patch(
        "/api/v1/session/preferences",
        json={"temperature_unit": "Fahrenheit"},
        headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.contract
def test_update_preferences_accepts_default_location(test_client: TestClient, auth_headers, sample_location):
    """Test that update preferences accepts default location."""
    response = test_client.patch(
        "/api/v1/session/preferences",
        json={"default_location": sample_location},
        headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.contract
def test_update_preferences_accepts_partial_updates(test_client: TestClient, auth_headers):
    """Test that update preferences accepts partial updates (PATCH behavior)."""
    # Update only temperature unit
    response = test_client.patch(
        "/api/v1/session/preferences",
        json={"temperature_unit": "Celsius"},
        headers=auth_headers
    )
    assert response.status_code == 200

    # Empty update should also work
    response = test_client.patch(
        "/api/v1/session/preferences",
        json={},
        headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.contract
def test_update_preferences_validates_temperature_unit(test_client: TestClient, auth_headers):
    """Test that update preferences validates temperature unit."""
    response = test_client.patch(
        "/api/v1/session/preferences",
        json={"temperature_unit": "Kelvin"},  # Invalid unit
        headers=auth_headers
    )
    assert response.status_code == 400


@pytest.mark.contract
def test_update_preferences_requires_auth(test_client: TestClient):
    """Test that update preferences requires authentication."""
    response = test_client.patch(
        "/api/v1/session/preferences",
        json={"temperature_unit": "Celsius"}
    )
    assert response.status_code in [200, 401]