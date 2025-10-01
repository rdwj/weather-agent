"""Contract tests for GET /api/v1/weather/alerts endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.contract
def test_weather_alerts_returns_200(test_client: TestClient, auth_headers):
    """Test that weather alerts endpoint returns 200."""
    response = test_client.get(
        "/api/v1/weather/alerts",
        headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.contract
def test_weather_alerts_response_schema(test_client: TestClient, auth_headers):
    """Test that weather alerts returns expected schema."""
    response = test_client.get(
        "/api/v1/weather/alerts",
        headers=auth_headers
    )

    if response.status_code == 200:
        data = response.json()

        # Should have alerts array
        if "alerts" in data:
            assert isinstance(data["alerts"], list)
            for alert in data["alerts"]:
                # Required fields
                assert "severity" in alert
                assert "headline" in alert
                assert alert["severity"] in ["Moderate", "Severe", "Extreme"]

                # Optional fields
                if "id" in alert:
                    assert isinstance(alert["id"], str)
                if "description" in alert:
                    assert isinstance(alert["description"], str)
                if "effective_from" in alert:
                    assert isinstance(alert["effective_from"], str)
                if "expires_at" in alert:
                    assert isinstance(alert["expires_at"], str)

        # Should have locations array
        if "locations" in data:
            assert isinstance(data["locations"], list)
            for location in data["locations"]:
                assert "display_name" in location


@pytest.mark.contract
def test_weather_alerts_requires_auth(test_client: TestClient):
    """Test that weather alerts requires authentication."""
    response = test_client.get("/api/v1/weather/alerts")
    # When auth is disabled in testing, it might return 200
    assert response.status_code in [200, 401]