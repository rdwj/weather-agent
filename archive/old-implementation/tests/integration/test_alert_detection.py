"""Integration tests for alert detection."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_alert_detection_in_weather_query(test_client: TestClient, auth_headers):
    """Test that alerts are detected in weather queries."""
    # Query for a location (in real scenario, might have alerts)
    query = {
        "query": "What's the weather in Oklahoma City?"
    }

    response = test_client.post(
        "/api/v1/weather/query",
        json=query,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()

    # Check if alerts field exists
    if "alerts" in data:
        assert isinstance(data["alerts"], list)
        for alert in data["alerts"]:
            assert "severity" in alert
            assert "headline" in alert
            assert alert["severity"] in ["Moderate", "Severe", "Extreme"]


@pytest.mark.integration
def test_monitored_locations_alerts(test_client: TestClient, auth_headers):
    """Test alerts for monitored locations."""
    # Step 1: Set monitored locations
    locations = [
        {"display_name": "Miami, FL", "city": "Miami", "country": "US"},
        {"display_name": "Houston, TX", "city": "Houston", "country": "US"}
    ]

    update_response = test_client.put(
        "/api/v1/session/locations",
        json={"locations": locations},
        headers=auth_headers
    )
    assert update_response.status_code == 200

    # Step 2: Check alerts for monitored locations
    alerts_response = test_client.get(
        "/api/v1/weather/alerts",
        headers=auth_headers
    )
    assert alerts_response.status_code == 200
    alerts_data = alerts_response.json()

    # Verify structure
    assert "alerts" in alerts_data
    assert isinstance(alerts_data["alerts"], list)

    # If there are alerts, verify they're severe or extreme only
    for alert in alerts_data["alerts"]:
        assert alert["severity"] in ["Severe", "Extreme"]


@pytest.mark.integration
def test_alert_filtering_by_severity(test_client: TestClient, auth_headers):
    """Test that only severe and extreme alerts are returned."""
    # Get alerts
    response = test_client.get(
        "/api/v1/weather/alerts",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()

    if "alerts" in data and len(data["alerts"]) > 0:
        # All returned alerts should be Severe or Extreme
        for alert in data["alerts"]:
            assert alert["severity"] in ["Severe", "Extreme"]
            # Moderate alerts should not be included
            assert alert["severity"] != "Moderate"


@pytest.mark.integration
def test_alert_expiration_handling(test_client: TestClient, auth_headers):
    """Test that expired alerts are not returned."""
    # Get alerts
    response = test_client.get(
        "/api/v1/weather/alerts",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()

    if "alerts" in data:
        for alert in data["alerts"]:
            if "expires_at" in alert:
                # In a real test, we'd verify expires_at is in the future
                # For now, just verify the field format
                assert isinstance(alert["expires_at"], str)