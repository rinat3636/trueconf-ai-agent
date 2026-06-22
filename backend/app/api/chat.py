from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.analytics import ChatMessage
from app.schemas.knowledge import ChatRequest, ChatResponse, FeedbackRequest
from app.services.chat_service import generate_answer

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_msg = ChatMessage(
        user_id=current_user.id,
        session_id=request.session_id or "new",
        role="user",
        content=request.message,
    )
    db.add(user_msg)

    answer, sources, session_id = await generate_answer(
        request.message, db, request.session_id
    )

    assistant_msg = ChatMessage(
        user_id=current_user.id,
        session_id=session_id,
        role="assistant",
        content=answer,
        sources=sources,
    )
    db.add(assistant_msg)
    await db.flush()

    return ChatResponse(answer=answer, sources=sources, session_id=session_id)


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

    if request.feedback == "not_useful":
        from app.models.analytics import ModerationQueue
        mod_item = ModerationQueue(
            item_type="bad_answer",
            title=f"Bad answer report for message #{request.message_id}",
            content=f"Question: {msg.content}\n\nThis answer was marked as not useful.",
            source_info=f"User: {current_user.username}",
            status="pending",
        )
        db.add(mod_item)

    return {"status": "ok"}


@router.get("/history")
async def get_chat_history(
    session_id: str = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(ChatMessage).where(
        ChatMessage.user_id == current_user.id
    ).order_by(ChatMessage.created_at.desc()).limit(limit)

    if session_id:
        query = query.where(ChatMessage.session_id == session_id)

    result = await db.execute(query)
    messages = result.scalars().all()

    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "sources": m.sources,
            "feedback": m.feedback,
            "created_at": m.created_at.isoformat(),
        }
        for m in reversed(messages)
    ]
