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
from app.models.analytics import SalesReport, SalesRecord
from app.schemas.analytics import (
    SalesReportResponse,
    AnalysisQuestionRequest,
    AnalysisQuestionResponse,
)
from app.services.analytics_service import (
    get_sales_analytics,
    get_manager_analysis,
    get_client_analysis,
    generate_ai_recommendations,
    answer_analytics_question,
)
from app.services.document_processor import parse_sales_report

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


async def process_sales_report_background(report_id: int, file_path: str):
    from app.core.database import async_session

    async with async_session() as db:
        try:
            records, metadata = parse_sales_report(file_path)

            result = await db.execute(select(SalesReport).where(SalesReport.id == report_id))
            report = result.scalar_one_or_none()
            if not report:
                return

            for record in records:
                sales_record = SalesRecord(
                    report_id=report_id,
                    manager_name=record.get("manager_name"),
                    client_name=record.get("client_name"),
                    product_name=record.get("product_name"),
                    quantity=record.get("quantity"),
                    tonnage=record.get("tonnage"),
                    revenue=record.get("revenue"),
                    profit=record.get("profit"),
                    margin_pct=record.get("margin_pct"),
                    record_level=record.get("record_level", "product"),
                )
                db.add(sales_record)

            report.period_start = metadata.get("period", "").split(" - ")[0] if " - " in metadata.get("period", "") else metadata.get("period")
            report.period_end = metadata.get("period", "").split(" - ")[1] if " - " in metadata.get("period", "") else None
            report.total_revenue = metadata.get("total_revenue")
            report.total_profit = metadata.get("total_profit")
            report.total_clients = metadata.get("total_clients")
            report.total_skus = metadata.get("total_skus")
            report.status = "ready"

            summary_parts = []
            if metadata.get("period"):
                summary_parts.append(f"Период: {metadata['period']}")
            if metadata.get("total_revenue"):
                summary_parts.append(f"Выручка: {metadata['total_revenue']:,.0f} руб.")
            if metadata.get("total_profit"):
                summary_parts.append(f"Прибыль: {metadata['total_profit']:,.0f} руб.")
            if metadata.get("total_managers"):
                summary_parts.append(f"Менеджеров: {metadata['total_managers']}")
            if metadata.get("total_clients"):
                summary_parts.append(f"Клиентов: {metadata['total_clients']}")
            if metadata.get("total_skus"):
                summary_parts.append(f"SKU: {metadata['total_skus']}")
            report.summary = "; ".join(summary_parts)

            await db.commit()
        except Exception as e:
            result = await db.execute(select(SalesReport).where(SalesReport.id == report_id))
            report = result.scalar_one_or_none()
            if report:
                report.status = "error"
                report.summary = f"Error: {str(e)}"
            await db.commit()


@router.post("/reports/upload", response_model=SalesReportResponse)
async def upload_sales_report(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    report_type: str = Form("sales"),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".xlsx", ".xls", ".csv"}:
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, .csv files supported")

    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = str(UPLOAD_DIR / "reports" / unique_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    report = SalesReport(
        filename=unique_name,
        original_filename=file.filename,
        report_type=report_type,
        uploaded_by=current_user.id,
        status="processing",
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)

    background_tasks.add_task(process_sales_report_background, report.id, file_path)

    return SalesReportResponse.model_validate(report)


@router.get("/reports", response_model=list[SalesReportResponse])
async def list_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SalesReport).order_by(SalesReport.created_at.desc()))
    reports = result.scalars().all()
    return [SalesReportResponse.model_validate(r) for r in reports]


@router.get("/reports/{report_id}", response_model=SalesReportResponse)
async def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SalesReport).where(SalesReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return SalesReportResponse.model_validate(report)


@router.get("/reports/{report_id}/analytics")
async def get_report_analytics(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SalesReport).where(SalesReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != "ready":
        raise HTTPException(status_code=400, detail="Report is still processing")

    analytics = await get_sales_analytics(db, report_id)
    return analytics


@router.get("/reports/{report_id}/managers")
async def get_report_managers(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis = await get_manager_analysis(db, report_id)
    return analysis


@router.get("/reports/{report_id}/clients")
async def get_report_clients(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis = await get_client_analysis(db, report_id)
    return analysis


@router.get("/reports/{report_id}/recommendations")
async def get_report_recommendations(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analytics = await get_sales_analytics(db, report_id)
    recommendations = await generate_ai_recommendations(analytics)
    return {"recommendations": recommendations}


@router.post("/ask", response_model=AnalysisQuestionResponse)
async def ask_analytics_question(
    request: AnalysisQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    answer = await answer_analytics_question(db, request.question, request.report_id)
    return AnalysisQuestionResponse(answer=answer)
