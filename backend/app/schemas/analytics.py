from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class SalesReportResponse(BaseModel):
    id: int
    original_filename: str
    period_start: Optional[str]
    period_end: Optional[str]
    report_type: str
    total_revenue: Optional[float]
    total_profit: Optional[float]
    total_clients: Optional[int]
    total_skus: Optional[int]
    summary: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class SalesAnalyticsResponse(BaseModel):
    report_id: int
    period: str
    total_revenue: float
    total_profit: float
    avg_margin: float
    top_managers: List[Dict[str, Any]]
    top_clients: List[Dict[str, Any]]
    top_products: List[Dict[str, Any]]
    weak_managers: List[Dict[str, Any]]
    declining_clients: List[Dict[str, Any]]
    recommendations: List[str]


class ManagerAnalysis(BaseModel):
    name: str
    revenue: float
    profit: float
    margin: float
    client_count: int
    sku_count: int
    top_categories: List[Dict[str, Any]]
    top_clients: List[Dict[str, Any]]


class ClientAnalysis(BaseModel):
    name: str
    manager: str
    revenue: float
    profit: float
    margin: float
    sku_count: int
    top_products: List[Dict[str, Any]]


class AnalysisQuestionRequest(BaseModel):
    question: str
    report_id: Optional[int] = None


class AnalysisQuestionResponse(BaseModel):
    answer: str
    data: Optional[Dict[str, Any]] = None


class SystemStats(BaseModel):
    total_documents: int
    total_knowledge_items: int
    approved_knowledge_items: int
    total_queries: int
    total_users: int
    total_reports: int
    pending_moderation: int
    positive_feedback_pct: Optional[float]
