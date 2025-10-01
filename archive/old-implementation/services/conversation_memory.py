"""Conversation memory management for weather agent."""

import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ..models.conversation_turn import ConversationTurn
from ..models.weather_query import Location

logger = logging.getLogger(__name__)


class ConversationMemoryManager:
    """Manages conversation memory and context for weather agent sessions."""

    def __init__(self, session_id: str, max_turns: int = 20):
        """Initialize conversation memory manager.

        Args:
            session_id: Session identifier
            max_turns: Maximum number of turns to keep in memory
        """
        self.session_id = session_id
        self.max_turns = max_turns
        self._conversation_history: List[ConversationTurn] = []
        self._location_cache: Dict[str, Location] = {}
        self._temporal_context: Optional[str] = None

    def add_turn(self, turn: ConversationTurn) -> None:
        """Add a conversation turn to history.

        Args:
            turn: Conversation turn to add
        """
        self._conversation_history.append(turn)

        # Extract and cache location if present
        if turn.location_context:
            self._location_cache[turn.location_context.display_name] = turn.location_context

        # Maintain max turns limit
        if len(self._conversation_history) > self.max_turns:
            self._conversation_history = self._conversation_history[-self.max_turns:]

        logger.debug(f"Added turn to conversation history for session {self.session_id}")

    def get_conversation_history(self, limit: Optional[int] = None) -> List[ConversationTurn]:
        """Get conversation history.

        Args:
            limit: Optional limit on number of turns to return

        Returns:
            List of conversation turns
        """
        if limit:
            return self._conversation_history[-limit:]
        return self._conversation_history.copy()

    def get_last_turn(self) -> Optional[ConversationTurn]:
        """Get the last conversation turn.

        Returns:
            Last conversation turn or None if history is empty
        """
        return self._conversation_history[-1] if self._conversation_history else None

    def get_current_location(self) -> Optional[Location]:
        """Get the current location context from conversation.

        Returns:
            Most recent location mentioned or None
        """
        # Check recent turns for location
        for turn in reversed(self._conversation_history[-5:]):
            if turn.location_context:
                return turn.location_context

        # Check location cache
        if self._location_cache:
            # Return most recently used location
            return list(self._location_cache.values())[-1]

        return None

    def extract_locations_from_history(self) -> List[Location]:
        """Extract all unique locations from conversation history.

        Returns:
            List of unique locations mentioned
        """
        locations = {}
        for turn in self._conversation_history:
            if turn.location_context:
                key = turn.location_context.display_name
                locations[key] = turn.location_context

        return list(locations.values())

    def get_temporal_context(self) -> Optional[str]:
        """Get current temporal context (today, tomorrow, next week, etc.).

        Returns:
            Temporal context string or None
        """
        # Check recent queries for temporal indicators
        for turn in reversed(self._conversation_history[-3:]):
            temporal = self._extract_temporal_from_query(turn.user_query)
            if temporal:
                return temporal

        return self._temporal_context

    def _extract_temporal_from_query(self, query: str) -> Optional[str]:
        """Extract temporal context from query.

        Args:
            query: User query string

        Returns:
            Temporal context or None
        """
        query_lower = query.lower()

        temporal_patterns = {
            "today": ["today", "right now", "current", "currently"],
            "tomorrow": ["tomorrow"],
            "week": ["this week", "next week", "weekly", "7 day", "seven day"],
            "weekend": ["weekend", "saturday", "sunday"],
            "next_few_days": ["next few days", "coming days", "next 3 days", "next 5 days"]
        }

        for temporal_type, patterns in temporal_patterns.items():
            for pattern in patterns:
                if pattern in query_lower:
                    return temporal_type

        return None

    def update_temporal_context(self, temporal: str) -> None:
        """Update temporal context.

        Args:
            temporal: Temporal context string
        """
        self._temporal_context = temporal

    def get_context_summary(self) -> Dict[str, Any]:
        """Get a summary of the current conversation context.

        Returns:
            Dictionary with context information
        """
        return {
            "session_id": self.session_id,
            "turn_count": len(self._conversation_history),
            "current_location": self.get_current_location(),
            "temporal_context": self.get_temporal_context(),
            "recent_locations": list(self._location_cache.keys())[-3:] if self._location_cache else [],
            "last_activity": self._conversation_history[-1].timestamp if self._conversation_history else None
        }

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._conversation_history.clear()
        self._location_cache.clear()
        self._temporal_context = None
        logger.info(f"Cleared conversation history for session {self.session_id}")

    def serialize(self) -> str:
        """Serialize conversation memory to JSON.

        Returns:
            JSON string of conversation memory
        """
        data = {
            "session_id": self.session_id,
            "max_turns": self.max_turns,
            "conversation_history": [
                {
                    "user_query": turn.user_query,
                    "assistant_response": turn.assistant_response,
                    "timestamp": turn.timestamp.isoformat(),
                    "location": turn.location_context.dict() if turn.location_context else None
                }
                for turn in self._conversation_history
            ],
            "temporal_context": self._temporal_context
        }
        return json.dumps(data, default=str)

    @classmethod
    def deserialize(cls, data: str) -> "ConversationMemoryManager":
        """Deserialize conversation memory from JSON.

        Args:
            data: JSON string of conversation memory

        Returns:
            ConversationMemoryManager instance
        """
        parsed = json.loads(data)
        manager = cls(
            session_id=parsed["session_id"],
            max_turns=parsed.get("max_turns", 20)
        )

        # Restore conversation history
        for turn_data in parsed.get("conversation_history", []):
            location = None
            if turn_data.get("location"):
                location = Location(**turn_data["location"])

            turn = ConversationTurn(
                user_query=turn_data["user_query"],
                assistant_response=turn_data["assistant_response"],
                timestamp=datetime.fromisoformat(turn_data["timestamp"]),
                location_context=location
            )
            manager._conversation_history.append(turn)

        manager._temporal_context = parsed.get("temporal_context")
        return manager


