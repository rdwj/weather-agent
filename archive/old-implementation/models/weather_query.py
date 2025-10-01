"""WeatherQuery model."""

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Location(BaseModel):
    """Geographic reference for weather queries."""
    id: UUID = Field(default_factory=uuid4)
    display_name: str
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    city: Optional[str] = None
    state_province: Optional[str] = None
    country: Optional[str] = Field(None, max_length=2)  # ISO 3166-1 alpha-2
    postal_code: Optional[str] = None
    timezone: Optional[str] = None

    @field_validator("latitude", "longitude")
    @classmethod
    def validate_coordinates(cls, v, info):
        """Ensure both lat and lon are provided together."""
        if info.field_name == "longitude" and v is not None:
            if info.data.get("latitude") is None:
                raise ValueError("Latitude required when longitude is provided")
        return v


class WeatherQuery(BaseModel):
    """Natural language question about weather with context."""
    id: UUID = Field(default_factory=uuid4)
    user_id: str
    session_id: str
    query_text: str = Field(..., min_length=1, max_length=500)
    location_context: Optional[Location] = None
    temporal_context: Optional[str] = None  # today, tomorrow, next week
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[int] = Field(None, ge=0)

    @field_validator("query_text")
    @classmethod
    def validate_query_text(cls, v):
        """Validate query text doesn't contain PII."""
        # Simple check - in production would use more sophisticated PII detection
        sensitive_patterns = ["ssn", "social security", "credit card", "password"]
        lower_text = v.lower()
        for pattern in sensitive_patterns:
            if pattern in lower_text:
                raise ValueError(f"Query text appears to contain sensitive information: {pattern}")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_utc(cls, v):
        """Ensure timestamp is UTC."""
        if v.tzinfo is not None and v.tzinfo.utcoffset(None) is not None:
            # Convert to UTC if timezone aware
            return v.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return v


class WeatherQueryRequest(BaseModel):
    """Request model for weather query endpoint."""
    query: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[UUID] = None


class WeatherQueryResponse(BaseModel):
    """Response model for weather query endpoint."""
    query_id: UUID
    response: str
    weather_data: Optional[dict] = None
    data_freshness: datetime
    cache_hit: bool = False
    alerts: list[dict] = Field(default_factory=list)