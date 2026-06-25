import os
import uuid
import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.core.config import UPLOAD_DIR
from app.core.audit import log_action
from app.models.user import User
from app.models.knowledge import (
    Document, KnowledgeItem, KnowledgeItemVersion,
    CorporateRule, AnswerCorrection, KnowledgeConflict, ModerationQueue,
)
from app.schemas.knowledge import (
    DocumentResponse,
    KnowledgeItemCreate, KnowledgeItemUpdate, KnowledgeItemResponse,
    CorporateRuleCreate, CorporateRuleResponse,
    AnswerCorrectionCreate, AnswerCorrectionResponse,
    ModerationItemResponse, ModerationAction,
    ConflictResponse, ConflictResolve,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt", ".pptx"}


async def process_document_background(document_id: int, file_path: str, category: str):
    """Background task: full document processing pipeline with conflict detection."""
    from app.core.database import async_session
    from app.services.self_learning import process_document_pipeline

    async with async_session() as db:
        await process_document_pipeline(document_id, file_path, db)


# --- Documents ---

@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form("other"),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    content = await file.read()

    checksum = hashlib.sha256(content).hexdigest()
    result = await db.execute(select(Document).where(Document.checksum_sha256 == checksum))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This file has already been uploaded (duplicate checksum)")

    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = str(UPLOAD_DIR / "documents" / unique_name)
    with open(file_path, "wb") as f:
        f.write(content)

    document = Document(
        uploaded_by=current_user.id,
        filename=unique_name,
        original_filename=file.filename,
        file_type=ext.lstrip("."),
        file_path=file_path,
        file_size=len(content),
        category=category,
        status="processing",
        checksum_sha256=checksum,
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)

    await log_action(
        db, "upload_document", user_id=current_user.id,
        entity_type="document", entity_id=document.id,
        new_value={"filename": file.filename, "category": category},
    )

    background_tasks.add_task(process_document_background, document.id, file_path, category)

    return DocumentResponse.model_validate(document)


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Document).order_by(Document.created_at.desc())
    if category:
        query = query.where(Document.category == category)
    result = await db.execute(query)
    return [DocumentResponse.model_validate(d) for d in result.scalars().all()]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    from app.core.qdrant import delete_by_filter, KNOWLEDGE_COLLECTION
    try:
        delete_by_filter(KNOWLEDGE_COLLECTION, "document_id", document_id)
    except Exception:
        pass

    await log_action(
        db, "delete_document", user_id=current_user.id,
        entity_type="document", entity_id=document_id,
    )
    await db.delete(doc)
    return {"status": "deleted"}


@router.post("/documents/{document_id}/reprocess")
async def reprocess_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = "processing"
    background_tasks.add_task(process_document_background, doc.id, doc.file_path, doc.category)
    return {"status": "reprocessing"}


# --- Knowledge Items ---

