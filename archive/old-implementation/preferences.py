"""User preferences API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import structlog

from src.models.user_session import UserPreferences
from src.models.location import Location
from src.services.session_service import SessionStorageService as SessionService

logger = structlog.get_logger(__name__)

router = APIRouter()


class PreferencesUpdateRequest(BaseModel):
    """Request model for updating preferences."""
    temperature_unit: Optional[str] = Field(None, pattern="^(Celsius|Fahrenheit|Kelvin)$")
    language: Optional[str] = Field(None, pattern="^[a-z]{2}$")  # ISO 639-1
    time_format: Optional[str] = Field(None, pattern="^(12h|24h)$")
    default_location: Optional[Location] = None

    @field_validator("temperature_unit")
    @classmethod
    def validate_temperature_unit(cls, v):
        """Validate temperature unit."""
        if v and v not in ["Celsius", "Fahrenheit", "Kelvin"]:
            raise ValueError("Temperature unit must be Celsius, Fahrenheit, or Kelvin")
        return v

    @field_validator("time_format")
    @classmethod
    def validate_time_format(cls, v):
        """Validate time format."""
        if v and v not in ["12h", "24h"]:
            raise ValueError("Time format must be 12h or 24h")
        return v


async def get_current_user(request: Request) -> str:
    """Extract current user from request context."""
    # In production, this would validate OAuth token
    # For now, return a default user or from header
    user_id = request.headers.get("X-User-ID", "anonymous")
    return user_id


async def get_session_id_from_header(request: Request) -> Optional[str]:
    """Extract session ID from request header."""
    return request.headers.get("X-Session-ID")


@router.get("/session/preferences", response_model=UserPreferences)
async def get_preferences(
    request: Request,
    user_id: str = Depends(get_current_user),
    session_id: Optional[str] = Depends(get_session_id_from_header)
) -> UserPreferences:
    """
    Get user preferences for the session.

    Returns the current user preferences including temperature unit,
    language, time format, and default location.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "Preferences requested",
        user_id=user_id,
        session_id=session_id,
        request_id=request_id
    )

    try:
        session_service = SessionService()

        # Get session
        if session_id:
            session = await session_service.get_session(session_id)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found"
                )
        else:
            # Get most recent session or create new one
            sessions = await session_service.get_user_sessions(user_id)
            if not sessions:
                session = await session_service.create_session(user_id)
                logger.info("Created new session for preferences", session_id=str(session.id))
            else:
                session = sessions[0]

        # Verify session belongs to user
        if session.user_id != user_id:
            logger.warning(
                "Preferences access denied",
                session_id=str(session.id),
                user_id=user_id,
                session_user_id=session.user_id
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        logger.info(
            "Preferences retrieved",
            session_id=str(session.id),
            temperature_unit=session.preferences.temperature_unit,
            language=session.preferences.language
        )

        return session.preferences

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get preferences",
            error=str(e),
            user_id=user_id,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve preferences"
        )


@router.patch("/session/preferences", response_model=UserPreferences)
async def update_preferences(
    request: Request,
    preferences_update: PreferencesUpdateRequest,
    user_id: str = Depends(get_current_user),
    session_id: Optional[str] = Depends(get_session_id_from_header)
) -> UserPreferences:
    """
    Update user preferences for the session.

    Allows partial updates to user preferences. Only provided fields
    will be updated; others remain unchanged.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "Preferences update requested",
        user_id=user_id,
        session_id=session_id,
        updates=preferences_update.model_dump(exclude_none=True),
        request_id=request_id
    )

    try:
        session_service = SessionService()

        # Get session
        if session_id:
            session = await session_service.get_session(session_id)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found"
                )
        else:
            # Get most recent session or create new one
            sessions = await session_service.get_user_sessions(user_id)
            if not sessions:
                session = await session_service.create_session(user_id)
                logger.info("Created new session for preferences update", session_id=str(session.id))
            else:
                session = sessions[0]

        # Verify session belongs to user
        if session.user_id != user_id:
            logger.warning(
                "Preferences update denied",
                session_id=str(session.id),
                user_id=user_id,
                session_user_id=session.user_id
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Apply updates
        update_data = preferences_update.model_dump(exclude_none=True)
        for field, value in update_data.items():
            if hasattr(session.preferences, field):
                setattr(session.preferences, field, value)

        # Update session activity
        session.update_activity()

        # Save session
        await session_service.update_session(session)

        logger.info(
            "Preferences updated",
            session_id=str(session.id),
            updates=update_data
        )

        return session.preferences

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update preferences",
            error=str(e),
            user_id=user_id,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )