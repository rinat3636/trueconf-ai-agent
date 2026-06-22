from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON

from app.core.database import Base


class SalesReport(Base):
    __tablename__ = "sales_reports"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    period_start = Column(String(50), nullable=True)
    period_end = Column(String(50), nullable=True)
    report_type = Column(String(50), default="sales")  # sales, reps, clients
    total_revenue = Column(Float, nullable=True)
    total_profit = Column(Float, nullable=True)
    total_clients = Column(Integer, nullable=True)
    total_skus = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    analysis_json = Column(JSON, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="processing")  # processing, ready, error
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SalesRecord(Base):
    __tablename__ = "sales_records"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("sales_reports.id"), nullable=False)
    manager_name = Column(String(255), nullable=True)
    client_name = Column(String(500), nullable=True)
    product_name = Column(String(500), nullable=True)
    quantity = Column(Float, nullable=True)
    tonnage = Column(Float, nullable=True)
    revenue = Column(Float, nullable=True)
    profit = Column(Float, nullable=True)
    margin_pct = Column(Float, nullable=True)
    record_level = Column(String(20), default="product")  # manager, client, product


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)
    feedback = Column(String(20), nullable=True)  # useful, not_useful
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ModerationQueue(Base):
    __tablename__ = "moderation_queue"

    id = Column(Integer, primary_key=True, index=True)
    item_type = Column(String(50), nullable=False)  # new_knowledge, conflict, suggestion, bad_answer
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    source_info = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending, approved, rejected
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime, nullable=True)
