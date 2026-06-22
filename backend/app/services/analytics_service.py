"""
Sales analytics service (ARCHITECTURE.md 7, 8.3).

Provides:
  - Overview analytics (revenue, profit, margin)
  - Manager (ТП) analysis with ratings
  - Client analysis
  - Product analysis with SKU dependency detection
  - AI recommendations via LLM
  - Free-form Q&A on sales data
"""

from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.llm import chat_completion
from app.models.analytics import SalesRecord, SalesReport


async def get_sales_analytics(db: AsyncSession, report_id: int) -> Dict[str, Any]:
    result = await db.execute(
        select(SalesRecord).where(SalesRecord.report_id == report_id)
    )
    records = result.scalars().all()

    if not records:
        return {"error": "No records found"}

    rep_records = [r for r in records if r.level == "rep"]
    client_records = [r for r in records if r.level == "client"]
    product_records = [r for r in records if r.level == "product"]

    total_revenue = sum(r.revenue or 0 for r in rep_records)
    total_profit = sum(r.gross_profit or 0 for r in rep_records)
    avg_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

    top_managers = sorted(rep_records, key=lambda r: r.gross_profit or 0, reverse=True)[:10]
    weak_managers = sorted(rep_records, key=lambda r: r.margin_pct or 0)[:5]

    top_clients = sorted(client_records, key=lambda r: r.gross_profit or 0, reverse=True)[:10]
    declining_clients = sorted(client_records, key=lambda r: r.margin_pct or 0)[:5]

    top_products = sorted(product_records, key=lambda r: r.gross_profit or 0, reverse=True)[:10]

    return {
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "avg_margin": round(avg_margin, 2),
        "manager_count": len(rep_records),
        "client_count": len(client_records),
        "product_count": len(product_records),
        "top_managers": [
            {
                "name": m.name,
                "revenue": m.revenue,
                "profit": m.gross_profit,
                "margin": m.margin_pct,
            }
            for m in top_managers
        ],
        "weak_managers": [
            {
                "name": m.name,
                "revenue": m.revenue,
                "profit": m.gross_profit,
                "margin": m.margin_pct,
            }
            for m in weak_managers
        ],
        "top_clients": [
            {
                "name": c.name,
                "revenue": c.revenue,
                "profit": c.gross_profit,
                "margin": c.margin_pct,
            }
            for c in top_clients
        ],
        "declining_clients": [
            {
                "name": c.name,
                "revenue": c.revenue,
                "profit": c.gross_profit,
                "margin": c.margin_pct,
            }
            for c in declining_clients
        ],
        "top_products": [
            {
                "name": p.name,
                "revenue": p.revenue,
                "profit": p.gross_profit,
                "margin": p.margin_pct,
            }
            for p in top_products
        ],
    }


async def get_manager_analysis(db: AsyncSession, report_id: int) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.report_id == report_id,
            SalesRecord.level == "rep",
        )
    )
    managers = result.scalars().all()

    analysis = []
    for m in managers:
        clients_result = await db.execute(
            select(SalesRecord).where(
                SalesRecord.report_id == report_id,
                SalesRecord.parent_id == m.id,
                SalesRecord.level == "client",
            )
        )
        clients = clients_result.scalars().all()

        products_result = await db.execute(
            select(SalesRecord).where(
                SalesRecord.report_id == report_id,
                SalesRecord.parent_id.in_([c.id for c in clients]) if clients else False,
                SalesRecord.level == "product",
            )
        )
        products = products_result.scalars().all() if clients else []

        unique_skus = set(p.name for p in products if p.name)
        total_client_revenue = sum(c.revenue or 0 for c in clients)
        top_client_share = 0.0
        if clients and total_client_revenue > 0:
            top_client = max(clients, key=lambda c: c.revenue or 0)
            top_client_share = round((top_client.revenue or 0) / total_client_revenue * 100, 1)

        analysis.append({
            "name": m.name,
            "revenue": m.revenue,
            "profit": m.gross_profit,
            "margin": m.margin_pct,
            "client_count": len(clients),
            "sku_count": len(unique_skus),
            "top_client_share_pct": top_client_share,
            "top_clients": [
                {"name": c.name, "revenue": c.revenue, "profit": c.gross_profit}
                for c in sorted(clients, key=lambda x: x.gross_profit or 0, reverse=True)[:5]
            ],
        })

    return sorted(analysis, key=lambda x: x["profit"] or 0, reverse=True)


