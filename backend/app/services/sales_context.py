"""
Smart sales context for the RAG chat pipeline.

Instead of always sending the same top-5 summary, this module:
1. Extracts entity mentions (TP names, client names, product names) from the question
2. Runs targeted SQL queries for matched entities
3. Assembles a focused context that the LLM can answer from accurately
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.analytics import SalesRecord, SalesReport

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

async def load_entity_names(db: AsyncSession, report_id: int) -> Dict[str, List[Dict[str, Any]]]:
    """Load all TP/client/product names from the report for fuzzy matching."""
    result = await db.execute(
        select(SalesRecord).where(SalesRecord.report_id == report_id)
    )
    records = result.scalars().all()

    entities = {"reps": [], "clients": [], "products": []}
    for r in records:
        entry = {"id": r.id, "name": r.name, "parent_id": r.parent_id}
        if r.level == "rep":
            entities["reps"].append(entry)
        elif r.level == "client":
            entities["clients"].append(entry)
        elif r.level == "product":
            entities["products"].append(entry)

    return entities


def _normalize(text: str) -> str:
    text = text.lower().strip()
    # Remove punctuation except hyphens inside words
    text = re.sub(r'[^\w\s-]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _stem_ru(word: str) -> str:
    """Simple Russian stemmer: strip common suffixes for declension matching."""
    if len(word) <= 3:
        return word
    # Strip genitive/dative/instrumental/prepositional endings
    for suffix in ["ого", "ому", "ой", "ей", "ым", "им", "ых", "их",
                   "ую", "юю", "ая", "яя", "ое", "ее",
                   "ов", "ев", "ам", "ям", "ах", "ях",
                   "ом", "ем", "ий", "ый"]:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)]
    for suffix in ["а", "я", "у", "ю", "е", "и", "о", "ы"]:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)]
    return word


def _fuzzy_match(query: str, name: str, threshold: float = 0.6) -> bool:
    """Check if query mentions this entity name."""
    q = _normalize(query)
    n = _normalize(name)

    if not n or len(n) < 3:
        return False

    # Exact substring
    if n in q:
        return True

    # Check surname (first word of FIO)
    parts = n.split()
    if parts and len(parts[0]) >= 3:
        surname = parts[0]
        if surname in q:
            return True
        # Stem-based matching (handles Russian declensions: Кузнецова → Кузнецов → matches Кузнецовой)
        surname_stem = _stem_ru(surname)
        if len(surname_stem) >= 4:
            q_words = q.split()
            for qw in q_words:
                if len(qw) >= 4 and _stem_ru(qw) == surname_stem:
                    return True

    # Check significant words (>= 4 chars) from entity name
    significant_words = [w for w in parts if len(w) >= 4]
    if significant_words:
        q_words = q.split()
        q_stems = {_stem_ru(w) for w in q_words if len(w) >= 4}
        matched = sum(1 for w in significant_words if w in q or _stem_ru(w) in q_stems)
        if matched / len(significant_words) >= threshold:
            return True

    return False


async def extract_entities(
    question: str,
    db: AsyncSession,
    report_id: int,
) -> Dict[str, List[Dict[str, Any]]]:
    """Find which TPs, clients, or products the user is asking about."""
    all_entities = await load_entity_names(db, report_id)
    q_lower = _normalize(question)

    matched = {"reps": [], "clients": [], "products": []}

    for rep in all_entities["reps"]:
        if _fuzzy_match(q_lower, rep["name"]):
            matched["reps"].append(rep)

    # Only search clients if no TP matched, OR question explicitly mentions a specific
    # client name that is NOT the same surname as the matched TP
    if matched["reps"]:
        # If TP matched, only add client matches that are clearly different entities
        rep_stems = set()
        for rep in matched["reps"]:
            parts = rep["name"].lower().split()
            if parts:
                rep_stems.add(_stem_ru(parts[0]))

        # Only match clients whose surname root is NOT the same as matched TP
        if any(kw in q_lower for kw in ["точк", "магазин", "киоск", "ооо"]):
            for client in all_entities["clients"]:
                if _fuzzy_match(q_lower, client["name"]):
                    client_parts = client["name"].lower().split()
                    client_stem = _stem_ru(client_parts[0]) if client_parts else ""
                    if client_stem not in rep_stems:
                        matched["clients"].append(client)
    else:
        # No TP matched — search all clients freely
        for client in all_entities["clients"]:
            if _fuzzy_match(q_lower, client["name"]):
                matched["clients"].append(client)

    # Product matching
    if any(kw in q_lower for kw in [
        "продукт", "товар", "sku", "ассортимент", "мороженое",
        "пломбир", "эскимо", "рожок", "торт",
    ]):
        for product in all_entities["products"]:
            if _fuzzy_match(q_lower, product["name"]):
                matched["products"].append(product)

    return matched


# ---------------------------------------------------------------------------
# Targeted SQL queries
# ---------------------------------------------------------------------------

async def get_rep_detail(
    db: AsyncSession, report_id: int, rep_id: int
) -> Dict[str, Any]:
    """Full detail for a specific TP: all their clients with revenue/profit."""
    rep_result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.id == rep_id,
            SalesRecord.report_id == report_id,
        )
    )
    rep = rep_result.scalar_one_or_none()
    if not rep:
        return {}

    clients_result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.report_id == report_id,
            SalesRecord.parent_id == rep_id,
            SalesRecord.level == "client",
        ).order_by(SalesRecord.gross_profit.desc())
    )
    clients = clients_result.scalars().all()

    # Get product counts per client
    client_products = {}
    if clients:
        client_ids = [c.id for c in clients]
        products_result = await db.execute(
            select(
                SalesRecord.parent_id,
                func.count(SalesRecord.id).label("cnt"),
            ).where(
                SalesRecord.report_id == report_id,
                SalesRecord.parent_id.in_(client_ids),
                SalesRecord.level == "product",
            ).group_by(SalesRecord.parent_id)
        )
        for row in products_result:
            client_products[row[0]] = row[1]

    # Unique products across all clients
    all_products_result = await db.execute(
        select(SalesRecord.name).where(
            SalesRecord.report_id == report_id,
            SalesRecord.parent_id.in_([c.id for c in clients]) if clients else False,
            SalesRecord.level == "product",
        ).distinct()
    )
    unique_products = [r[0] for r in all_products_result if r[0]]

    return {
        "name": rep.name,
        "revenue": rep.revenue,
        "profit": rep.gross_profit,
        "margin": rep.margin_pct,
        "client_count": len(clients),
        "unique_sku_count": len(unique_products),
        "clients": [
            {
                "name": c.name,
                "revenue": c.revenue,
                "profit": c.gross_profit,
                "margin": c.margin_pct,
                "sku_count": client_products.get(c.id, 0),
            }
            for c in clients
        ],
        "top_products": unique_products[:20],
    }


async def get_client_detail(
    db: AsyncSession, report_id: int, client_id: int
) -> Dict[str, Any]:
    """Full detail for a specific client: their products, TP, revenue."""
    client_result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.id == client_id,
            SalesRecord.report_id == report_id,
        )
    )
    client = client_result.scalar_one_or_none()
    if not client:
        return {}

    # Find parent TP
    rep_name = ""
    if client.parent_id:
        rep_result = await db.execute(
            select(SalesRecord).where(SalesRecord.id == client.parent_id)
        )
        rep = rep_result.scalar_one_or_none()
        if rep:
            rep_name = rep.name

    # Products for this client
    products_result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.report_id == report_id,
            SalesRecord.parent_id == client_id,
            SalesRecord.level == "product",
        ).order_by(SalesRecord.gross_profit.desc())
    )
    products = products_result.scalars().all()

    return {
        "name": client.name,
        "rep_name": rep_name,
        "revenue": client.revenue,
        "profit": client.gross_profit,
        "margin": client.margin_pct,
        "products": [
            {
                "name": p.name,
                "quantity": p.quantity,
                "revenue": p.revenue,
                "profit": p.gross_profit,
                "margin": p.margin_pct,
            }
            for p in products
        ],
    }


async def get_product_across_clients(
    db: AsyncSession, report_id: int, product_name: str
) -> Dict[str, Any]:
    """Detail for a product across all clients who buy it."""
    products_result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.report_id == report_id,
            SalesRecord.level == "product",
            SalesRecord.name == product_name,
        )
    )
    products = products_result.scalars().all()

    if not products:
        return {}

    # Get client and rep names
    client_ids = list(set(p.parent_id for p in products if p.parent_id))
    client_map = {}
    rep_map = {}
    if client_ids:
        clients_result = await db.execute(
            select(SalesRecord).where(SalesRecord.id.in_(client_ids))
        )
        for c in clients_result.scalars().all():
            client_map[c.id] = c.name
            rep_map[c.id] = c.parent_id

    # Get rep names
    rep_ids = list(set(v for v in rep_map.values() if v))
    rep_name_map = {}
    if rep_ids:
        reps_result = await db.execute(
            select(SalesRecord).where(SalesRecord.id.in_(rep_ids))
        )
        for r in reps_result.scalars().all():
            rep_name_map[r.id] = r.name

    total_revenue = sum(p.revenue or 0 for p in products)
    total_profit = sum(p.gross_profit or 0 for p in products)
    total_quantity = sum(p.quantity or 0 for p in products)

    buyers = []
    for p in sorted(products, key=lambda x: x.gross_profit or 0, reverse=True):
        client_name = client_map.get(p.parent_id, "")
        rep_id = rep_map.get(p.parent_id)
        buyers.append({
            "client": client_name,
            "rep": rep_name_map.get(rep_id, ""),
            "quantity": p.quantity,
            "revenue": p.revenue,
            "profit": p.gross_profit,
        })

    return {
        "product_name": product_name,
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "total_quantity": total_quantity,
        "client_count": len(products),
        "buyers": buyers[:30],
    }


# ---------------------------------------------------------------------------
# Build smart sales context
# ---------------------------------------------------------------------------

def _safe_num(val, default=0):
    return val if val is not None else default


async def build_smart_sales_context(
    question: str,
    db: AsyncSession,
    report_id: int,
) -> Tuple[str, Dict[str, Any]]:
    """Build a targeted sales context based on entities mentioned in the question.

    Returns (context_text, trace_info).
    """
    matched = await extract_entities(question, db, report_id)
    trace = {
        "matched_reps": [r["name"] for r in matched["reps"]],
        "matched_clients": [c["name"] for c in matched["clients"]],
        "matched_products": [p["name"] for p in matched["products"]],
        "context_type": "generic",
    }

    context_parts = []

    # --- If specific TP(s) mentioned, load their full details ---
    if matched["reps"]:
        trace["context_type"] = "rep_detail"
        for rep_entry in matched["reps"][:3]:
            detail = await get_rep_detail(db, report_id, rep_entry["id"])
            if not detail:
                continue
            text = _format_rep_detail(detail)
            context_parts.append(text)

    # --- If specific client(s) mentioned ---
    if matched["clients"]:
        trace["context_type"] = "client_detail" if not matched["reps"] else "rep_and_client_detail"
        for client_entry in matched["clients"][:5]:
            detail = await get_client_detail(db, report_id, client_entry["id"])
            if not detail:
                continue
            text = _format_client_detail(detail)
            context_parts.append(text)

    # --- If specific product(s) mentioned ---
    if matched["products"]:
        if not matched["reps"] and not matched["clients"]:
            trace["context_type"] = "product_detail"
        seen_names = set()
        for prod_entry in matched["products"][:5]:
            if prod_entry["name"] in seen_names:
                continue
            seen_names.add(prod_entry["name"])
            detail = await get_product_across_clients(db, report_id, prod_entry["name"])
            if not detail:
                continue
            text = _format_product_detail(detail)
            context_parts.append(text)

    # --- If nothing specific matched, fall back to enriched overview ---
    if not context_parts:
        trace["context_type"] = "overview"
        overview = await _build_enriched_overview(db, report_id)
        context_parts.append(overview)

    full_context = "\n\n".join(context_parts)
    # Limit total context to ~6000 chars (leaves room for RAG + rules)
    if len(full_context) > 6000:
        full_context = full_context[:6000] + "\n...(данные обрезаны)"

    return full_context, trace


def _format_rep_detail(detail: Dict[str, Any]) -> str:
    lines = [
        f"ТП: {detail['name']}",
        f"Выручка: {_safe_num(detail.get('revenue')):,.0f} руб.",
        f"Прибыль: {_safe_num(detail.get('profit')):,.0f} руб.",
        f"Маржа: {_safe_num(detail.get('margin')):.1f}%",
        f"Клиентов: {detail.get('client_count', 0)}",
        f"Уникальных SKU: {detail.get('unique_sku_count', 0)}",
    ]

    clients = detail.get("clients", [])
    if clients:
        lines.append(f"\nВсе клиенты {detail['name']} ({len(clients)} шт.):")
        for c in clients:
            sku_info = f", SKU: {c['sku_count']}" if c.get("sku_count") else ""
            lines.append(
                f"  {c['name']}: выручка {_safe_num(c.get('revenue')):,.0f}, "
                f"прибыль {_safe_num(c.get('profit')):,.0f}, "
                f"маржа {_safe_num(c.get('margin')):.1f}%{sku_info}"
            )

    products = detail.get("top_products", [])
    if products:
        lines.append(f"\nТоп продуктов {detail['name']}:")
        for p in products:
            lines.append(f"  {p}")

    return "\n".join(lines)


def _format_client_detail(detail: Dict[str, Any]) -> str:
    lines = [
        f"Клиент: {detail['name']}",
        f"ТП: {detail.get('rep_name', 'N/A')}",
        f"Выручка: {_safe_num(detail.get('revenue')):,.0f} руб.",
        f"Прибыль: {_safe_num(detail.get('profit')):,.0f} руб.",
        f"Маржа: {_safe_num(detail.get('margin')):.1f}%",
    ]

    products = detail.get("products", [])
    if products:
        lines.append(f"\nАссортимент ({len(products)} позиций):")
        for p in products:
            lines.append(
                f"  {p['name']}: кол-во {_safe_num(p.get('quantity')):.0f}, "
                f"выручка {_safe_num(p.get('revenue')):,.0f}, "
                f"маржа {_safe_num(p.get('margin')):.1f}%"
            )

    return "\n".join(lines)


def _format_product_detail(detail: Dict[str, Any]) -> str:
    lines = [
        f"Продукт: {detail['product_name']}",
        f"Общая выручка: {_safe_num(detail.get('total_revenue')):,.0f} руб.",
        f"Общая прибыль: {_safe_num(detail.get('total_profit')):,.0f} руб.",
        f"Общее количество: {_safe_num(detail.get('total_quantity')):.0f}",
        f"Клиентов покупают: {detail.get('client_count', 0)}",
    ]

    buyers = detail.get("buyers", [])
    if buyers:
        lines.append(f"\nПокупатели ({len(buyers)} шт.):")
        for b in buyers:
            lines.append(
                f"  {b['client']} (ТП: {b['rep']}): "
                f"кол-во {_safe_num(b.get('quantity')):.0f}, "
                f"выручка {_safe_num(b.get('revenue')):,.0f}"
            )

    return "\n".join(lines)


async def _build_enriched_overview(db: AsyncSession, report_id: int) -> str:
    """Enriched overview that includes ALL TPs with their client counts."""
    result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.report_id == report_id,
            SalesRecord.level == "rep",
        ).order_by(SalesRecord.gross_profit.desc())
    )
    reps = result.scalars().all()

    if not reps:
        return "Данные аналитики продаж отсутствуют."

    total_revenue = sum(r.revenue or 0 for r in reps)
    total_profit = sum(r.gross_profit or 0 for r in reps)
    avg_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

    # Count clients per rep
    rep_ids = [r.id for r in reps]
    clients_count_result = await db.execute(
        select(
            SalesRecord.parent_id,
            func.count(SalesRecord.id).label("cnt"),
        ).where(
            SalesRecord.report_id == report_id,
            SalesRecord.parent_id.in_(rep_ids),
            SalesRecord.level == "client",
        ).group_by(SalesRecord.parent_id)
    )
    clients_per_rep = {row[0]: row[1] for row in clients_count_result}

    # Count total unique products
    total_products_result = await db.execute(
        select(func.count(func.distinct(SalesRecord.name))).where(
            SalesRecord.report_id == report_id,
            SalesRecord.level == "product",
        )
    )
    total_products = total_products_result.scalar() or 0

    total_clients_result = await db.execute(
        select(func.count(SalesRecord.id)).where(
            SalesRecord.report_id == report_id,
            SalesRecord.level == "client",
        )
    )
    total_clients = total_clients_result.scalar() or 0

    lines = [
        f"Общая выручка: {total_revenue:,.0f} руб.",
        f"Общая прибыль: {total_profit:,.0f} руб.",
        f"Средняя маржа: {avg_margin:.1f}%",
        f"ТП: {len(reps)}, Клиентов: {total_clients}, Уникальных SKU: {total_products}",
        "",
        "Все торговые представители:",
    ]

    for r in reps:
        cc = clients_per_rep.get(r.id, 0)
        lines.append(
            f"  {r.name}: выручка {_safe_num(r.revenue):,.0f}, "
            f"прибыль {_safe_num(r.gross_profit):,.0f}, "
            f"маржа {_safe_num(r.margin_pct):.1f}%, клиентов: {cc}"
        )

    return "\n".join(lines)
