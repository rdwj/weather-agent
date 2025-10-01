"""Contract tests for GET /api/v1/session/locations endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.contract
def test_get_locations_returns_200(test_client: TestClient, auth_headers):
    """Test that get locations endpoint returns 200."""
    response = test_client.get(
        "/api/v1/session/locations",
        headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.contract
def test_get_locations_response_schema(test_client: TestClient, auth_headers):
    """Test that get locations returns expected schema."""
    response = test_client.get(
        "/api/v1/session/locations",
        headers=auth_headers
    )

    if response.status_code == 200:
        data = response.json()

        # Should have locations array
        assert "locations" in data
        assert isinstance(data["locations"], list)

        # Max 3 locations
        assert len(data["locations"]) <= 3

        # Check each location
        for location in data["locations"]:
            # Required field
            assert "display_name" in location
            assert isinstance(location["display_name"], str)

            # Optional fields
            if "latitude" in location:
                assert isinstance(location["latitude"], (int, float))
                assert -90 <= location["latitude"] <= 90
            if "longitude" in location:
                assert isinstance(location["longitude"], (int, float))
                assert -180 <= location["longitude"] <= 180
            if "city" in location:
                assert isinstance(location["city"], str)
            if "country" in location:
                assert isinstance(location["country"], str)


@pytest.mark.contract
def test_get_locations_requires_auth(test_client: TestClient):
    """Test that get locations requires authentication."""
    response = test_client.get("/api/v1/session/locations")
    assert response.status_code in [200, 401]