from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Index, JSON

from app.core.database import Base


class SalesReport(Base):
    __tablename__ = "sales_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    period_start = Column(String(50), nullable=True)
    period_end = Column(String(50), nullable=True)
    branch = Column(String(255), nullable=True)
    report_type = Column(String(50), default="sales")
    total_revenue = Column(Float, nullable=True)
    total_profit = Column(Float, nullable=True)
    total_clients = Column(Integer, nullable=True)
    total_skus = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    analysis_json = Column(JSON, nullable=True)
    metadata_json = Column(JSON, default=dict)
    status = Column(String(20), nullable=False, default="pending")  # pending, processing, processed, error
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime, nullable=True)


class SalesRecord(Base):
    __tablename__ = "sales_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey("sales_reports.id", ondelete="CASCADE"), nullable=False)
    level = Column(String(20), nullable=False)  # rep, client, product
    parent_id = Column(Integer, ForeignKey("sales_records.id"), nullable=True)
    name = Column(Text, nullable=False)
    quantity = Column(Float, nullable=True)
    tonnage = Column(Float, nullable=True)
    revenue = Column(Float, nullable=True)
    gross_profit = Column(Float, nullable=True)
    margin_pct = Column(Float, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_sales_report", "report_id"),
        Index("idx_sales_level", "level"),
        Index("idx_sales_parent", "parent_id"),
    )
