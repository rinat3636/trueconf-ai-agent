"""
Index sales data profiles into Qdrant for RAG search.

After parsing an Excel report, generates text profiles for:
- Each TP (all clients, top products, key metrics)
- Top clients (products, TP, metrics)
- Top products (who buys, volumes)

Also auto-generates training Q&A pairs from the data.
"""

import uuid
import logging
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.llm import get_embedding
from app.core.qdrant import upsert_vector, delete_by_filter, KNOWLEDGE_COLLECTION
from app.models.analytics import SalesRecord, SalesReport

logger = logging.getLogger(__name__)


def _safe_num(val, default=0):
    return val if val is not None else default


async def index_sales_profiles(db: AsyncSession, report_id: int) -> int:
    """Generate and index text profiles for all TPs, top clients, top products.
    Returns number of vectors indexed."""
    # First, remove old sales profiles for this report
    try:
        delete_by_filter(KNOWLEDGE_COLLECTION, "sales_report_id", report_id)
    except Exception:
        pass

    count = 0

    # --- TP profiles ---
    reps_result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.report_id == report_id,
            SalesRecord.level == "rep",
        ).order_by(SalesRecord.gross_profit.desc())
    )
    reps = reps_result.scalars().all()

    for rep in reps:
        clients_result = await db.execute(
            select(SalesRecord).where(
                SalesRecord.report_id == report_id,
                SalesRecord.parent_id == rep.id,
                SalesRecord.level == "client",
            ).order_by(SalesRecord.gross_profit.desc())
        )
        clients = clients_result.scalars().all()
        client_names = [c.name for c in clients[:30]]

        # Get unique products for this TP
        if clients:
            client_ids = [c.id for c in clients]
            products_result = await db.execute(
                select(SalesRecord.name).where(
                    SalesRecord.report_id == report_id,
                    SalesRecord.parent_id.in_(client_ids),
                    SalesRecord.level == "product",
                ).distinct().limit(30)
            )
            product_names = [r[0] for r in products_result if r[0]]
        else:
            product_names = []

        profile_text = _build_rep_profile(rep, clients, client_names, product_names)
        embedding = await get_embedding(profile_text)

        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"sales_rep_{report_id}_{rep.id}"))
        payload = {
            "sales_report_id": report_id,
            "sales_record_id": rep.id,
            "content": profile_text,
            "title": f"ТП {rep.name}",
            "source": "sales_profile",
            "category": "sales_data",
            "type": "sales_profile",
            "entity_type": "rep",
            "entity_name": rep.name,
            "priority": 60,
            "status": "approved",
        }
        upsert_vector(KNOWLEDGE_COLLECTION, point_id, embedding, payload)
        count += 1

    # --- Top client profiles (top 50 by profit) ---
    clients_result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.report_id == report_id,
            SalesRecord.level == "client",
        ).order_by(SalesRecord.gross_profit.desc()).limit(50)
    )
    top_clients = clients_result.scalars().all()

    # Build rep name map
    rep_name_map = {r.id: r.name for r in reps}

    for client in top_clients:
        products_result = await db.execute(
            select(SalesRecord).where(
                SalesRecord.report_id == report_id,
                SalesRecord.parent_id == client.id,
                SalesRecord.level == "product",
            ).order_by(SalesRecord.gross_profit.desc())
        )
        products = products_result.scalars().all()
        rep_name = rep_name_map.get(client.parent_id, "")

        profile_text = _build_client_profile(client, rep_name, products)
        embedding = await get_embedding(profile_text)

        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"sales_client_{report_id}_{client.id}"))
        payload = {
            "sales_report_id": report_id,
            "sales_record_id": client.id,
            "content": profile_text,
            "title": f"Клиент {client.name}",
            "source": "sales_profile",
            "category": "sales_data",
            "type": "sales_profile",
            "entity_type": "client",
            "entity_name": client.name,
            "rep_name": rep_name,
            "priority": 55,
            "status": "approved",
        }
        upsert_vector(KNOWLEDGE_COLLECTION, point_id, embedding, payload)
        count += 1

    # --- Top product profiles (top 30 by aggregated revenue) ---
    product_agg_result = await db.execute(
        select(
            SalesRecord.name,
            func.sum(SalesRecord.revenue).label("total_rev"),
            func.sum(SalesRecord.gross_profit).label("total_profit"),
            func.sum(SalesRecord.quantity).label("total_qty"),
            func.count(SalesRecord.id).label("client_count"),
        ).where(
            SalesRecord.report_id == report_id,
            SalesRecord.level == "product",
        ).group_by(SalesRecord.name).order_by(
            func.sum(SalesRecord.revenue).desc()
        ).limit(30)
    )
    top_products = product_agg_result.all()

    total_rev_result = await db.execute(
        select(func.sum(SalesRecord.revenue)).where(
            SalesRecord.report_id == report_id,
            SalesRecord.level == "rep",
        )
    )
    total_revenue = total_rev_result.scalar() or 1

    for prod in top_products:
        product_name, rev, profit, qty, cc = prod
        if not product_name:
            continue

        share = (rev / total_revenue * 100) if total_revenue > 0 else 0
        profile_text = (
            f"Продукт: {product_name}\n"
            f"Общая выручка: {_safe_num(rev):,.0f} руб. ({share:.1f}% от общей)\n"
            f"Общая прибыль: {_safe_num(profit):,.0f} руб.\n"
            f"Общее количество: {_safe_num(qty):.0f}\n"
            f"Клиентов покупают: {cc}\n"
        )

        embedding = await get_embedding(profile_text)
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"sales_product_{report_id}_{product_name}"))
        payload = {
            "sales_report_id": report_id,
            "content": profile_text,
            "title": f"Продукт {product_name}",
            "source": "sales_profile",
            "category": "sales_data",
            "type": "sales_profile",
            "entity_type": "product",
            "entity_name": product_name,
            "priority": 50,
            "status": "approved",
        }
        upsert_vector(KNOWLEDGE_COLLECTION, point_id, embedding, payload)
        count += 1

    logger.info(
        "Indexed %d sales profiles for report %d (%d reps, %d clients, %d products)",
        count, report_id, len(reps), len(top_clients), len(top_products),
    )
    return count


