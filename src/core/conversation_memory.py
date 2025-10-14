#!/usr/bin/env python3
"""
Conversation memory implementation using LangGraph for multi-turn conversations.

This module provides conversation state persistence and memory management
using LangGraph's checkpointing capabilities.
"""

import logging
import uuid
from datetime import datetime
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages

logger = logging.getLogger(__name__)


class ConversationState(TypedDict):
    """State schema for conversation memory."""

    # Core conversation data
    messages: Annotated[list[dict[str, str]], add_messages]
    thread_id: str
    user_id: str | None

    # Weather context
    current_location: str | None
    previous_locations: list[str]
    last_weather_data: dict[str, Any] | None

    # Query processing
    current_query: str
    processed_response: str | None

    # Metadata
    conversation_turn: int
    last_updated: str

    # Analysis context
    intent: dict[str, Any] | None
    needs_formatting: bool


def create_initial_state(
    query: str,
    thread_id: str | None = None,
    user_id: str | None = None
) -> ConversationState:
    """
    Create initial conversation state.

    Args:
        query: User's query
        thread_id: Optional thread identifier
        user_id: Optional user identifier

    Returns:
        Initial conversation state
    """
    return ConversationState(
        messages=[],
        thread_id=thread_id or str(uuid.uuid4()),
        user_id=user_id,
        current_location=None,
        previous_locations=[],
        last_weather_data=None,
        current_query=query,
        processed_response=None,
        conversation_turn=1,
        last_updated=datetime.utcnow().isoformat(),
        intent=None,
        needs_formatting=True
    )


class ConversationMemoryManager:
    """Manages conversation memory and state using simple in-memory storage."""

    def __init__(self, use_redis: bool = False, redis_url: str | None = None):
        """
        Initialize conversation memory manager.

        Args:
            use_redis: Whether to use Redis for persistence
            redis_url: Redis connection URL (if use_redis=True)
        """
        self.use_redis = use_redis
        self.redis_url = redis_url

        # Use simple dict storage for now (LangGraph checkpointer API is complex)
        # In production, this would be replaced with Redis
        self._conversations: dict[str, dict[str, Any]] = {}

        logger.info(f"Initialized conversation memory with {'Redis (planned)' if use_redis else 'in-memory'} storage")

    def get_conversation_history(
        self,
        thread_id: str,
        max_turns: int = 10
    ) -> list[dict[str, str]]:
        """
        Get conversation history for a thread.

        Args:
            thread_id: Thread identifier
            max_turns: Maximum number of turns to retrieve

        Returns:
            List of conversation messages
        """
        if thread_id in self._conversations:
            messages = self._conversations[thread_id].get("messages", [])
            return messages[-max_turns*2:] if messages else []
        return []

    def get_last_location(self, thread_id: str) -> str | None:
        """
        Get the last discussed location from conversation history.

        Args:
            thread_id: Thread identifier

        Returns:
            Last location or None
        """
        if thread_id in self._conversations:
            location = self._conversations[thread_id].get("current_location")
            logger.info(f"📍 Retrieved location for thread {thread_id[:20]}: {location}")
            return location
        logger.warning(f"⚠️ Thread {thread_id[:20]} not found in conversations")
        return None

    def get_last_weather_data(self, thread_id: str) -> dict[str, Any] | None:
        """
        Get the last weather data from conversation history.

        Args:
            thread_id: Thread identifier

        Returns:
            Last weather data or None
        """
        if thread_id in self._conversations:
            return self._conversations[thread_id].get("last_weather_data")
        return None

    def update_conversation_state(
        self,
        thread_id: str,
        user_message: str,
        assistant_response: str,
        location: str | None = None,
        weather_data: dict[str, Any] | None = None,
        intent: dict[str, Any] | None = None
    ) -> bool:
        """
        Update conversation state with new turn.

        Args:
            thread_id: Thread identifier
            user_message: User's message
            assistant_response: Assistant's response
            location: Location discussed (if any)
            weather_data: Weather data fetched (if any)
            intent: Query intent analysis (if any)

        Returns:
            True if update successful
        """
        try:
            if thread_id in self._conversations:
                # Update existing conversation
                current_state = self._conversations[thread_id]

                # Add messages
                messages = current_state.get("messages", [])
                messages.extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_response}
                ])

                # Update locations
                previous_locations = current_state.get("previous_locations", [])
                if location:
                    if location not in previous_locations:
                        previous_locations.append(location)
                        # Keep only last 5 locations
                        previous_locations = previous_locations[-5:]

                # Update state
                self._conversations[thread_id] = {
                    "messages": messages,
                    "thread_id": thread_id,
                    "current_location": location or current_state.get("current_location"),
                    "previous_locations": previous_locations,
                    "last_weather_data": weather_data or current_state.get("last_weather_data"),
                    "conversation_turn": current_state.get("conversation_turn", 0) + 1,
                    "last_updated": datetime.utcnow().isoformat(),
                    "intent": intent
                }

            else:
                # Create new conversation
                self._conversations[thread_id] = {
                    "messages": [
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": assistant_response}
                    ],
                    "thread_id": thread_id,
                    "current_location": location,
                    "previous_locations": [location] if location else [],
                    "last_weather_data": weather_data,
                    "conversation_turn": 1,
                    "last_updated": datetime.utcnow().isoformat(),
                    "intent": intent
                }

            return True

        except Exception as e:
            logger.error(f"Error updating conversation state: {e}")
            return False

    def clear_thread(self, thread_id: str) -> bool:
        """
        Clear conversation history for a thread.

        Args:
            thread_id: Thread identifier

        Returns:
            True if cleared successfully
        """
        try:
            if thread_id in self._conversations:
                del self._conversations[thread_id]
            logger.info(f"Cleared conversation thread: {thread_id}")
            return True

        except Exception as e:
            logger.error(f"Error clearing thread: {e}")
            return False

    def get_thread_summary(self, thread_id: str) -> dict[str, Any]:
        """
        Get summary of conversation thread.

        Args:
            thread_id: Thread identifier

        Returns:
            Thread summary with key metadata
        """
        if thread_id in self._conversations:
            values = self._conversations[thread_id]
            messages = values.get("messages", [])

            return {
                "thread_id": thread_id,
                "message_count": len(messages),
                "conversation_turns": values.get("conversation_turn", 0),
                "current_location": values.get("current_location"),
                "previous_locations": values.get("previous_locations", []),
                "last_updated": values.get("last_updated"),
                "has_weather_data": values.get("last_weather_data") is not None,
                "exists": True
            }

        return {
            "thread_id": thread_id,
            "exists": False
        }


# Singleton instance
_memory_manager: ConversationMemoryManager | None = None


def get_memory_manager(
    use_redis: bool = False,
    redis_url: str | None = None
) -> ConversationMemoryManager:
    """
    Get or create the conversation memory manager singleton.

    Args:
        use_redis: Whether to use Redis for persistence
        redis_url: Redis connection URL

    Returns:
        ConversationMemoryManager instance
    """
    global _memory_manager

    if _memory_manager is None:
        _memory_manager = ConversationMemoryManager(
            use_redis=use_redis,
            redis_url=redis_url
        )

    return _memory_manager
