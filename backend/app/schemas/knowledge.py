from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# --- Documents ---

class DocumentUploadResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    category: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    category: str
    description: Optional[str]
    summary: Optional[str] = None
    status: str
    chunk_count: int
    error_message: Optional[str] = None
    checksum_sha256: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Knowledge Items ---

class KnowledgeItemCreate(BaseModel):
    title: str
    content: str
    category: str = "other"
    priority: int = 50


class KnowledgeItemUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[int] = None


class KnowledgeItemResponse(BaseModel):
    id: int
    title: str
    content: str
    category: str
    status: str
    version: int
    priority: int
    document_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Corporate Rules ---

class CorporateRuleCreate(BaseModel):
    rule_type: str
    title: str
    content: str
    priority: int = 50
    category: Optional[str] = None


class CorporateRuleResponse(BaseModel):
    id: int
    rule_type: str
    title: str
    content: str
    priority: int
    is_active: bool
    category: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Answer Corrections ---

class AnswerCorrectionCreate(BaseModel):
    message_id: Optional[int] = None
    original_question: str
    original_answer: str = ""
    corrected_answer: str
    correction_type: str = "answer_fix"  # answer_fix, new_knowledge, new_rule, knowledge_update
    notes: Optional[str] = None


class AnswerCorrectionResponse(BaseModel):
    id: int
    original_question: str
    original_answer: str
    corrected_answer: str
    correction_type: str
    priority: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- Chat ---

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[int] = None
    channel: str = "web"


class SourceInfo(BaseModel):
    document_id: Optional[int] = None
    document_title: str
    relevance_score: float
    chunk_preview: str


class RuleInfo(BaseModel):
    rule_id: int
    title: str
    rule_type: str
    priority: int


class ChatResponse(BaseModel):
    answer: str
    session_id: int
    message_id: int
    sources: List[SourceInfo] = []
    rules_applied: List[RuleInfo] = []
    confidence: float = 0.0
    response_time_ms: int = 0


class FeedbackRequest(BaseModel):
    message_id: int
    feedback: str  # useful / not_useful
    comment: Optional[str] = None


# --- Moderation ---

class ModerationItemResponse(BaseModel):
    id: int
    item_type: str
    item_id: Optional[int]
    action: str
    payload: dict
    status: str
    review_notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ModerationAction(BaseModel):
    action: str  # approve / reject
    notes: Optional[str] = None


# --- Knowledge Conflicts ---

class ConflictResponse(BaseModel):
    id: int
    new_item_id: int
    existing_item_id: int
    conflict_type: str
    similarity_score: Optional[float]
    new_content_preview: Optional[str]
    existing_content_preview: Optional[str]
    resolution: str
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ConflictResolve(BaseModel):
    resolution: str  # replace_old, keep_old, merge
    merged_content: Optional[str] = None
    notes: Optional[str] = None