@router.get("/items", response_model=list[KnowledgeItemResponse])
async def list_knowledge_items(
    category: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(KnowledgeItem).order_by(KnowledgeItem.created_at.desc())
    if category:
        query = query.where(KnowledgeItem.category == category)
    if status:
        query = query.where(KnowledgeItem.status == status)
    result = await db.execute(query)
    return [KnowledgeItemResponse.model_validate(i) for i in result.scalars().all()]


@router.post("/items", response_model=KnowledgeItemResponse)
async def create_knowledge_item(
    item: KnowledgeItemCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    knowledge = KnowledgeItem(
        title=item.title,
        content=item.content,
        category=item.category,
        priority=item.priority,
        status="approved",
        approved_by=current_user.id,
    )
    db.add(knowledge)
    await db.flush()
    await db.refresh(knowledge)

    from app.services.knowledge_service import add_knowledge_item_to_vector_db
    await add_knowledge_item_to_vector_db(
        knowledge.id, knowledge.content, knowledge.title,
        knowledge.category, knowledge.priority,
    )

    # Invalidate chat cache
    from app.core.redis import delete_cached
    await delete_cached("chat:*")

    await log_action(
        db, "create_knowledge", user_id=current_user.id,
        entity_type="knowledge_item", entity_id=knowledge.id,
    )
    return KnowledgeItemResponse.model_validate(knowledge)


@router.put("/items/{item_id}", response_model=KnowledgeItemResponse)
async def update_knowledge_item(
    item_id: int,
    item: KnowledgeItemUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == item_id))
    knowledge = result.scalar_one_or_none()
    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    version_entry = KnowledgeItemVersion(
        item_id=knowledge.id,
        version=knowledge.version,
        title=knowledge.title,
        content=knowledge.content,
        changed_by=current_user.id,
        change_reason="Updated via admin panel",
    )
    db.add(version_entry)

    if item.title is not None:
        knowledge.title = item.title
    if item.content is not None:
        knowledge.content = item.content
    if item.category is not None:
        knowledge.category = item.category
    if item.priority is not None:
        knowledge.priority = item.priority
    knowledge.version += 1

    from app.services.knowledge_service import add_knowledge_item_to_vector_db
    await add_knowledge_item_to_vector_db(
        knowledge.id, knowledge.content, knowledge.title,
        knowledge.category, knowledge.priority,
    )

    # Invalidate chat cache
    from app.core.redis import delete_cached
    await delete_cached("chat:*")

    await log_action(
        db, "update_knowledge", user_id=current_user.id,
        entity_type="knowledge_item", entity_id=knowledge.id,
    )
    return KnowledgeItemResponse.model_validate(knowledge)


@router.delete("/items/{item_id}")
async def delete_knowledge_item(
    item_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == item_id))
    knowledge = result.scalar_one_or_none()
    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    knowledge.status = "archived"

    # Remove from Qdrant vector DB
    from app.core.qdrant import delete_vectors, KNOWLEDGE_COLLECTION
    import uuid
    try:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"knowledge_{item_id}"))
        delete_vectors(KNOWLEDGE_COLLECTION, [point_id])
    except Exception:
        pass

    # Invalidate chat cache
    from app.core.redis import delete_cached
    await delete_cached("chat:*")

    await log_action(
        db, "delete_knowledge", user_id=current_user.id,
        entity_type="knowledge_item", entity_id=knowledge.id,
    )
    return {"status": "archived"}