async def get_client_analysis(db: AsyncSession, report_id: int) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.report_id == report_id,
            SalesRecord.level == "client",
        )
    )
    clients = result.scalars().all()

    analysis = []
    for c in clients:
        products_result = await db.execute(
            select(SalesRecord).where(
                SalesRecord.report_id == report_id,
                SalesRecord.parent_id == c.id,
                SalesRecord.level == "product",
            )
        )
        products = products_result.scalars().all()

        analysis.append({
            "name": c.name,
            "revenue": c.revenue,
            "profit": c.gross_profit,
            "margin": c.margin_pct,
            "sku_count": len(products),
            "top_products": [
                {"name": p.name, "revenue": p.revenue, "profit": p.gross_profit}
                for p in sorted(products, key=lambda x: x.gross_profit or 0, reverse=True)[:5]
            ],
        })

    return sorted(analysis, key=lambda x: x["profit"] or 0, reverse=True)


async def get_product_analysis(db: AsyncSession, report_id: int) -> Dict[str, Any]:
    """Product-level analysis with SKU dependency detection."""
    result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.report_id == report_id,
            SalesRecord.level == "product",
        )
    )
    products = result.scalars().all()

    if not products:
        return {"products": [], "sku_dependencies": []}

    product_agg: Dict[str, Dict[str, Any]] = {}
    for p in products:
        name = p.name or "Unknown"
        if name not in product_agg:
            product_agg[name] = {
                "name": name,
                "total_revenue": 0,
                "total_profit": 0,
                "total_quantity": 0,
                "total_tonnage": 0,
                "tp_count": 0,
                "client_count": 0,
                "margins": [],
            }
        agg = product_agg[name]
        agg["total_revenue"] += p.revenue or 0
        agg["total_profit"] += p.gross_profit or 0
        agg["total_quantity"] += p.quantity or 0
        agg["total_tonnage"] += p.tonnage or 0
        agg["client_count"] += 1
        if p.margin_pct is not None:
            agg["margins"].append(p.margin_pct)

    product_list = []
    total_revenue = sum(a["total_revenue"] for a in product_agg.values())

    for name, agg in product_agg.items():
        avg_margin = sum(agg["margins"]) / len(agg["margins"]) if agg["margins"] else 0
        revenue_share = (agg["total_revenue"] / total_revenue * 100) if total_revenue > 0 else 0
        product_list.append({
            "name": name,
            "total_revenue": round(agg["total_revenue"], 2),
            "total_profit": round(agg["total_profit"], 2),
            "total_quantity": round(agg["total_quantity"], 2),
            "total_tonnage": round(agg["total_tonnage"], 4),
            "avg_margin": round(avg_margin, 2),
            "client_count": agg["client_count"],
            "revenue_share_pct": round(revenue_share, 2),
        })

    product_list.sort(key=lambda x: x["total_revenue"], reverse=True)

    # SKU dependency: products with > 10% revenue share
    sku_dependencies = [
        {
            "name": p["name"],
            "revenue_share_pct": p["revenue_share_pct"],
            "risk": "high" if p["revenue_share_pct"] > 20 else "medium",
        }
        for p in product_list if p["revenue_share_pct"] > 10
    ]

    # Low-margin products
    low_margin = [
        {"name": p["name"], "avg_margin": p["avg_margin"], "total_revenue": p["total_revenue"]}
        for p in product_list if p["avg_margin"] < 15 and p["total_revenue"] > 10000
    ]

    return {
        "products": product_list[:50],
        "sku_dependencies": sku_dependencies,
        "low_margin_products": low_margin,
        "total_unique_skus": len(product_list),
    }


async def generate_ai_recommendations(analytics: Dict[str, Any]) -> List[str]:
    analytics_text = _format_analytics_for_ai(analytics)

    text = await chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    'Ты — ИИ-аналитик продаж для компании ТД "Мир Мороженого" '
                    "(дистрибьютор мороженого, Владимирская область).\n"
                    "На основании данных сформируй конкретные рекомендации по улучшению продаж.\n"
                    "Определи:\n"
                    "- Лучших и слабых ТП (торговых представителей)\n"
                    "- Низкую маржинальность и её причины\n"
                    "- Точки роста (клиенты, SKU, территории)\n"
                    "- Зависимость от отдельных SKU (если >20% выручки — это риск)\n"
                    "- Слабую клиентскую базу (мало SKU у клиента)\n"
                    "- Снижение продаж\n"
                    "Рекомендации должны быть практичными и адресными.\n"
                    "Отвечай на русском языке."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Данные аналитики продаж:\n\n{analytics_text}\n\n"
                    "Сформируй 5-10 конкретных управленческих рекомендаций."
                ),
            },
        ],
        max_tokens=2000,
        temperature=0.4,
    )

    recommendations = []
    for line in text.split("\n"):
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("-") or line.startswith("*")):
            clean = line.lstrip("0123456789.-*) ").strip()
            if clean:
                recommendations.append(clean)

    if not recommendations:
        recommendations = [text]

    return recommendations


