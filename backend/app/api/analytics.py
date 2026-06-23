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
    get_product_analysis,
    generate_ai_recommendations,
    generate_full_ai_analysis,
    answer_analytics_question,
    compare_reports,
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

            # Insert with parent_id tracking for hierarchy
            current_rep_id = None
            current_client_id = None

            level_map = {"manager": "rep", "client": "client", "product": "product"}

            for record in records:
                parent_id = None
                raw_level = record.get("record_level", "product")
                level = level_map.get(raw_level, raw_level)

                if level == "client":
                    parent_id = current_rep_id
                elif level == "product":
                    parent_id = current_client_id

                if level == "rep":
                    name = record.get("manager_name") or record.get("name", "")
                elif level == "client":
                    name = record.get("client_name") or record.get("name", "")
                elif level == "product":
                    name = record.get("product_name") or record.get("name", "")
                else:
                    name = record.get("name", "")

                sales_record = SalesRecord(
                    report_id=report_id,
                    level=level,
                    parent_id=parent_id,
                    name=name,
                    quantity=record.get("quantity"),
                    tonnage=record.get("tonnage"),
                    revenue=record.get("revenue"),
                    gross_profit=record.get("gross_profit") or record.get("profit"),
                    margin_pct=record.get("margin_pct"),
                )
                db.add(sales_record)
                await db.flush()

                if level == "rep":
                    current_rep_id = sales_record.id
                    current_client_id = None
                elif level == "client":
                    current_client_id = sales_record.id

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

            # Index sales profiles in Qdrant for RAG search
            try:
                from app.services.sales_indexer import index_sales_profiles
                indexed = await index_sales_profiles(db, report_id)
                import logging
                logging.getLogger(__name__).info(
                    "Indexed %d sales profiles for report %d", indexed, report_id
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    "Failed to index sales profiles for report %d: %s", report_id, e
                )

            # Auto-generate training pairs and add as corrections
            try:
                from app.services.sales_indexer import generate_training_pairs
                from app.services.knowledge_service import add_correction_to_vector_db
                from app.models.knowledge import AnswerCorrection

                pairs = await generate_training_pairs(db, report_id)
                for pair in pairs:
                    existing = await db.execute(
                        select(AnswerCorrection).where(
                            AnswerCorrection.original_question == pair["question"],
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue
                    correction = AnswerCorrection(
                        original_question=pair["question"],
                        corrected_answer=pair["answer"],
                        correction_type="auto_sales",
                        is_active=True,
                        priority=80,
                    )
                    db.add(correction)
                    await db.flush()
                    await db.refresh(correction)
                    try:
                        await add_correction_to_vector_db(
                            correction.id, pair["question"], pair["answer"],
                            correction_type="auto_sales", priority=80,
                        )
                    except Exception:
                        pass
                await db.commit()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    "Failed to generate training pairs for report %d: %s", report_id, e
                )

            # Invalidate chat cache
            try:
                from app.core.redis import delete_cached
                await delete_cached("chat:*")
            except Exception:
                pass
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

    from sqlalchemy import update, delete as sql_delete
    await db.execute(
        update(SalesRecord)
        .where(SalesRecord.report_id == report_id)
        .values(parent_id=None)
    )
    await db.execute(
        sql_delete(SalesRecord).where(SalesRecord.report_id == report_id)
    )
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


@router.get("/reports/{report_id}/products")
async def get_report_products(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_product_analysis(db, report_id)


@router.get("/reports/{report_id}/full-analysis")
async def get_full_ai_analysis(
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
    return await generate_full_ai_analysis(db, report_id)


@router.post("/ask", response_model=AnalysisQuestionResponse)
async def ask_analytics_question(
    request: AnalysisQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    answer = await answer_analytics_question(db, request.question, request.report_id)
    return AnalysisQuestionResponse(answer=answer)


@router.get("/reports/compare/{report_id_current}/{report_id_previous}")
async def compare_two_reports(
    report_id_current: int,
    report_id_previous: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compare two reports: changes in revenue, profit, clients, products per TP."""
    for rid in (report_id_current, report_id_previous):
        result = await db.execute(select(SalesReport).where(SalesReport.id == rid))
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(status_code=404, detail=f"Report {rid} not found")
        if report.status != "processed":
            raise HTTPException(status_code=400, detail=f"Report {rid} is still processing")

    return await compare_reports(db, report_id_current, report_id_previous)


@router.post("/reports/{report_id}/reindex")
async def reindex_sales_profiles(
    report_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Re-index sales profiles in Qdrant and regenerate training pairs."""
    result = await db.execute(select(SalesReport).where(SalesReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != "processed":
        raise HTTPException(status_code=400, detail="Report is still processing")

    async def _reindex(rid: int):
        from app.core.database import async_session as _session
        from app.services.sales_indexer import index_sales_profiles, generate_training_pairs
        from app.services.knowledge_service import add_correction_to_vector_db
        from app.models.knowledge import AnswerCorrection
        import logging
        _logger = logging.getLogger(__name__)
        async with _session() as _db:
            try:
                indexed = await index_sales_profiles(_db, rid)
                _logger.info("Re-indexed %d sales profiles for report %d", indexed, rid)

                pairs = await generate_training_pairs(_db, rid)
                for pair in pairs:
                    existing = await _db.execute(
                        select(AnswerCorrection).where(
                            AnswerCorrection.original_question == pair["question"],
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue
                    correction = AnswerCorrection(
                        original_question=pair["question"],
                        corrected_answer=pair["answer"],
                        correction_type="auto_sales",
                        is_active=True,
                        priority=80,
                    )
                    _db.add(correction)
                    await _db.flush()
                    await _db.refresh(correction)
                    try:
                        await add_correction_to_vector_db(
                            correction.id, pair["question"], pair["answer"],
                            correction_type="auto_sales", priority=80,
                        )
                    except Exception:
                        pass
                await _db.commit()
            except Exception as e:
                _logger.error("Reindex failed for report %d: %s", rid, e)

    background_tasks.add_task(_reindex, report_id)
    return {"status": "reindexing", "report_id": report_id}
