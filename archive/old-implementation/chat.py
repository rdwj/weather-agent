"""Chat API endpoints for weather agent."""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from typing import Optional, List
from datetime import datetime
import structlog
from uuid import uuid4

from src.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatSession,
    ChatMessage,
    SessionListResponse,
    SessionDetailResponse
)
from src.services.chat_service import ChatService
from src.services.session_service import SessionStorageService
from src.lib.redis_client import RedisConnectionManager

logger = structlog.get_logger(__name__)
router = APIRouter()


async def get_current_user(request: Request) -> str:
    """Extract current user from request context."""
    # In production, this would validate OAuth token
    # For now, return from header or default
    return request.headers.get("X-User-ID", "default-user")


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    chat_request: ChatRequest,
    user_id: str = Depends(get_current_user)
) -> ChatResponse:
    """
    Process a chat message and return response.

    This endpoint handles natural language weather queries in a conversational manner.
    It maintains session context for multi-turn conversations.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "Chat request received",
        user_id=user_id,
        message_preview=chat_request.message[:100],
        session_id=chat_request.session_id,
        request_id=request_id
    )

    try:
        # Initialize services
        chat_service = ChatService()
        session_service = SessionStorageService()
        await session_service.initialize()  # Initialize Redis connection

        # Get or create session (handle "string" as None)
        session_id = chat_request.session_id
        if not session_id or session_id == "string":
            # Create new session
            session = ChatSession(
                session_id=str(uuid4()),
                user_id=user_id
            )
            await session_service.save_session(session.session_id, session.model_dump())
            session_id = session.session_id
            logger.info("Created new session", session_id=session_id)
        else:
            # Retrieve existing session
            session_data = await session_service.get_session(session_id)
            if not session_data:
                logger.warning("Invalid session ID, creating new", session_id=session_id)
                session = ChatSession(
                    session_id=str(uuid4()),
                    user_id=user_id
                )
                await session_service.save_session(session.session_id, session.model_dump())
                session_id = session.session_id
            else:
                session = ChatSession(**session_data)

        # Add user message to session
        user_message = ChatMessage(
            role="user",
            content=chat_request.message,
            timestamp=datetime.utcnow()
        )
        session.messages.append(user_message)

        # Process message through chat service with model parameters
        response_text, metadata, suggestions = await chat_service.process_message(
            message=chat_request.message,
            session=session,
            context=chat_request.context,
            model_params=chat_request.model_params
        )

        # Add assistant response to session
        assistant_message = ChatMessage(
            role="assistant",
            content=response_text,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )
        session.messages.append(assistant_message)
        session.updated_at = datetime.utcnow()

        # Save updated session
        await session_service.save_session(session_id, session.model_dump())

        logger.info(
            "Chat response generated",
            session_id=session_id,
            has_metadata=bool(metadata),
            has_suggestions=bool(suggestions)
        )

        return ChatResponse(
            response=response_text,
            session_id=session_id,
            metadata=metadata,
            suggestions=suggestions
        )

    except Exception as e:
        logger.error(
            "Failed to process chat message",
            error=str(e),
            user_id=user_id,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process your message. Please try again."
        )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    request: Request,
    limit: int = 10,
    offset: int = 0,
    user_id: str = Depends(get_current_user)
) -> SessionListResponse:
    """
    List user's chat sessions.

    Returns a paginated list of the user's chat sessions with basic metadata.
    """
    logger.info("Session list requested", user_id=user_id, limit=limit, offset=offset)

    try:
        session_service = SessionStorageService()
        await session_service.initialize()  # Initialize Redis connection
        sessions = await session_service.list_user_sessions(user_id, limit, offset)

        # Create session summaries
        session_summaries = []
        for session_data in sessions:
            session = ChatSession(**session_data)
            summary = {
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "message_count": len(session.messages),
                "last_message": session.messages[-1].content[:100] if session.messages else None,
                "active": session.active
            }
            session_summaries.append(summary)

        return SessionListResponse(
            sessions=session_summaries,
            total=len(session_summaries)
        )

    except Exception as e:
        logger.error("Failed to list sessions", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions"
        )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    request: Request,
    session_id: str,
    user_id: str = Depends(get_current_user)
) -> SessionDetailResponse:
    """
    Get detailed session information including full message history.
    """
    logger.info("Session detail requested", session_id=session_id, user_id=user_id)

    try:
        session_service = SessionStorageService()
        await session_service.initialize()  # Initialize Redis connection
        session_data = await session_service.get_session(session_id)

        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        session = ChatSession(**session_data)

        # Verify user owns this session
        if session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        return SessionDetailResponse(
            session_id=session.session_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            messages=session.messages,
            context=session.context,
            message_count=len(session.messages)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get session", error=str(e), session_id=session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session"
        )


@router.post("/sessions", response_model=ChatSession)
async def create_session(
    request: Request,
    user_id: str = Depends(get_current_user)
) -> ChatSession:
    """
    Create a new chat session.
    """
    logger.info("Creating new session", user_id=user_id)

    try:
        session_service = SessionStorageService()
        await session_service.initialize()  # Initialize Redis connection

        # Create new session
        session = ChatSession(
            session_id=str(uuid4()),
            user_id=user_id
        )

        # Save session
        await session_service.save_session(session.session_id, session.model_dump())

        logger.info("Session created", session_id=session.session_id)
        return session

    except Exception as e:
        logger.error("Failed to create session", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session"
        )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    request: Request,
    session_id: str,
    user_id: str = Depends(get_current_user)
) -> None:
    """
    Delete a chat session.
    """
    logger.info("Session deletion requested", session_id=session_id, user_id=user_id)

    try:
        session_service = SessionStorageService()
        await session_service.initialize()  # Initialize Redis connection

        # Get session to verify ownership
        session_data = await session_service.get_session(session_id)
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        session = ChatSession(**session_data)
        if session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Delete session
        await session_service.delete_session(session_id)
        logger.info("Session deleted", session_id=session_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete session", error=str(e), session_id=session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session"
        )