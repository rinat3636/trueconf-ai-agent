from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Index, JSON

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer, nullable=False)
    category = Column(String(50), nullable=False, default="other")
    status = Column(String(20), nullable=False, default="pending")  # pending, processing, processed, error
    error_message = Column(Text, nullable=True)
    chunk_count = Column(Integer, default=0)
    description = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)
    checksum_sha256 = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_documents_status", "status"),
        Index("idx_documents_category", "category"),
        Index("idx_documents_checksum", "checksum_sha256"),
    )


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, default="other")
    status = Column(String(20), nullable=False, default="pending_review")  # draft, pending_review, approved, rejected, archived
    version = Column(Integer, nullable=False, default=1)
    qdrant_point_id = Column(String(100), nullable=True)
    priority = Column(Integer, nullable=False, default=50)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    source_chunk = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_knowledge_status", "status"),
        Index("idx_knowledge_category", "category"),
        Index("idx_knowledge_document", "document_id"),
    )


class KnowledgeItemVersion(Base):
    __tablename__ = "knowledge_item_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    change_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_ki_versions", "item_id", "version"),
    )


class CorporateRule(Base):
    __tablename__ = "corporate_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    rule_type = Column(String(50), nullable=False)  # communication, terminology, preferred_phrasing, restriction, business_rule, system_prompt
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    priority = Column(Integer, nullable=False, default=50)
    is_active = Column(Boolean, default=True, nullable=False)
    category = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_rules_active", "is_active"),
        Index("idx_rules_type", "rule_type"),
    )


class AnswerCorrection(Base):
    __tablename__ = "answer_corrections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True)
    original_question = Column(Text, nullable=False)
    original_answer = Column(Text, nullable=False)
    corrected_answer = Column(Text, nullable=False)
    correction_type = Column(String(30), nullable=False, default="answer_fix")  # answer_fix, new_knowledge, new_rule, knowledge_update
    priority = Column(Integer, nullable=False, default=90)
    linked_knowledge_item_id = Column(Integer, ForeignKey("knowledge_items.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_corrections_active", "is_active"),
    )


class KnowledgeConflict(Base):
    __tablename__ = "knowledge_conflicts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    new_item_id = Column(Integer, ForeignKey("knowledge_items.id"), nullable=False)
    existing_item_id = Column(Integer, ForeignKey("knowledge_items.id"), nullable=False)
    conflict_type = Column(String(50), nullable=False)  # contradiction, duplicate, partial_overlap
    similarity_score = Column(Float, nullable=True)
    new_content_preview = Column(Text, nullable=True)
    existing_content_preview = Column(Text, nullable=True)
    resolution = Column(String(20), nullable=False, default="pending")  # pending, replace_old, keep_old, merge
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_conflicts_pending", "resolution"),
    )


class ModerationQueue(Base):
    __tablename__ = "moderation_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_type = Column(String(30), nullable=False)  # new_knowledge, self_learned, correction_review, conflict, bad_feedback
    item_id = Column(Integer, nullable=True)
    action = Column(String(100), nullable=False, default="review")
    payload = Column(JSON, default=dict)
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_moderation_pending", "status", "created_at"),
        Index("idx_moderation_type", "item_type"),
    )
