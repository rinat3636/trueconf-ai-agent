from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.user import User
from app.models.knowledge import Document, KnowledgeItem
from app.models.analytics import SalesReport, ChatMessage, ModerationQueue
from app.schemas.analytics import SystemStats, TrueConfStatus
from app.services.trueconf_bot import trueconf_bot

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
        select(func.count(KnowledgeItem.id)).where(KnowledgeItem.is_approved == True)
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

    tc_status = await trueconf_bot.get_status()
    trueconf_info = TrueConfStatus(
        enabled=tc_status.get("enabled", False),
        connected=tc_status.get("connected", False),
        running=tc_status.get("running", False),
        server_url=tc_status.get("server_url", ""),
        bot_user=tc_status.get("bot_user", ""),
        active_chats=tc_status.get("active_chats", 0),
    )

    return SystemStats(
        total_documents=total_documents,
        total_knowledge_items=total_knowledge,
        approved_knowledge_items=approved_knowledge,
        total_queries=total_queries,
        total_users=total_users,
        total_reports=total_reports,
        pending_moderation=pending_moderation,
        positive_feedback_pct=round(positive_pct, 1) if positive_pct is not None else None,
        trueconf=trueconf_info,
    )
