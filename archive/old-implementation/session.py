"""Session management API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from typing import List, Optional
from uuid import UUID
import structlog

from src.models.user_session import (
    SessionInfo,
    MonitoredLocations,
    UpdateLocationsRequest,
    UserSession
)
from src.models.location import Location
from src.services.session_service import SessionStorageService as SessionService

logger = structlog.get_logger(__name__)

router = APIRouter()


async def get_current_user(request: Request) -> str:
    """Extract current user from request context."""
    # In production, this would validate OAuth token
    # For now, return a default user or from header
    user_id = request.headers.get("X-User-ID", "anonymous")
    return user_id


async def get_session_id_from_header(request: Request) -> Optional[str]:
    """Extract session ID from request header."""
    return request.headers.get("X-Session-ID")


@router.get("/session", response_model=SessionInfo)
async def get_session_info(
    request: Request,
    user_id: str = Depends(get_current_user),
    session_id: Optional[str] = Depends(get_session_id_from_header)
) -> SessionInfo:
    """
    Get current session information.

    Returns information about the current user session including
    creation time, expiration, and conversation count.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "Session info requested",
        user_id=user_id,
        session_id=session_id,
        request_id=request_id
    )

    try:
        session_service = SessionService()

        # If session_id not provided, get the most recent session
        if not session_id:
            sessions = await session_service.get_user_sessions(user_id)
            if not sessions:
                # Create a new session
                session = await session_service.create_session(user_id)
                logger.info("Created new session", session_id=str(session.id), user_id=user_id)
            else:
                # Get the most recent active session
                session = sessions[0]
        else:
            # Get specific session
            session = await session_service.get_session(session_id)
            if not session:
                logger.warning("Session not found", session_id=session_id)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found"
                )

            # Verify session belongs to user
            if session.user_id != user_id:
                logger.warning(
                    "Session access denied",
                    session_id=session_id,
                    user_id=user_id,
                    session_user_id=session.user_id
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )

        # Check if session is expired
        if session.is_expired():
            logger.info("Session expired", session_id=str(session.id))
            # Create a new session
            session = await session_service.create_session(user_id)
            logger.info("Created replacement session", session_id=str(session.id))

        return SessionInfo(
            session_id=session.id,
            user_id=session.user_id,
            created_at=session.created_at,
            expires_at=session.expires_at,
            conversation_count=len(session.conversation_history)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get session info",
            error=str(e),
            user_id=user_id,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session information"
        )


@router.get("/session/locations", response_model=MonitoredLocations)
async def get_monitored_locations(
    request: Request,
    user_id: str = Depends(get_current_user),
    session_id: Optional[str] = Depends(get_session_id_from_header)
) -> MonitoredLocations:
    """
    Get monitored locations for the session.

    Returns the list of locations being monitored for weather alerts
    in the current session.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "Monitored locations requested",
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
            # Get most recent session
            sessions = await session_service.get_user_sessions(user_id)
            if not sessions:
                # Return empty list if no session
                return MonitoredLocations(locations=[])
            session = sessions[0]

        # Verify session belongs to user
        if session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        return MonitoredLocations(
            locations=session.monitored_locations
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get monitored locations",
            error=str(e),
            user_id=user_id,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve monitored locations"
        )


@router.put("/session/locations", response_model=MonitoredLocations)
async def update_monitored_locations(
    request: Request,
    locations_request: UpdateLocationsRequest,
    user_id: str = Depends(get_current_user),
    session_id: Optional[str] = Depends(get_session_id_from_header)
) -> MonitoredLocations:
    """
    Update monitored locations for the session.

    Updates the list of locations to monitor for weather alerts.
    Maximum of 3 locations allowed per session.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "Update monitored locations requested",
        user_id=user_id,
        session_id=session_id,
        locations_count=len(locations_request.locations),
        request_id=request_id
    )

    try:
        session_service = SessionService()

        # Get or create session
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
            else:
                session = sessions[0]

        # Verify session belongs to user
        if session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Update locations
        session.monitored_locations = locations_request.locations
        session.update_activity()

        # Save session
        await session_service.update_session(session)

        logger.info(
            "Monitored locations updated",
            session_id=str(session.id),
            locations_count=len(session.monitored_locations)
        )

        return MonitoredLocations(
            locations=session.monitored_locations
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update monitored locations",
            error=str(e),
            user_id=user_id,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update monitored locations"
        )