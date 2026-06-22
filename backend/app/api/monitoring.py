from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user
from app.models.user import User
from app.models.knowledge import Document, KnowledgeItem, ModerationQueue
from app.models.analytics import SalesReport
from app.models.chat import ChatSession, ChatMessage
from app.models.audit import AuditLog
from app.schemas.analytics import SystemStats, AuditLogResponse

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    docs_result = await db.execute(select(func.count(Document.id)))
    total_documents = docs_result.scalar() or 0

    ki_result = await db.execute(select(func.count(KnowledgeItem.id)))
    total_knowledge = ki_result.scalar() or 0

    approved_result = await db.execute(
        select(func.count(KnowledgeItem.id)).where(KnowledgeItem.status == "approved")
    )
    approved_knowledge = approved_result.scalar() or 0

    queries_result = await db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.role == "user")
    )
    total_queries = queries_result.scalar() or 0

    users_result = await db.execute(select(func.count(User.id)))
    total_users = users_result.scalar() or 0

    reports_result = await db.execute(select(func.count(SalesReport.id)))
    total_reports = reports_result.scalar() or 0

    pending_result = await db.execute(
        select(func.count(ModerationQueue.id)).where(ModerationQueue.status == "pending")
    )
    pending_moderation = pending_result.scalar() or 0

    total_feedback = await db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.feedback.isnot(None))
    )
    total_fb = total_feedback.scalar() or 0

    positive_feedback = await db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.feedback == "useful")
    )
    positive_fb = positive_feedback.scalar() or 0

    positive_pct = (positive_fb / total_fb * 100) if total_fb > 0 else None

    return SystemStats(
        total_documents=total_documents,
        total_knowledge_items=total_knowledge,
        approved_knowledge_items=approved_knowledge,
        total_queries=total_queries,
        total_users=total_users,
        total_reports=total_reports,
        pending_moderation=pending_moderation,
        positive_feedback_pct=round(positive_pct, 1) if positive_pct is not None else None,
    )


@router.get("/audit", response_model=list[AuditLogResponse])
async def get_audit_log(
    limit: int = 100,
    action: Optional[str] = None,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if action:
        query = query.where(AuditLog.action == action)
    result = await db.execute(query)
    return [AuditLogResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/health")
async def health_check():
    import redis.asyncio as aioredis
    from app.core.config import settings
    from app.core.database import engine

    status = {"status": "ok", "services": {}}

    try:
        async with engine.connect() as conn:
            await conn.execute(select(func.count()).select_from(User.__table__))
        status["services"]["mysql"] = "ok"
    except Exception as e:
        status["services"]["mysql"] = f"error: {str(e)}"
        status["status"] = "degraded"

    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        await r.close()
        status["services"]["redis"] = "ok"
    except Exception as e:
        status["services"]["redis"] = f"error: {str(e)}"
        status["status"] = "degraded"

    try:
        from app.core.qdrant import get_qdrant
        client = get_qdrant()
        client.get_collections()
        status["services"]["qdrant"] = "ok"
    except Exception as e:
        status["services"]["qdrant"] = f"error: {str(e)}"
        status["status"] = "degraded"

    return status
