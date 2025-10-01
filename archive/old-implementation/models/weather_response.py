"""WeatherResponse model."""

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator

from .weather_alert import WeatherAlert


class TemperatureUnit(str, Enum):
    """Temperature unit enumeration."""
    CELSIUS = "Celsius"
    FAHRENHEIT = "Fahrenheit"


class CurrentWeather(BaseModel):
    """Current weather conditions."""
    temperature: float
    temperature_unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT
    conditions: str
    humidity: Optional[float] = Field(None, ge=0, le=100)
    wind_speed: Optional[float] = Field(None, ge=0)
    wind_direction: Optional[str] = None
    feels_like: Optional[float] = None
    pressure: Optional[float] = None
    visibility: Optional[float] = None
    uv_index: Optional[int] = Field(None, ge=0)


class ForecastDay(BaseModel):
    """Daily forecast information."""
    date: datetime
    high_temp: float
    low_temp: float
    conditions: str
    precipitation_chance: float = Field(..., ge=0, le=100)
    humidity: Optional[float] = Field(None, ge=0, le=100)
    wind_speed: Optional[float] = Field(None, ge=0)
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None


class WeatherResponse(BaseModel):
    """Structured weather information returned to user."""
    id: UUID = Field(default_factory=uuid4)
    query_id: UUID
    weather_data: dict  # Flexible structure for various weather data
    temperature_unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT
    data_source: str  # MCP server identifier
    freshness_timestamp: datetime
    cache_hit: bool = False
    alerts: List[WeatherAlert] = Field(default_factory=list)

    @field_validator("freshness_timestamp")
    @classmethod
    def validate_freshness(cls, v, info):
        """Validate data freshness."""
        if not info.data.get("cache_hit", False):
            # If not from cache, data should be fresh (within 15 minutes)
            age = datetime.utcnow() - v
            if age.total_seconds() > 900:  # 15 minutes
                raise ValueError("Weather data is stale (>15 minutes old) but not marked as cached")
        return v

    @field_validator("weather_data")
    @classmethod
    def validate_weather_data_structure(cls, v):
        """Ensure weather_data has expected structure."""
        # Basic validation - can be extended based on requirements
        if not isinstance(v, dict):
            raise ValueError("weather_data must be a dictionary")
        return v


class WeatherAlertsResponse(BaseModel):
    """Response model for weather alerts endpoint."""
    alerts: List[WeatherAlert]
    locations: List[dict]  # Simplified location info