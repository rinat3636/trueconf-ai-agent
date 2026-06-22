"""
Self-learning pipeline (ARCHITECTURE.md section 6.3).

Triggers:
  - New document uploaded → extract_knowledge_task
  - Chat messages batch analysis → analyze_messages_task (periodic)
  - New report uploaded → analyze_report_task

All extracted knowledge goes to moderation queue — NEVER auto-approved.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.knowledge import (
    Document,
    KnowledgeItem,
    KnowledgeConflict,
    ModerationQueue,
)
from app.models.chat import ChatMessage, ChatSession
from app.services.knowledge_service import (
    extract_knowledge_from_text,
    run_conflict_detection,
    generate_document_summary,
    analyze_unanswered_questions,
    add_document_to_knowledge_base,
)
from app.services.document_processor import (
    extract_text,
    compute_file_checksum,
    detect_document_category,
)

logger = logging.getLogger(__name__)


async def process_document_pipeline(
    document_id: int,
    file_path: str,
    db: AsyncSession,
    user_id: Optional[int] = None,
):
    """Full document processing pipeline:
    1. Extract text
    2. Compute checksum
    3. Auto-detect category
    4. Generate summary (LLM)
    5. Chunk + embed → Qdrant
    6. Extract knowledge items (LLM)
    7. For each extracted knowledge:
       a. Check for conflicts (vector + LLM)
       b. Create KnowledgeItem (status=pending_review)
       c. Create ModerationQueue entry
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        logger.error(f"Document {document_id} not found")
        return

    try:
        doc.status = "processing"
        await db.commit()

        # Step 1: Extract text
        text = extract_text(file_path)
        if not text or len(text.strip()) < 50:
            doc.status = "error"
            doc.error_message = "Не удалось извлечь текст из документа (возможно, это скан — нужен OCR)"
            await db.commit()
            return

        # Step 2: Checksum
        checksum = compute_file_checksum(file_path)
        doc.checksum_sha256 = checksum

        # Step 3: Auto-detect category if not set
        if not doc.category:
            doc.category = detect_document_category(doc.filename, text)

        # Step 4: Generate summary
        try:
            summary = await generate_document_summary(text)
            doc.summary = summary
        except Exception as e:
            logger.warning(f"Failed to generate summary for doc {document_id}: {e}")

        # Step 5: Chunk + embed → Qdrant
        try:
            chunk_count = await add_document_to_knowledge_base(
                file_path, document_id, category=doc.category
            )
            doc.chunk_count = chunk_count
        except Exception as e:
            logger.error(f"Failed to index document {document_id}: {e}")
            doc.error_message = f"Ошибка индексации: {str(e)}"

        # Step 6: Extract knowledge items
        try:
            knowledge_items = await extract_knowledge_from_text(text)
        except Exception as e:
            logger.warning(f"Failed to extract knowledge from doc {document_id}: {e}")
            knowledge_items = []

        # Step 7: For each extracted knowledge item
        for ki_data in knowledge_items:
            ki = KnowledgeItem(
                document_id=document_id,
                title=ki_data["title"],
                content=ki_data["content"],
                category=ki_data.get("category", doc.category or "general"),
                status="pending_review",
                version=1,
                priority=50,
                source_chunk=ki_data.get("source_chunk", ""),
            )
            db.add(ki)
            await db.flush()
            await db.refresh(ki)

            # 7a: Check for conflicts
            try:
                conflicts = await run_conflict_detection(ki_data["content"], new_item_id=ki.id)
                for conflict_data in conflicts:
                    conflict = KnowledgeConflict(
                        new_item_id=ki.id,
                        existing_item_id=conflict_data.get("existing_item_id"),
                        conflict_type=conflict_data["conflict_type"],
                        similarity_score=conflict_data.get("similarity_score", 0.0),
                        resolution="pending",
                    )
                    db.add(conflict)
                    await db.flush()

                    # Create moderation queue entry for conflict
                    mod_conflict = ModerationQueue(
                        item_type="conflict",
                        item_id=conflict.id,
                        action="resolve_conflict",
                        payload={
                            "new_item_title": ki.title,
                            "conflict_type": conflict_data["conflict_type"],
                            "similarity_score": conflict_data.get("similarity_score"),
                            "existing_item_id": conflict_data.get("existing_item_id"),
                        },
                        status="pending",
                        created_by=user_id,
                    )
                    db.add(mod_conflict)
            except Exception as e:
                logger.warning(f"Conflict detection failed for item {ki.id}: {e}")

            # 7b: Create moderation queue entry for new knowledge
            mod_item = ModerationQueue(
                item_type="new_knowledge",
                item_id=ki.id,
                action="approve_knowledge",
                payload={
                    "title": ki.title,
                    "content": ki.content[:500],
                    "category": ki.category,
                    "document_id": document_id,
                    "document_name": doc.filename,
                },
                status="pending",
                created_by=user_id,
            )
            db.add(mod_item)

        doc.status = "processed"
        doc.processed_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info(
            f"Document {document_id} processed: {doc.chunk_count} chunks, "
            f"{len(knowledge_items)} knowledge items extracted"
        )

    except Exception as e:
        logger.error(f"Document processing pipeline failed for {document_id}: {e}")
        doc.status = "error"
        doc.error_message = str(e)[:1000]
        await db.commit()
        raise