@router.get("/items/{item_id}/versions")
async def get_knowledge_versions(
    item_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeItemVersion).where(KnowledgeItemVersion.item_id == item_id)
        .order_by(KnowledgeItemVersion.version.desc())
    )
    versions = result.scalars().all()
    return [
        {
            "id": v.id,
            "version": v.version,
            "title": v.title,
            "content": v.content,
            "changed_by": v.changed_by,
            "change_reason": v.change_reason,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]


# --- Reindex ---

@router.post("/reindex")
async def reindex_knowledge(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    await log_action(db, "reindex_knowledge", user_id=current_user.id)
    background_tasks.add_task(_reindex_all)
    return {"status": "reindexing started"}


async def _reindex_all():
    from app.core.database import async_session
    from app.services.knowledge_service import (
        add_knowledge_item_to_vector_db,
        add_correction_to_vector_db,
        add_document_to_knowledge_base,
    )

    async with async_session() as db:
        # Re-embed approved knowledge items
        result = await db.execute(
            select(KnowledgeItem).where(KnowledgeItem.status == "approved")
        )
        items = result.scalars().all()
        for item in items:
            await add_knowledge_item_to_vector_db(
                item.id, item.content, item.title, item.category, item.priority
            )

        # Re-embed active corrections
        corr_result = await db.execute(
            select(AnswerCorrection).where(AnswerCorrection.is_active == True)
        )
        corrections = corr_result.scalars().all()
        for c in corrections:
            await add_correction_to_vector_db(
                c.id, c.original_question, c.corrected_answer,
                c.correction_type, c.priority,
            )

        # Re-embed processed documents
        doc_result = await db.execute(
            select(Document).where(Document.status == "processed")
        )
        docs = doc_result.scalars().all()
        for doc in docs:
            if os.path.exists(doc.file_path):
                try:
                    await add_document_to_knowledge_base(
                        doc.file_path, doc.id, doc.category
                    )
                except Exception:
                    pass


# --- Search ---

@router.get("/search")
async def search_knowledge_api(
    query: str,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Search knowledge base via vector similarity."""
    from app.services.knowledge_service import search_knowledge

    results = await search_knowledge(query, n_results=10, category=category)
    return [
        {
            "content": r["content"],
            "category": r["metadata"].get("category", "general"),
            "title": r["metadata"].get("title", ""),
            "score": round(r["score"], 3),
            "source": r["metadata"].get("source", ""),
        }
        for r in results
    ]


# --- Corporate Rules ---

@router.get("/rules", response_model=list[CorporateRuleResponse])
async def list_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CorporateRule).order_by(CorporateRule.priority.desc(), CorporateRule.created_at.desc())
    )
    return [CorporateRuleResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/rules", response_model=CorporateRuleResponse)
async def create_rule(
    rule: CorporateRuleCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    corporate_rule = CorporateRule(
        created_by=current_user.id,
        rule_type=rule.rule_type,
        title=rule.title,
        content=rule.content,
        priority=rule.priority,
        category=rule.category,
    )
    db.add(corporate_rule)
    await db.flush()
    await db.refresh(corporate_rule)

    await log_action(
        db, "create_rule", user_id=current_user.id,
        entity_type="corporate_rule", entity_id=corporate_rule.id,
    )
    return CorporateRuleResponse.model_validate(corporate_rule)


@router.put("/rules/{rule_id}", response_model=CorporateRuleResponse)
async def update_rule(
    rule_id: int,
    rule: CorporateRuleCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CorporateRule).where(CorporateRule.id == rule_id))
    existing = result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="Rule not found")

    existing.rule_type = rule.rule_type
    existing.title = rule.title
    existing.content = rule.content
    existing.priority = rule.priority
    existing.category = rule.category

    await log_action(
        db, "update_rule", user_id=current_user.id,
        entity_type="corporate_rule", entity_id=rule_id,
    )
    return CorporateRuleResponse.model_validate(existing)


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CorporateRule).where(CorporateRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await log_action(
        db, "delete_rule", user_id=current_user.id,
        entity_type="corporate_rule", entity_id=rule_id,
    )
    return {"status": "deleted"}


@router.patch("/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CorporateRule).where(CorporateRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = not rule.is_active
    return {"status": "ok", "is_active": rule.is_active}


# --- Answer Corrections ---

@router.get("/corrections", response_model=list[AnswerCorrectionResponse])
async def list_corrections(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AnswerCorrection).order_by(AnswerCorrection.created_at.desc()))
    return [AnswerCorrectionResponse.model_validate(c) for c in result.scalars().all()]


@router.post("/corrections", response_model=AnswerCorrectionResponse)
async def create_correction(
    correction: AnswerCorrectionCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    answer_correction = AnswerCorrection(
        created_by=current_user.id,
        message_id=correction.message_id,
        original_question=correction.original_question,
        original_answer=correction.original_answer,
        corrected_answer=correction.corrected_answer,
        correction_type=correction.correction_type,
        priority=95 if correction.correction_type == "answer_fix" else 80,
        notes=correction.notes,
    )
    db.add(answer_correction)
    await db.flush()
    await db.refresh(answer_correction)

    from app.services.knowledge_service import add_correction_to_vector_db
    await add_correction_to_vector_db(
        answer_correction.id,
        answer_correction.original_question,
        answer_correction.corrected_answer,
        correction_type=correction.correction_type,
        priority=answer_correction.priority,
    )

    if correction.correction_type != "answer_fix":
        mod_item = ModerationQueue(
            item_type="correction_review",
            item_id=answer_correction.id,
            action=f"review_{correction.correction_type}",
            payload={
                "correction_id": answer_correction.id,
                "correction_type": correction.correction_type,
                "original_question": correction.original_question,
                "corrected_answer": correction.corrected_answer[:500],
                "notes": correction.notes,
            },
            status="pending",
            created_by=current_user.id,
        )
        db.add(mod_item)

    await log_action(
        db, "create_correction", user_id=current_user.id,
        entity_type="answer_correction", entity_id=answer_correction.id,
        new_value={"correction_type": correction.correction_type},
    )
    return AnswerCorrectionResponse.model_validate(answer_correction)


# --- Moderation ---

@router.get("/moderation", response_model=list[ModerationItemResponse])
async def list_moderation_queue(
    status: Optional[str] = "pending",
    item_type: Optional[str] = None,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(ModerationQueue).order_by(ModerationQueue.created_at.desc())
    if status:
        query = query.where(ModerationQueue.status == status)
    if item_type:
        query = query.where(ModerationQueue.item_type == item_type)
    result = await db.execute(query)
    return [ModerationItemResponse.model_validate(i) for i in result.scalars().all()]


@router.get("/moderation/stats")
async def moderation_stats(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func
    result = await db.execute(
        select(ModerationQueue.status, func.count(ModerationQueue.id))
        .group_by(ModerationQueue.status)
    )
    stats = {row[0]: row[1] for row in result.all()}
    return stats


@router.post("/moderation/approve-all")
async def approve_all_pending(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Bulk approve all pending moderation items and their knowledge items."""
    from datetime import datetime, timezone
    from app.services.knowledge_service import add_knowledge_item_to_vector_db

    result = await db.execute(
        select(ModerationQueue).where(ModerationQueue.status == "pending")
    )
    pending_items = result.scalars().all()

    approved_count = 0
    for item in pending_items:
        item.status = "approved"
        item.reviewed_by = current_user.id
        item.reviewed_at = datetime.now(timezone.utc)

        if item.item_type in ("new_knowledge", "self_learned") and item.item_id:
            ki_result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == item.item_id))
            ki = ki_result.scalar_one_or_none()
            if ki and ki.status != "approved":
                ki.status = "approved"
                ki.approved_by = current_user.id
                try:
                    await add_knowledge_item_to_vector_db(
                        ki.id, ki.content, ki.title, ki.category, ki.priority
                    )
                except Exception:
                    pass
        approved_count += 1

    await db.commit()
    return {"status": "ok", "approved": approved_count}


@router.post("/moderation/{item_id}/action")
async def moderate_item_action(
    item_id: int,
    action: ModerationAction,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Unified moderation action endpoint (approve/reject)."""
    if action.action == "approve":
        return await approve_moderation(item_id, action, current_user, db)
    elif action.action == "reject":
        return await reject_moderation(item_id, action, current_user, db)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action.action}")


@router.post("/moderation/{item_id}/approve")
async def approve_moderation(
    item_id: int,
    action: ModerationAction,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ModerationQueue).where(ModerationQueue.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Moderation item not found")

    from datetime import datetime, timezone

    item.status = "approved"
    item.reviewed_by = current_user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_notes = action.notes

    if item.item_type in ("new_knowledge", "self_learned") and item.item_id:
        ki_result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == item.item_id))
        ki = ki_result.scalar_one_or_none()
        if ki:
            ki.status = "approved"
            ki.approved_by = current_user.id
            try:
                from app.services.knowledge_service import add_knowledge_item_to_vector_db
                await add_knowledge_item_to_vector_db(
                    ki.id, ki.content, ki.title, ki.category, ki.priority
                )
            except RuntimeError as e:
                logger.warning("Skipping vector indexing (embeddings unavailable): %s", e)

    await log_action(
        db, "approve_moderation", user_id=current_user.id,
        entity_type="moderation_queue", entity_id=item_id,
    )
    return {"status": "approved"}


@router.post("/moderation/{item_id}/reject")
async def reject_moderation(
    item_id: int,
    action: ModerationAction,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ModerationQueue).where(ModerationQueue.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Moderation item not found")

    from datetime import datetime, timezone

    item.status = "rejected"
    item.reviewed_by = current_user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_notes = action.notes

    if item.item_id:
        ki_result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == item.item_id))
        ki = ki_result.scalar_one_or_none()
        if ki:
            ki.status = "rejected"

    await log_action(
        db, "reject_moderation", user_id=current_user.id,
        entity_type="moderation_queue", entity_id=item_id,
    )
    return {"status": "rejected"}


# --- Knowledge Conflicts ---

async def _build_conflict_response(db: AsyncSession, conflict: KnowledgeConflict) -> ConflictResponse:
    """Enrich a conflict with item titles and fall back to item content
    for legacy rows where the preview columns were never populated."""
    new_item = await db.get(KnowledgeItem, conflict.new_item_id)
    existing_item = await db.get(KnowledgeItem, conflict.existing_item_id)

    response = ConflictResponse.model_validate(conflict)
    response.new_title = new_item.title if new_item else None
    response.existing_title = existing_item.title if existing_item else None
    if not response.new_content_preview and new_item:
        response.new_content_preview = (new_item.content or "")[:500]
    if not response.existing_content_preview and existing_item:
        response.existing_content_preview = (existing_item.content or "")[:500]
    return response


@router.get("/conflicts", response_model=list[ConflictResponse])
async def list_conflicts(
    resolution: Optional[str] = "pending",
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(KnowledgeConflict).order_by(KnowledgeConflict.created_at.desc())
    if resolution:
        query = query.where(KnowledgeConflict.resolution == resolution)
    result = await db.execute(query)
    conflicts = result.scalars().all()
    return [await _build_conflict_response(db, c) for c in conflicts]


@router.get("/conflicts/{conflict_id}", response_model=ConflictResponse)
async def get_conflict(
    conflict_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeConflict).where(KnowledgeConflict.id == conflict_id))
    conflict = result.scalar_one_or_none()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    return await _build_conflict_response(db, conflict)


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: int,
    data: ConflictResolve,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeConflict).where(KnowledgeConflict.id == conflict_id))
    conflict = result.scalar_one_or_none()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")

    from datetime import datetime, timezone

    conflict.resolution = data.resolution
    conflict.resolved_by = current_user.id
    conflict.resolved_at = datetime.now(timezone.utc)
    conflict.notes = data.notes

    if data.resolution == "replace_old":
        old_result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == conflict.existing_item_id))
        old_item = old_result.scalar_one_or_none()
        if old_item:
            old_item.status = "archived"

        new_result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == conflict.new_item_id))
        new_item = new_result.scalar_one_or_none()
        if new_item:
            new_item.status = "approved"
            new_item.approved_by = current_user.id

    elif data.resolution == "keep_old":
        new_result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == conflict.new_item_id))
        new_item = new_result.scalar_one_or_none()
        if new_item:
            new_item.status = "rejected"

    elif data.resolution == "merge" and data.merged_content:
        old_result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == conflict.existing_item_id))
        old_item = old_result.scalar_one_or_none()
        if old_item:
            old_item.content = data.merged_content
            old_item.version += 1
            from app.services.knowledge_service import add_knowledge_item_to_vector_db
            await add_knowledge_item_to_vector_db(
                old_item.id, old_item.content, old_item.title,
                old_item.category, old_item.priority,
            )

        new_result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == conflict.new_item_id))
        new_item = new_result.scalar_one_or_none()
        if new_item:
            new_item.status = "archived"

    await log_action(
        db, "resolve_conflict", user_id=current_user.id,
        entity_type="knowledge_conflict", entity_id=conflict_id,
        new_value={"resolution": data.resolution},
    )
    return {"status": "resolved", "resolution": data.resolution}
