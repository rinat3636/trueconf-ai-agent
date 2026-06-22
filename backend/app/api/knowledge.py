import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.core.config import UPLOAD_DIR
from app.models.user import User
from app.models.knowledge import Document, KnowledgeItem, CorporateRule, AnswerCorrection
from app.models.analytics import ModerationQueue
from app.schemas.knowledge import (
    DocumentResponse,
    KnowledgeItemCreate,
    KnowledgeItemResponse,
    CorporateRuleCreate,
    CorporateRuleResponse,
    AnswerCorrectionCreate,
    AnswerCorrectionResponse,
    ModerationItemResponse,
    ModerationAction,
)
from app.services.knowledge_service import (
    add_document_to_knowledge_base,
    add_knowledge_item_to_vector_db,
    add_correction_to_vector_db,
    generate_document_summary,
    extract_knowledge_from_text,
    delete_document_from_vector_db,
)
from app.services.document_processor import extract_text

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt"}


async def process_document_background(
    document_id: int,
    file_path: str,
    category: Optional[str],
):
    from app.core.database import async_session

    async with async_session() as db:
        try:
            text = extract_text(file_path)

            summary = await generate_document_summary(text)
            chunk_count = await add_document_to_knowledge_base(file_path, document_id, category)
            knowledge_items = await extract_knowledge_from_text(text)

            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.description = summary
                doc.chunk_count = chunk_count
                doc.status = "ready"

            for item in knowledge_items:
                mod_item = ModerationQueue(
                    item_type="new_knowledge",
                    title=item["title"],
                    content=item["content"],
                    source_info=f"Document ID: {document_id}",
                    status="pending",
                )
                db.add(mod_item)

            await db.commit()
        except Exception as e:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "error"
                doc.description = f"Error: {str(e)}"
            await db.commit()


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = str(UPLOAD_DIR / "documents" / unique_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    document = Document(
        filename=unique_name,
        original_filename=file.filename,
        file_type=ext.lstrip("."),
        file_size=len(content),
        category=category,
        uploaded_by=current_user.id,
        status="processing",
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)

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
    docs = result.scalars().all()
    return [DocumentResponse.model_validate(d) for d in docs]


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

    file_path = str(UPLOAD_DIR / "documents" / doc.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    delete_document_from_vector_db(document_id)
    await db.delete(doc)
    return {"status": "deleted"}


@router.get("/items", response_model=list[KnowledgeItemResponse])
async def list_knowledge_items(
    category: Optional[str] = None,
    approved_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(KnowledgeItem).order_by(KnowledgeItem.created_at.desc())
    if category:
        query = query.where(KnowledgeItem.category == category)
    if approved_only:
        query = query.where(KnowledgeItem.is_approved == True)
    result = await db.execute(query)
    items = result.scalars().all()
    return [KnowledgeItemResponse.model_validate(i) for i in items]


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
        is_approved=True,
        approved_by=current_user.id,
        created_by=current_user.id,
    )
    db.add(knowledge)
    await db.flush()
    await db.refresh(knowledge)

    await add_knowledge_item_to_vector_db(knowledge.id, knowledge.content, knowledge.category)

    return KnowledgeItemResponse.model_validate(knowledge)


@router.put("/items/{item_id}", response_model=KnowledgeItemResponse)
async def update_knowledge_item(
    item_id: int,
    item: KnowledgeItemCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == item_id))
    knowledge = result.scalar_one_or_none()
    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    knowledge.title = item.title
    knowledge.content = item.content
    knowledge.category = item.category

    await add_knowledge_item_to_vector_db(knowledge.id, knowledge.content, knowledge.category)

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

    await db.delete(knowledge)
    return {"status": "deleted"}


# --- Corporate Rules ---

@router.get("/rules", response_model=list[CorporateRuleResponse])
async def list_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CorporateRule).order_by(CorporateRule.created_at.desc()))
    rules = result.scalars().all()
    return [CorporateRuleResponse.model_validate(r) for r in rules]


@router.post("/rules", response_model=CorporateRuleResponse)
async def create_rule(
    rule: CorporateRuleCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    corporate_rule = CorporateRule(
        rule_type=rule.rule_type,
        title=rule.title,
        content=rule.content,
        created_by=current_user.id,
    )
    db.add(corporate_rule)
    await db.flush()
    await db.refresh(corporate_rule)
    return CorporateRuleResponse.model_validate(corporate_rule)


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
    return {"status": "deleted"}


# --- Answer Corrections ---

@router.get("/corrections", response_model=list[AnswerCorrectionResponse])
async def list_corrections(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AnswerCorrection).order_by(AnswerCorrection.created_at.desc()))
    corrections = result.scalars().all()
    return [AnswerCorrectionResponse.model_validate(c) for c in corrections]


@router.post("/corrections", response_model=AnswerCorrectionResponse)
async def create_correction(
    correction: AnswerCorrectionCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    answer_correction = AnswerCorrection(
        original_question=correction.original_question,
        original_answer=correction.original_answer,
        corrected_answer=correction.corrected_answer,
        corrected_by=current_user.id,
    )
    db.add(answer_correction)
    await db.flush()
    await db.refresh(answer_correction)

    await add_correction_to_vector_db(
        answer_correction.id,
        answer_correction.original_question,
        answer_correction.corrected_answer,
    )

    return AnswerCorrectionResponse.model_validate(answer_correction)


# --- Moderation ---

@router.get("/moderation", response_model=list[ModerationItemResponse])
async def list_moderation_queue(
    status: Optional[str] = "pending",
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(ModerationQueue).order_by(ModerationQueue.created_at.desc())
    if status:
        query = query.where(ModerationQueue.status == status)
    result = await db.execute(query)
    items = result.scalars().all()
    return [ModerationItemResponse.model_validate(i) for i in items]


@router.post("/moderation/{item_id}/action")
async def moderate_item(
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

    if action.action == "approve":
        item.status = "approved"
        item.reviewed_by = current_user.id
        item.reviewed_at = datetime.now(timezone.utc)

        knowledge = KnowledgeItem(
            title=item.title,
            content=item.content,
            is_approved=True,
            approved_by=current_user.id,
            created_by=current_user.id,
        )
        db.add(knowledge)
        await db.flush()
        await db.refresh(knowledge)

        await add_knowledge_item_to_vector_db(knowledge.id, knowledge.content)
    elif action.action == "reject":
        item.status = "rejected"
        item.reviewed_by = current_user.id
        item.reviewed_at = datetime.now(timezone.utc)
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    return {"status": item.status}