def _build_rep_profile(rep, clients, client_names, product_names) -> str:
    lines = [
        f"Торговый представитель: {rep.name}",
        f"Выручка: {_safe_num(rep.revenue):,.0f} руб.",
        f"Прибыль: {_safe_num(rep.gross_profit):,.0f} руб.",
        f"Маржа: {_safe_num(rep.margin_pct):.1f}%",
        f"Количество клиентов: {len(clients)}",
        f"Количество уникальных SKU: {len(product_names)}",
    ]

    if client_names:
        lines.append(f"Клиенты: {', '.join(client_names)}")

    if clients:
        lines.append("Топ клиентов по прибыли:")
        for c in clients[:10]:
            lines.append(
                f"  {c.name}: выручка {_safe_num(c.revenue):,.0f}, "
                f"прибыль {_safe_num(c.gross_profit):,.0f}, "
                f"маржа {_safe_num(c.margin_pct):.1f}%"
            )

    if product_names:
        lines.append(f"Основные продукты: {', '.join(product_names[:15])}")

    return "\n".join(lines)


def _build_client_profile(client, rep_name, products) -> str:
    lines = [
        f"Клиент: {client.name}",
        f"Торговый представитель: {rep_name}",
        f"Выручка: {_safe_num(client.revenue):,.0f} руб.",
        f"Прибыль: {_safe_num(client.gross_profit):,.0f} руб.",
        f"Маржа: {_safe_num(client.margin_pct):.1f}%",
        f"Количество позиций (SKU): {len(products)}",
    ]

    if products:
        lines.append("Ассортимент:")
        for p in products:
            lines.append(
                f"  {p.name}: кол-во {_safe_num(p.quantity):.0f}, "
                f"выручка {_safe_num(p.revenue):,.0f}"
            )

    return "\n".join(lines)


async def generate_training_pairs(db: AsyncSession, report_id: int) -> List[Dict[str, str]]:
    """Auto-generate Q&A training pairs from sales data.
    Returns list of {question, answer} dicts."""
    pairs = []

    # Get all reps
    reps_result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.report_id == report_id,
            SalesRecord.level == "rep",
        ).order_by(SalesRecord.gross_profit.desc())
    )
    reps = reps_result.scalars().all()

    if not reps:
        return pairs

    # Overview pair
    total_rev = sum(_safe_num(r.revenue) for r in reps)
    total_profit = sum(_safe_num(r.gross_profit) for r in reps)
    rep_names = [r.name for r in reps]

    pairs.append({
        "question": "Сколько торговых представителей работает в компании?",
        "answer": f"В компании работают {len(reps)} торговых представителей: {', '.join(rep_names)}.",
    })

    pairs.append({
        "question": "Какая общая выручка компании?",
        "answer": f"Общая выручка составляет {total_rev:,.0f} руб., общая прибыль {total_profit:,.0f} руб.",
    })

    # Per-TP pairs
    for rep in reps:
        # Client count
        cc_result = await db.execute(
            select(func.count(SalesRecord.id)).where(
                SalesRecord.report_id == report_id,
                SalesRecord.parent_id == rep.id,
                SalesRecord.level == "client",
            )
        )
        client_count = cc_result.scalar() or 0

        surname = rep.name.split()[0] if rep.name else rep.name

        pairs.append({
            "question": f"Сколько клиентов у {rep.name}?",
            "answer": (
                f"У {rep.name} {client_count} клиентов. "
                f"Выручка: {_safe_num(rep.revenue):,.0f} руб., "
                f"прибыль: {_safe_num(rep.gross_profit):,.0f} руб., "
                f"маржа: {_safe_num(rep.margin_pct):.1f}%."
            ),
        })

        pairs.append({
            "question": f"Какая выручка у {surname}?",
            "answer": (
                f"Выручка {rep.name}: {_safe_num(rep.revenue):,.0f} руб., "
                f"прибыль: {_safe_num(rep.gross_profit):,.0f} руб., "
                f"маржинальность: {_safe_num(rep.margin_pct):.1f}%."
            ),
        })

    # Best/worst TP
    best_tp = reps[0]
    worst_tp = min(reps, key=lambda r: _safe_num(r.margin_pct))
    pairs.append({
        "question": "Кто лучший торговый представитель по прибыли?",
        "answer": (
            f"Лучший ТП по прибыли: {best_tp.name} "
            f"(прибыль {_safe_num(best_tp.gross_profit):,.0f} руб., "
            f"маржа {_safe_num(best_tp.margin_pct):.1f}%)."
        ),
    })
    pairs.append({
        "question": "У кого самая низкая маржинальность?",
        "answer": (
            f"Самая низкая маржинальность у {worst_tp.name}: "
            f"{_safe_num(worst_tp.margin_pct):.1f}% "
            f"(выручка {_safe_num(worst_tp.revenue):,.0f} руб.)."
        ),
    })

    return pairs
