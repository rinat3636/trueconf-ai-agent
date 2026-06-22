import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.core.config import UPLOAD_DIR
from app.core.audit import log_action
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
    from datetime import datetime, timezone

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
                    level=record.get("level", "product"),
                    name=record.get("name", ""),
                    quantity=record.get("quantity"),
                    tonnage=record.get("tonnage"),
                    revenue=record.get("revenue"),
                    gross_profit=record.get("gross_profit") or record.get("profit"),
                    margin_pct=record.get("margin_pct"),
                )
                db.add(sales_record)

            period = metadata.get("period", "")
            if " - " in period:
                parts = period.split(" - ")
                report.period_start = parts[0]
                report.period_end = parts[1]
            else:
                report.period_start = period
            report.total_revenue = metadata.get("total_revenue")
            report.total_profit = metadata.get("total_profit")
            report.total_clients = metadata.get("total_clients")
            report.total_skus = metadata.get("total_skus")
            report.status = "processed"
            report.processed_at = datetime.now(timezone.utc)

            summary_parts = []
            if metadata.get("period"):
                summary_parts.append(f"Период: {metadata['period']}")
            if metadata.get("total_revenue"):
                summary_parts.append(f"Выручка: {metadata['total_revenue']:,.0f} руб.")
            if metadata.get("total_profit"):
                summary_parts.append(f"Прибыль: {metadata['total_profit']:,.0f} руб.")
            if metadata.get("total_managers"):
                summary_parts.append(f"Менеджеров: {metadata['total_managers']}")
            report.summary = "; ".join(summary_parts)

            await db.commit()
        except Exception as e:
            result = await db.execute(select(SalesReport).where(SalesReport.id == report_id))
            report = result.scalar_one_or_none()
            if report:
                report.status = "error"
                report.summary = f"Ошибка: {str(e)}"
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

    content = await file.read()
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = str(UPLOAD_DIR / "reports" / unique_name)
    with open(file_path, "wb") as f:
        f.write(content)

    report = SalesReport(
        uploaded_by=current_user.id,
        filename=unique_name,
        original_filename=file.filename,
        file_path=file_path,
        report_type=report_type,
        status="processing",
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)

    await log_action(
        db, "upload_report", user_id=current_user.id,
        entity_type="sales_report", entity_id=report.id,
    )

    background_tasks.add_task(process_sales_report_background, report.id, file_path)
    return SalesReportResponse.model_validate(report)


@router.get("/reports", response_model=list[SalesReportResponse])
async def list_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SalesReport).order_by(SalesReport.created_at.desc()))
    return [SalesReportResponse.model_validate(r) for r in result.scalars().all()]


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


@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SalesReport).where(SalesReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if os.path.exists(report.file_path):
        os.remove(report.file_path)

    await db.delete(report)
    await log_action(
        db, "delete_report", user_id=current_user.id,
        entity_type="sales_report", entity_id=report_id,
    )
    return {"status": "deleted"}


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
    if report.status != "processed":
        raise HTTPException(status_code=400, detail="Report is still processing")
    return await get_sales_analytics(db, report_id)


@router.get("/reports/{report_id}/managers")
async def get_report_managers(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_manager_analysis(db, report_id)


@router.get("/reports/{report_id}/clients")
async def get_report_clients(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_client_analysis(db, report_id)


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