async def analyze_messages_task(db: AsyncSession, hours: int = 6):
    """Periodic task: analyze chat messages from the last N hours.

    1. Messages with feedback='not_useful' → create moderation task
    2. Messages with low confidence (< 0.3) → analyze missing knowledge
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # 1. Bad feedback messages
    bad_feedback_result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.feedback == "not_useful",
            ChatMessage.created_at >= cutoff,
            ChatMessage.role == "assistant",
        )
    )
    bad_messages = bad_feedback_result.scalars().all()

    for msg in bad_messages:
        existing = await db.execute(
            select(ModerationQueue).where(
                ModerationQueue.item_type == "bad_feedback",
                ModerationQueue.item_id == msg.id,
                ModerationQueue.status == "pending",
            )
        )
        if existing.scalar_one_or_none():
            continue

        mod_item = ModerationQueue(
            item_type="bad_feedback",
            item_id=msg.id,
            action="review_bad_answer",
            payload={
                "message_id": msg.id,
                "session_id": msg.session_id,
                "answer": msg.content[:500],
                "feedback_comment": msg.feedback_comment,
            },
            status="pending",
        )
        db.add(mod_item)

    # 2. Low-confidence answers → analyze gaps
    low_conf_result = await db.execute(
        select(ChatMessage)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .where(
            ChatMessage.role == "user",
            ChatMessage.created_at >= cutoff,
        )
    )
    user_messages = low_conf_result.scalars().all()

    low_conf_questions = []
    for msg in user_messages:
        assistant_result = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == msg.session_id,
                ChatMessage.role == "assistant",
                ChatMessage.created_at > msg.created_at,
            ).order_by(ChatMessage.created_at).limit(1)
        )
        assistant_msg = assistant_result.scalar_one_or_none()
        if assistant_msg and assistant_msg.trace:
            trace = assistant_msg.trace
            sources = trace.get("sources", [])
            if not sources:
                low_conf_questions.append(msg.content)

    if low_conf_questions:
        try:
            gaps = await analyze_unanswered_questions(low_conf_questions)
            for gap in gaps:
                mod_item = ModerationQueue(
                    item_type="self_learned",
                    item_id=0,
                    action="add_missing_knowledge",
                    payload={
                        "gap": gap["gap"],
                        "recommendation": gap["recommendation"],
                        "sample_questions": low_conf_questions[:5],
                    },
                    status="pending",
                )
                db.add(mod_item)
        except Exception as e:
            logger.warning(f"Failed to analyze unanswered questions: {e}")

    await db.commit()
    logger.info(
        f"Message analysis complete: {len(bad_messages)} bad feedback, "
        f"{len(low_conf_questions)} unanswered questions"
    )