class ConversationContextAnalyzer:
    """Analyzes conversation context for patterns and insights."""

    @staticmethod
    def analyze_query_intent(query: str) -> Dict[str, Any]:
        """Analyze the intent of a weather query.

        Args:
            query: User query string

        Returns:
            Dictionary with intent analysis
        """
        query_lower = query.lower()

        intent = {
            "is_current_weather": any(word in query_lower for word in ["current", "now", "today", "temperature"]),
            "is_forecast": any(word in query_lower for word in ["forecast", "tomorrow", "week", "next"]),
            "is_alert": any(word in query_lower for word in ["alert", "warning", "severe", "storm"]),
            "needs_location": "where" not in query_lower and not any(word in query_lower for word in ["in ", "at ", "for "]),
            "has_comparison": any(word in query_lower for word in ["compare", "versus", "vs", "difference"]),
            "is_follow_up": any(word in query_lower for word in ["how about", "what about", "and"])
        }

        return intent

    @staticmethod
    def should_retain_context(current_query: str, last_query: str) -> bool:
        """Determine if context should be retained between queries.

        Args:
            current_query: Current user query
            last_query: Previous user query

        Returns:
            True if context should be retained
        """
        # Check for explicit context indicators
        context_indicators = [
            "how about", "what about", "and", "also",
            "there", "same", "that location", "that place"
        ]

        current_lower = current_query.lower()
        for indicator in context_indicators:
            if indicator in current_lower:
                return True

        # Check if new location is mentioned
        if ConversationContextAnalyzer._has_new_location(current_query, last_query):
            return False

        return True

    @staticmethod
    def _has_new_location(current_query: str, last_query: str) -> bool:
        """Check if current query mentions a new location.

        Args:
            current_query: Current user query
            last_query: Previous user query

        Returns:
            True if new location is mentioned
        """
        # Simple heuristic - check for different city names
        # In production, would use NER or more sophisticated location extraction
        location_patterns = ["in ", "at ", "for ", "weather in", "weather at"]

        current_location = None
        last_location = None

        for pattern in location_patterns:
            if pattern in current_query.lower():
                current_location = current_query.lower().split(pattern)[-1].split()[0]
            if pattern in last_query.lower():
                last_location = last_query.lower().split(pattern)[-1].split()[0]

        return current_location and last_location and current_location != last_location