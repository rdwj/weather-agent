"""ConversationTurn model."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from .weather_query import Location


class ConversationTurn(BaseModel):
    """Single exchange in conversation history."""
    user_query: str
    assistant_response: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    location_context: Optional[Location] = None

    @property
    def summary(self) -> str:
        """Get a brief summary of the turn."""
        query_preview = self.user_query[:50] + "..." if len(self.user_query) > 50 else self.user_query
        return f"[{self.timestamp.strftime('%H:%M')}] Q: {query_preview}"