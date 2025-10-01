"""WeatherAlert model."""

from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator

from .weather_query import Location


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    MODERATE = "Moderate"
    SEVERE = "Severe"
    EXTREME = "Extreme"


class AlertStatus(str, Enum):
    """Alert status."""
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"


class WeatherAlert(BaseModel):
    """Severe weather notification."""
    id: UUID = Field(default_factory=uuid4)
    external_id: str  # From weather provider
    severity: AlertSeverity
    headline: str
    description: str
    affected_area: Location
    effective_from: datetime
    expires_at: datetime
    source: str  # Weather service name
    status: AlertStatus = AlertStatus.PENDING

    @field_validator("expires_at")
    @classmethod
    def validate_expiration(cls, v, info):
        """Validate expiration is after effective date."""
        if "effective_from" in info.data:
            if v <= info.data["effective_from"]:
                raise ValueError("expires_at must be after effective_from")
        return v

    @field_validator("severity")
    @classmethod
    def validate_notification_severity(cls, v):
        """Only severe and extreme trigger notifications."""
        # This is informational - actual filtering happens in service layer
        return v

    def update_status(self) -> None:
        """Update alert status based on current time."""
        now = datetime.utcnow()
        if now < self.effective_from:
            self.status = AlertStatus.PENDING
        elif now >= self.expires_at:
            self.status = AlertStatus.EXPIRED
        else:
            self.status = AlertStatus.ACTIVE

    def is_active(self) -> bool:
        """Check if alert is currently active."""
        self.update_status()
        return self.status == AlertStatus.ACTIVE

    def should_notify(self) -> bool:
        """Check if alert should trigger notification."""
        return self.severity in [AlertSeverity.SEVERE, AlertSeverity.EXTREME] and self.is_active()