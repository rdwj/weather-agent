"""Session storage service using Redis."""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID

from ..models.user_session import UserSession, SessionStatus, UserPreferences
from ..models.conversation_turn import ConversationTurn
from ..models.weather_query import Location
from ..lib.redis_client import (
    RedisConnectionManager,
    RedisKeyBuilder,
    RedisOperations,
    get_redis_connection
)

logger = logging.getLogger(__name__)


class SessionStorageService:
    """Service for storing and retrieving user sessions in Redis."""

    DEFAULT_SESSION_TTL = 1800  # 30 minutes

    def __init__(self, connection_manager: Optional[RedisConnectionManager] = None):
        """Initialize session storage service.

        Args:
            connection_manager: Optional Redis connection manager
        """
        self.connection_manager = connection_manager
        self.operations: Optional[RedisOperations] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the service."""
        if self._initialized:
            return

        if not self.connection_manager:
            self.connection_manager = await get_redis_connection()

        self.operations = RedisOperations(self.connection_manager)
        self._initialized = True

    async def save_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """Save a chat session to Redis.

        Args:
            session_id: Unique session identifier
            session_data: Session data dictionary

        Returns:
            True if saved successfully
        """
        if not self._initialized:
            await self.initialize()

        try:
            key = f"session:{session_id}"
            # Convert datetime objects to ISO format strings
            if 'created_at' in session_data:
                session_data['created_at'] = session_data['created_at'].isoformat() if hasattr(session_data['created_at'], 'isoformat') else session_data['created_at']
            if 'updated_at' in session_data:
                session_data['updated_at'] = session_data['updated_at'].isoformat() if hasattr(session_data['updated_at'], 'isoformat') else session_data['updated_at']

            # Convert messages timestamps
            if 'messages' in session_data:
                for msg in session_data['messages']:
                    if 'timestamp' in msg:
                        msg['timestamp'] = msg['timestamp'].isoformat() if hasattr(msg['timestamp'], 'isoformat') else msg['timestamp']

            json_data = json.dumps(session_data)
            await self.operations.set_with_ttl(key, json_data, ttl=self.DEFAULT_SESSION_TTL)
            return True
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a chat session from Redis.

        Args:
            session_id: Session identifier

        Returns:
            Session data dictionary or None
        """
        if not self._initialized:
            await self.initialize()

        try:
            key = f"session:{session_id}"
            data = await self.operations.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session from Redis.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted successfully
        """
        if not self._initialized:
            await self.initialize()

        try:
            key = f"session:{session_id}"
            result = await self.operations.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False

    async def list_user_sessions(self, user_id: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """List sessions for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip

        Returns:
            List of session data dictionaries
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Get all session keys
            pattern = "session:*"
            keys = await self.operations.keys(pattern)

            sessions = []
            for key in keys:
                data = await self.operations.get(key)
                if data:
                    session_data = json.loads(data)
                    if session_data.get('user_id') == user_id:
                        sessions.append(session_data)

            # Sort by updated_at descending
            sessions.sort(key=lambda x: x.get('updated_at', ''), reverse=True)

            # Apply pagination
            return sessions[offset:offset+limit]
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []

    async def create_session(self,
                           user_id: str,
                           preferences: Optional[Any] = None) -> Any:
        """Create a new user session.

        Args:
            user_id: User identifier
            preferences: Optional user preferences

        Returns:
            Created UserSession
        """
        await self.initialize()

        # Create session
        session = UserSession(
            user_id=user_id,
            preferences=preferences or UserPreferences()
        )

        # Store in Redis
        await self.save_session(session)

        logger.info(f"Created new session {session.id} for user {user_id}")
        return session

    async def get_user_session(self, user_id: str, session_id: str) -> Optional[UserSession]:
        """Retrieve a user session from Redis.

        Args:
            user_id: User identifier
            session_id: Session identifier

        Returns:
            UserSession or None if not found
        """
        await self.initialize()

        # Build key
        key = RedisKeyBuilder.session_key(user_id, session_id)

        # Get from Redis
        session_data = await self.operations.get_json(key)
        if not session_data:
            logger.debug(f"Session not found: {session_id}")
            return None

        try:
            # Reconstruct session
            session = self._deserialize_session(session_data)

            # Check if expired
            if session.is_expired():
                logger.info(f"Session {session_id} has expired")
                await self.delete_session(user_id, session_id)
                return None

            # Update activity
            session.update_activity()
            await self.save_session(session)

            return session

        except Exception as e:
            logger.error(f"Failed to deserialize session {session_id}: {e}")
            return None

    async def save_user_session(self, session: UserSession) -> bool:
        """Save a user session to Redis.

        Args:
            session: UserSession to save

        Returns:
            True if successful
        """
        await self.initialize()

        # Build key
        key = RedisKeyBuilder.session_key(session.user_id, str(session.id))

        # Serialize session
        session_data = self._serialize_session(session)

        # Calculate TTL
        ttl = self.DEFAULT_SESSION_TTL
        if session.expires_at:
            remaining = (session.expires_at - datetime.utcnow()).total_seconds()
            ttl = max(1, int(remaining))

        # Save to Redis
        success = await self.operations.set_json(key, session_data, ttl)

        if success:
            logger.debug(f"Saved session {session.id} with TTL {ttl}s")
        else:
            logger.error(f"Failed to save session {session.id}")

        return success

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        """Delete a user session from Redis.

        Args:
            user_id: User identifier
            session_id: Session identifier

        Returns:
            True if deleted
        """
        await self.initialize()

        key = RedisKeyBuilder.session_key(user_id, session_id)
        deleted = await self.operations.delete(key)

        if deleted:
            logger.info(f"Deleted session {session_id}")

        return bool(deleted)

    async def extend_session(self, user_id: str, session_id: str,
                           extension_minutes: int = 30) -> bool:
        """Extend session expiration.

        Args:
            user_id: User identifier
            session_id: Session identifier
            extension_minutes: Minutes to extend

        Returns:
            True if extended
        """
        await self.initialize()

        session = await self.get_session(user_id, session_id)
        if not session:
            return False

        # Extend expiration
        session.expires_at = datetime.utcnow() + timedelta(minutes=extension_minutes)
        session.update_activity()

        return await self.save_session(session)

    async def add_conversation_turn(self,
                                   user_id: str,
                                   session_id: str,
                                   turn: ConversationTurn) -> bool:
        """Add a conversation turn to session.

        Args:
            user_id: User identifier
            session_id: Session identifier
            turn: Conversation turn to add

        Returns:
            True if successful
        """
        await self.initialize()

        session = await self.get_session(user_id, session_id)
        if not session:
            return False

        session.add_conversation_turn(turn)
        return await self.save_session(session)

    async def update_preferences(self,
                                user_id: str,
                                session_id: str,
                                preferences: UserPreferences) -> bool:
        """Update user preferences in session.

        Args:
            user_id: User identifier
            session_id: Session identifier
            preferences: Updated preferences

        Returns:
            True if successful
        """
        await self.initialize()

        session = await self.get_session(user_id, session_id)
        if not session:
            return False

        session.preferences = preferences
        session.update_activity()
        return await self.save_session(session)

    async def update_monitored_locations(self,
                                        user_id: str,
                                        session_id: str,
                                        locations: List[Location]) -> bool:
        """Update monitored locations in session.

        Args:
            user_id: User identifier
            session_id: Session identifier
            locations: List of locations to monitor

        Returns:
            True if successful
        """
        await self.initialize()

        session = await self.get_session(user_id, session_id)
        if not session:
            return False

        if len(locations) > 3:
            logger.warning("Attempting to monitor more than 3 locations")
            locations = locations[:3]

        session.monitored_locations = locations
        session.update_activity()
        return await self.save_session(session)

    async def get_active_sessions(self, user_id: str) -> List[UserSession]:
        """Get all active sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            List of active sessions
        """
        await self.initialize()

        # Use Redis SCAN to find all sessions for user
        # Pattern: session:user_id:*
        pattern = f"{RedisKeyBuilder.SESSION_PREFIX}:{user_id}:*"

        sessions = []
        try:
            client = await self.connection_manager.get_client()
            cursor = 0

            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)

                for key in keys:
                    session_data = await self.operations.get_json(key)
                    if session_data:
                        try:
                            session = self._deserialize_session(session_data)
                            if not session.is_expired():
                                sessions.append(session)
                        except Exception as e:
                            logger.error(f"Failed to deserialize session from key {key}: {e}")

                if cursor == 0:
                    break

        except Exception as e:
            logger.error(f"Failed to get active sessions for user {user_id}: {e}")

        return sessions

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions from Redis.

        Returns:
            Number of sessions cleaned up
        """
        await self.initialize()

        # Redis TTL should handle most cleanup, but this ensures consistency
        pattern = f"{RedisKeyBuilder.SESSION_PREFIX}:*"
        cleaned = 0

        try:
            client = await self.connection_manager.get_client()
            cursor = 0

            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)

                for key in keys:
                    session_data = await self.operations.get_json(key)
                    if session_data:
                        try:
                            session = self._deserialize_session(session_data)
                            if session.is_expired():
                                await self.operations.delete(key)
                                cleaned += 1
                        except Exception as e:
                            logger.error(f"Error checking session {key}: {e}")

                if cursor == 0:
                    break

        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired sessions")

        return cleaned

    def _serialize_session(self, session: UserSession) -> Dict[str, Any]:
        """Serialize UserSession to dictionary.

        Args:
            session: UserSession to serialize

        Returns:
            Serialized session data
        """
        return {
            "id": str(session.id),
            "user_id": session.user_id,
            "session_token": session.session_token,
            "preferences": {
                "temperature_unit": session.preferences.temperature_unit,
                "default_location": session.preferences.default_location.dict() if session.preferences.default_location else None,
                "language": session.preferences.language,
                "time_format": session.preferences.time_format
            },
            "monitored_locations": [
                loc.dict() for loc in session.monitored_locations
            ],
            "conversation_history": [
                {
                    "user_query": turn.user_query,
                    "assistant_response": turn.assistant_response,
                    "timestamp": turn.timestamp.isoformat(),
                    "location_context": turn.location_context.dict() if turn.location_context else None
                }
                for turn in session.conversation_history
            ],
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "status": session.status.value
        }

    def _deserialize_session(self, data: Dict[str, Any]) -> UserSession:
        """Deserialize dictionary to UserSession.

        Args:
            data: Session data dictionary

        Returns:
            UserSession instance
        """
        # Reconstruct preferences
        pref_data = data.get("preferences", {})
        preferences = UserPreferences(
            temperature_unit=pref_data.get("temperature_unit", "Fahrenheit"),
            default_location=Location(**pref_data["default_location"]) if pref_data.get("default_location") else None,
            language=pref_data.get("language", "en"),
            time_format=pref_data.get("time_format", "12h")
        )

        # Reconstruct locations
        monitored_locations = [
            Location(**loc_data)
            for loc_data in data.get("monitored_locations", [])
        ]

        # Reconstruct conversation history
        conversation_history = []
        for turn_data in data.get("conversation_history", []):
            location = None
            if turn_data.get("location_context"):
                location = Location(**turn_data["location_context"])

            turn = ConversationTurn(
                user_query=turn_data["user_query"],
                assistant_response=turn_data["assistant_response"],
                timestamp=datetime.fromisoformat(turn_data["timestamp"]),
                location_context=location
            )
            conversation_history.append(turn)

        # Create session
        session = UserSession(
            id=UUID(data["id"]),
            user_id=data["user_id"],
            session_token=data["session_token"],
            preferences=preferences,
            monitored_locations=monitored_locations,
            conversation_history=conversation_history,
            created_at=datetime.fromisoformat(data["created_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            status=SessionStatus(data.get("status", "active"))
        )

        return session


class SessionMetrics:
    """Track session metrics in Redis."""

    def __init__(self, redis_operations: RedisOperations):
        """Initialize session metrics.

        Args:
            redis_operations: Redis operations instance
        """
        self.operations = redis_operations

    async def record_session_created(self, user_id: str) -> None:
        """Record session creation metric.

        Args:
            user_id: User identifier
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H")
        key = RedisKeyBuilder.metrics_key("sessions_created", timestamp)
        await self.operations.hincrby(key, user_id, 1)
        await self.operations.expire(key, 86400)  # 24 hour TTL

    async def record_session_activity(self, user_id: str) -> None:
        """Record session activity metric.

        Args:
            user_id: User identifier
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H")
        key = RedisKeyBuilder.metrics_key("session_activity", timestamp)
        await self.operations.hincrby(key, user_id, 1)
        await self.operations.expire(key, 86400)  # 24 hour TTL

    async def get_active_session_count(self) -> int:
        """Get count of active sessions.

        Returns:
            Number of active sessions
        """
        pattern = f"{RedisKeyBuilder.SESSION_PREFIX}:*"
        try:
            client = await self.operations.connection_manager.get_client()
            cursor = 0
            count = 0

            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)
                count += len(keys)
                if cursor == 0:
                    break

            return count
        except Exception as e:
            logger.error(f"Failed to count active sessions: {e}")
            return 0