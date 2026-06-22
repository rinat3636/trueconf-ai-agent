from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class DocumentUploadResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    category: Optional[str]
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
    category: Optional[str]
    description: Optional[str]
    status: str
    chunk_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeItemCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = None


class KnowledgeItemResponse(BaseModel):
    id: int
    title: str
    content: str
    category: Optional[str]
    is_approved: bool
    source_document_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class CorporateRuleCreate(BaseModel):
    rule_type: str
    title: str
    content: str


class CorporateRuleResponse(BaseModel):
    id: int
    rule_type: str
    title: str
    content: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AnswerCorrectionCreate(BaseModel):
    original_question: str
    original_answer: str
    corrected_answer: str


class AnswerCorrectionResponse(BaseModel):
    id: int
    original_question: str
    original_answer: str
    corrected_answer: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: Optional[List[str]] = None
    session_id: str


class FeedbackRequest(BaseModel):
    message_id: int
    feedback: str  # useful / not_useful


class ModerationItemResponse(BaseModel):
    id: int
    item_type: str
    title: str
    content: str
    source_info: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ModerationAction(BaseModel):
    action: str  # approve / reject