async def generate_full_ai_analysis(db: AsyncSession, report_id: int) -> Dict[str, Any]:
    """Full AI analysis: overview + manager + product + recommendations."""
    analytics = await get_sales_analytics(db, report_id)
    if "error" in analytics:
        return analytics

    recommendations = await generate_ai_recommendations(analytics)
    product_analysis = await get_product_analysis(db, report_id)

    analytics_text = _format_analytics_for_ai(analytics)
    products_text = ""
    if product_analysis.get("sku_dependencies"):
        products_text = "\n\nЗависимость от SKU:\n"
        for dep in product_analysis["sku_dependencies"]:
            products_text += f"  {dep['name']}: {dep['revenue_share_pct']:.1f}% выручки (риск: {dep['risk']})\n"

    detailed_analysis = await chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    'Ты — управленческий аналитик компании ТД "Мир Мороженого".\n'
                    "Проведи комплексный анализ данных продаж.\n"
                    "Структурируй ответ по разделам:\n"
                    "1. Общая оценка\n"
                    "2. Анализ ТП\n"
                    "3. Анализ клиентской базы\n"
                    "4. Анализ ассортимента\n"
                    "5. Риски и проблемы\n"
                    "6. Управленческие рекомендации\n"
                    "Отвечай на русском, конкретно и с цифрами."
                ),
            },
            {
                "role": "user",
                "content": f"Данные:\n{analytics_text}{products_text}",
            },
        ],
        max_tokens=3000,
        temperature=0.3,
    )

    return {
        "overview": analytics,
        "product_analysis": product_analysis,
        "recommendations": recommendations,
        "detailed_analysis": detailed_analysis,
    }


async def answer_analytics_question(
    db: AsyncSession,
    question: str,
    report_id: Optional[int] = None,
) -> str:
    if report_id:
        analytics = await get_sales_analytics(db, report_id)
        analytics_text = _format_analytics_for_ai(analytics)

        product_analysis = await get_product_analysis(db, report_id)
        if product_analysis.get("products"):
            analytics_text += "\n\nТоп-10 продуктов по выручке:\n"
            for p in product_analysis["products"][:10]:
                analytics_text += (
                    f"  {p['name']}: выручка {p['total_revenue']:,.0f}, "
                    f"маржа {p['avg_margin']:.1f}%, доля {p['revenue_share_pct']:.1f}%\n"
                )
    else:
        analytics_text = "Данные аналитики не загружены."

    return await chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    'Ты — ИИ-аналитик продаж компании ТД "Мир Мороженого" '
                    "(дистрибьютор мороженого, Владимирская область).\n"
                    "Отвечай на вопросы на основании предоставленных данных.\n"
                    "Будь точен и конкретен. Приводи цифры. Отвечай на русском языке.\n"
                    "Если данных недостаточно — укажи это."
                ),
            },
            {
                "role": "user",
                "content": f"Данные:\n{analytics_text}\n\nВопрос: {question}",
            },
        ],
        max_tokens=2000,
    )


def _format_analytics_for_ai(analytics: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"Общая выручка: {analytics.get('total_revenue', 0):,.0f} руб.")
    lines.append(f"Общая прибыль: {analytics.get('total_profit', 0):,.0f} руб.")
    lines.append(f"Средняя маржинальность: {analytics.get('avg_margin', 0):.1f}%")
    lines.append(f"Менеджеров (ТП): {analytics.get('manager_count', 0)}")
    lines.append(f"Клиентов: {analytics.get('client_count', 0)}")
    lines.append(f"SKU: {analytics.get('product_count', 0)}")

    if analytics.get("top_managers"):
        lines.append("\nТОП менеджеров по прибыли:")
        for m in analytics["top_managers"][:5]:
            lines.append(
                f"  {m['name']}: выручка {m.get('revenue', 0):,.0f}, "
                f"прибыль {m.get('profit', 0):,.0f}, маржа {m.get('margin', 0):.1f}%"
            )

    if analytics.get("weak_managers"):
        lines.append("\nМенеджеры с низкой маржинальностью:")
        for m in analytics["weak_managers"][:5]:
            lines.append(
                f"  {m['name']}: маржа {m.get('margin', 0):.1f}%, "
                f"прибыль {m.get('profit', 0):,.0f}"
            )

    if analytics.get("top_clients"):
        lines.append("\nТОП клиентов по прибыли:")
        for c in analytics["top_clients"][:5]:
            lines.append(
                f"  {c['name']}: "
                f"прибыль {c.get('profit', 0):,.0f}, маржа {c.get('margin', 0):.1f}%"
            )

    if analytics.get("declining_clients"):
        lines.append("\nКлиенты с низкой маржинальностью:")
        for c in analytics["declining_clients"][:5]:
            lines.append(
                f"  {c['name']}: маржа {c.get('margin', 0):.1f}%, "
                f"прибыль {c.get('profit', 0):,.0f}"
            )

    return "\n".join(lines)
