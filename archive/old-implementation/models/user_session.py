"""UserSession model."""

from uuid import UUID, uuid4
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator
import secrets

from .weather_query import Location
from .conversation_turn import ConversationTurn


class SessionStatus(str, Enum):
    """Session status enumeration."""
    ACTIVE = "active"
    EXPIRED = "expired"


class UserPreferences(BaseModel):
    """User preferences for the session."""
    temperature_unit: str = "Fahrenheit"
    default_location: Optional[Location] = None
    language: str = "en"
    time_format: str = "12h"  # 12h or 24h


class UserSession(BaseModel):
    """Authenticated user context with conversation history."""
    id: UUID = Field(default_factory=uuid4)
    user_id: str
    session_token: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    monitored_locations: List[Location] = Field(default_factory=list, max_length=3)
    conversation_history: List[ConversationTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=30))
    status: SessionStatus = SessionStatus.ACTIVE

    @field_validator("monitored_locations")
    @classmethod
    def validate_monitored_locations(cls, v):
        """Validate monitored locations list."""
        if len(v) > 3:
            raise ValueError("Maximum 3 monitored locations allowed")
        return v

    @field_validator("session_token")
    @classmethod
    def validate_session_token(cls, v):
        """Ensure session token is secure."""
        if len(v) < 32:
            raise ValueError("Session token must be at least 32 characters")
        return v

    def update_activity(self) -> None:
        """Update last activity and extend expiration."""
        self.last_activity = datetime.utcnow()
        self.expires_at = self.last_activity + timedelta(minutes=30)

    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.utcnow() > self.expires_at

    def add_conversation_turn(self, turn: ConversationTurn) -> None:
        """Add a conversation turn to history."""
        self.conversation_history.append(turn)
        self.update_activity()
        # Keep only last 20 turns to manage memory
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]


class SessionInfo(BaseModel):
    """Session information response model."""
    session_id: UUID
    user_id: str
    created_at: datetime
    expires_at: datetime
    conversation_count: int


class MonitoredLocations(BaseModel):
    """Monitored locations response model."""
    locations: List[Location] = Field(..., max_length=3)


class UpdateLocationsRequest(BaseModel):
    """Request model for updating monitored locations."""
    locations: List[Location] = Field(..., max_length=3)

    @field_validator("locations")
    @classmethod
    def validate_locations_count(cls, v):
        """Validate location count."""
        if len(v) > 3:
            raise ValueError("Maximum 3 locations allowed")
        return v