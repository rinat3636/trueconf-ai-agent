from typing import List, Dict, Any, Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.models.analytics import SalesRecord

client = AsyncOpenAI(
    api_key=settings.AITUNNEL_API_KEY,
    base_url=settings.AITUNNEL_BASE_URL,
)


async def get_sales_analytics(db: AsyncSession, report_id: int) -> Dict[str, Any]:
    result = await db.execute(
        select(SalesRecord).where(SalesRecord.report_id == report_id)
    )
    records = result.scalars().all()

    if not records:
        return {"error": "No records found"}

    manager_records = [r for r in records if r.record_level == "manager"]
    client_records = [r for r in records if r.record_level == "client"]
    product_records = [r for r in records if r.record_level == "product"]

    total_revenue = sum(r.revenue or 0 for r in manager_records)
    total_profit = sum(r.profit or 0 for r in manager_records)
    avg_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

    top_managers = sorted(manager_records, key=lambda r: r.profit or 0, reverse=True)[:10]
    weak_managers = sorted(manager_records, key=lambda r: r.margin_pct or 0)[:5]

    top_clients = sorted(client_records, key=lambda r: r.profit or 0, reverse=True)[:10]
    declining_clients = sorted(client_records, key=lambda r: r.margin_pct or 0)[:5]

    top_products = sorted(product_records, key=lambda r: r.profit or 0, reverse=True)[:10]

    return {
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "avg_margin": round(avg_margin, 2),
        "manager_count": len(manager_records),
        "client_count": len(client_records),
        "product_count": len(product_records),
        "top_managers": [
            {
                "name": m.manager_name,
                "revenue": m.revenue,
                "profit": m.profit,
                "margin": m.margin_pct,
            }
            for m in top_managers
        ],
        "weak_managers": [
            {
                "name": m.manager_name,
                "revenue": m.revenue,
                "profit": m.profit,
                "margin": m.margin_pct,
            }
            for m in weak_managers
        ],
        "top_clients": [
            {
                "name": c.client_name,
                "manager": c.manager_name,
                "revenue": c.revenue,
                "profit": c.profit,
                "margin": c.margin_pct,
            }
            for c in top_clients
        ],
        "declining_clients": [
            {
                "name": c.client_name,
                "manager": c.manager_name,
                "revenue": c.revenue,
                "profit": c.profit,
                "margin": c.margin_pct,
            }
            for c in declining_clients
        ],
        "top_products": [
            {
                "name": p.product_name,
                "client": p.client_name,
                "revenue": p.revenue,
                "profit": p.profit,
                "margin": p.margin_pct,
            }
            for p in top_products
        ],
    }


async def get_manager_analysis(db: AsyncSession, report_id: int) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.report_id == report_id,
            SalesRecord.record_level == "manager",
        )
    )
    managers = result.scalars().all()

    analysis = []
    for m in managers:
        clients_result = await db.execute(
            select(SalesRecord).where(
                SalesRecord.report_id == report_id,
                SalesRecord.manager_name == m.manager_name,
                SalesRecord.record_level == "client",
            )
        )
        clients = clients_result.scalars().all()

        products_result = await db.execute(
            select(SalesRecord).where(
                SalesRecord.report_id == report_id,
                SalesRecord.manager_name == m.manager_name,
                SalesRecord.record_level == "product",
            )
        )
        products = products_result.scalars().all()

        unique_products = set(p.product_name for p in products if p.product_name)

        analysis.append({
            "name": m.manager_name,
            "revenue": m.revenue,
            "profit": m.profit,
            "margin": m.margin_pct,
            "client_count": len(clients),
            "sku_count": len(unique_products),
            "top_clients": [
                {"name": c.client_name, "revenue": c.revenue, "profit": c.profit}
                for c in sorted(clients, key=lambda x: x.profit or 0, reverse=True)[:5]
            ],
        })

    return sorted(analysis, key=lambda x: x["profit"] or 0, reverse=True)


