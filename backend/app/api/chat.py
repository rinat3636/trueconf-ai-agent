from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.models.knowledge import ModerationQueue
from app.schemas.knowledge import ChatRequest, ChatResponse, FeedbackRequest
from app.services.chat_service import generate_answer

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if request.session_id:
        result = await db.execute(select(ChatSession).where(ChatSession.id == request.session_id))
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = ChatSession(
            user_id=current_user.id,
            channel=request.channel,
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)

    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)
    await db.flush()

    # Load chat history for context
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .where(ChatMessage.id != user_msg.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    history_msgs = list(reversed(history_result.scalars().all()))
    chat_history = [
        {"role": m.role, "content": m.content}
        for m in history_msgs
    ]

    try:
        answer_data = await generate_answer(request.message, db, chat_history=chat_history)
    except RuntimeError as e:
        error_msg = str(e)
        if "rate_limit" in error_msg.lower() or "лимит" in error_msg.lower():
            answer_data = {
                "answer": "Превышен лимит запросов к ИИ. Попробуйте через пару минут.",
                "sources": [],
                "rules_applied": [],
                "confidence": 0.0,
                "response_time_ms": 0,
                "trace": {"error": error_msg},
            }
        else:
            raise

    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer_data["answer"],
        trace=answer_data.get("trace", {}),
        response_time_ms=answer_data.get("response_time_ms", 0),
    )
    db.add(assistant_msg)
    await db.flush()
    await db.refresh(assistant_msg)

    session.last_activity_at = datetime.now(timezone.utc)

    return ChatResponse(
        answer=answer_data["answer"],
        session_id=session.id,
        message_id=assistant_msg.id,
        sources=answer_data.get("sources", []),
        rules_applied=answer_data.get("rules_applied", []),
        confidence=answer_data.get("confidence", 0.0),
        response_time_ms=answer_data.get("response_time_ms", 0),
    )


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ChatMessage).where(ChatMessage.id == request.message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    msg.feedback = request.feedback
    msg.feedback_comment = request.comment

    if request.feedback == "not_useful":
        mod_item = ModerationQueue(
            item_type="bad_feedback",
            item_id=msg.id,
            action="review_bad_answer",
            payload={
                "message_id": msg.id,
                "session_id": msg.session_id,
                "content": msg.content,
                "user": current_user.username,
                "comment": request.comment,
            },
            status="pending",
        )
        db.add(mod_item)

    return {"status": "ok"}


@router.get("/sessions")
async def list_sessions(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(ChatSession).where(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.last_activity_at.desc()).limit(limit)

    # Admins can see all sessions
    if current_user.role in ("super_admin", "admin"):
        query = select(ChatSession).order_by(ChatSession.last_activity_at.desc()).limit(limit)

    result = await db.execute(query)
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "user_id": s.user_id,
            "channel": s.channel,
            "started_at": s.started_at.isoformat(),
            "last_activity_at": s.last_activity_at.isoformat(),
        }
        for s in sessions
    ]


@router.get("/messages/{session_id}")
async def get_session_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if current_user.role not in ("super_admin", "admin") and session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "trace": m.trace,
            "feedback": m.feedback,
            "response_time_ms": m.response_time_ms,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


@router.get("/history")
async def get_chat_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(ChatMessage)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "feedback": m.feedback,
            "created_at": m.created_at.isoformat(),
        }
        for m in reversed(messages)
    ]
