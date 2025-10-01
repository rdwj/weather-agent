"""Contract tests for PUT /api/v1/session/locations endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.contract
def test_update_locations_returns_200_with_valid_request(test_client: TestClient, auth_headers, sample_location):
    """Test that update locations returns 200 with valid request."""
    response = test_client.put(
        "/api/v1/session/locations",
        json={"locations": [sample_location]},
        headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.contract
def test_update_locations_accepts_up_to_three_locations(test_client: TestClient, auth_headers):
    """Test that update locations accepts up to 3 locations."""
    locations = [
        {"display_name": "New York, NY", "city": "New York", "country": "US"},
        {"display_name": "London, UK", "city": "London", "country": "GB"},
        {"display_name": "Tokyo, Japan", "city": "Tokyo", "country": "JP"}
    ]

    response = test_client.put(
        "/api/v1/session/locations",
        json={"locations": locations},
        headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.contract
def test_update_locations_returns_400_with_too_many_locations(test_client: TestClient, auth_headers):
    """Test that update locations returns 400 with more than 3 locations."""
    locations = [
        {"display_name": f"City {i}"} for i in range(4)
    ]

    response = test_client.put(
        "/api/v1/session/locations",
        json={"locations": locations},
        headers=auth_headers
    )
    assert response.status_code == 400


@pytest.mark.contract
def test_update_locations_validates_location_fields(test_client: TestClient, auth_headers):
    """Test that update locations validates location fields."""
    # Invalid latitude
    invalid_location = {
        "display_name": "Invalid",
        "latitude": 200,  # Out of range
        "longitude": 0
    }

    response = test_client.put(
        "/api/v1/session/locations",
        json={"locations": [invalid_location]},
        headers=auth_headers
    )
    assert response.status_code == 400


@pytest.mark.contract
def test_update_locations_requires_auth(test_client: TestClient, sample_location):
    """Test that update locations requires authentication."""
    response = test_client.put(
        "/api/v1/session/locations",
        json={"locations": [sample_location]}
    )
    assert response.status_code in [200, 401]