async def get_client_analysis(db: AsyncSession, report_id: int) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(SalesRecord).where(
            SalesRecord.report_id == report_id,
            SalesRecord.record_level == "client",
        )
    )
    clients = result.scalars().all()

    analysis = []
    for c in clients:
        products_result = await db.execute(
            select(SalesRecord).where(
                SalesRecord.report_id == report_id,
                SalesRecord.manager_name == c.manager_name,
                SalesRecord.client_name == c.client_name,
                SalesRecord.record_level == "product",
            )
        )
        products = products_result.scalars().all()

        analysis.append({
            "name": c.client_name,
            "manager": c.manager_name,
            "revenue": c.revenue,
            "profit": c.profit,
            "margin": c.margin_pct,
            "sku_count": len(products),
            "top_products": [
                {"name": p.product_name, "revenue": p.revenue, "profit": p.profit}
                for p in sorted(products, key=lambda x: x.profit or 0, reverse=True)[:5]
            ],
        })

    return sorted(analysis, key=lambda x: x["profit"] or 0, reverse=True)


async def generate_ai_recommendations(analytics: Dict[str, Any]) -> List[str]:
    analytics_text = _format_analytics_for_ai(analytics)

    response = await client.chat.completions.create(
        model=settings.LLM_ANALYSIS_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты - ИИ-аналитик продаж. На основании данных сформируй "
                    "конкретные рекомендации по улучшению продаж. "
                    "Рекомендации должны быть практичными и адресными. "
                    "Отвечай на русском языке."
                ),
            },
            {
                "role": "user",
                "content": f"Данные аналитики продаж:\n\n{analytics_text}\n\n"
                "Сформируй 5-10 конкретных рекомендаций.",
            },
        ],
        max_tokens=2000,
        temperature=0.4,
    )

    text = response.choices[0].message.content
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


async def answer_analytics_question(
    db: AsyncSession,
    question: str,
    report_id: Optional[int] = None,
) -> str:
    if report_id:
        analytics = await get_sales_analytics(db, report_id)
        analytics_text = _format_analytics_for_ai(analytics)
    else:
        analytics_text = "Данные аналитики не загружены."

    response = await client.chat.completions.create(
        model=settings.LLM_ANALYSIS_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты - ИИ-аналитик продаж. Отвечай на вопросы "
                    "на основании предоставленных данных. "
                    "Будь точен и конкретен. Отвечай на русском языке."
                ),
            },
            {
                "role": "user",
                "content": f"Данные:\n{analytics_text}\n\nВопрос: {question}",
            },
        ],
        max_tokens=2000,
        temperature=0.3,
    )

    return response.choices[0].message.content


def _format_analytics_for_ai(analytics: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"Общая выручка: {analytics.get('total_revenue', 0):,.0f} руб.")
    lines.append(f"Общая прибыль: {analytics.get('total_profit', 0):,.0f} руб.")
    lines.append(f"Средняя маржинальность: {analytics.get('avg_margin', 0):.1f}%")
    lines.append(f"Менеджеров: {analytics.get('manager_count', 0)}")
    lines.append(f"Клиентов: {analytics.get('client_count', 0)}")
    lines.append(f"SKU: {analytics.get('product_count', 0)}")

    if analytics.get("top_managers"):
        lines.append("\nТОП менеджеров по прибыли:")
        for m in analytics["top_managers"][:5]:
            lines.append(
                f"  {m['name']}: выручка {m['revenue']:,.0f}, "
                f"прибыль {m['profit']:,.0f}, маржа {m['margin']:.1f}%"
            )

    if analytics.get("weak_managers"):
        lines.append("\nМенеджеры с низкой маржинальностью:")
        for m in analytics["weak_managers"][:5]:
            lines.append(
                f"  {m['name']}: маржа {m['margin']:.1f}%, "
                f"прибыль {m['profit']:,.0f}"
            )

    if analytics.get("top_clients"):
        lines.append("\nТОП клиентов по прибыли:")
        for c in analytics["top_clients"][:5]:
            lines.append(
                f"  {c['name']} ({c['manager']}): "
                f"прибыль {c['profit']:,.0f}, маржа {c['margin']:.1f}%"
            )

    return "\n".join(lines)
