"""
Full 7-step RAG pipeline (ARCHITECTURE.md section 4.2):
  STEP 1: Query Analysis (intent + categories)
  STEP 2: Correction Check (cosine > 0.92 → return immediately)
  STEP 3: Corporate Rules Loading (priority DESC)
  STEP 4: Vector Search (Qdrant, weighted reranking)
  STEP 5: Context Assembly (rules + RAG + sales data, ≤ MAX_CONTEXT_TOKENS)
  STEP 6: LLM Generation (Groq primary + OpenAI fallback)
  STEP 7: Tracing (full JSONB trace)
"""

import time
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.llm import chat_completion
from app.core.redis import get_cached, set_cached, cache_key
from app.models.knowledge import CorporateRule, AnswerCorrection, KnowledgeItem
from app.models.analytics import SalesReport
from app.services.knowledge_service import (
    search_knowledge,
    search_corrections,
    detect_query_intent,
)
from app.services.analytics_service import (
    get_sales_analytics,
    get_product_analysis,
    _format_analytics_for_ai,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# STEP 3: Corporate Rules Loading
# ---------------------------------------------------------------------------

async def load_corporate_rules(db: AsyncSession) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(CorporateRule)
        .where(CorporateRule.is_active == True)
        .order_by(CorporateRule.priority.desc())
    )
    rules = result.scalars().all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "content": r.content,
            "rule_type": r.rule_type,
            "priority": r.priority,
            "category": r.category,
        }
        for r in rules
    ]


# ---------------------------------------------------------------------------
# STEP 2: Exact correction check (DB-level)
# ---------------------------------------------------------------------------

async def find_exact_correction(db: AsyncSession, question: str) -> Optional[Dict[str, Any]]:
    result = await db.execute(
        select(AnswerCorrection).where(AnswerCorrection.is_active == True)
    )
    corrections = result.scalars().all()

    question_lower = question.lower().strip()
    for correction in corrections:
        if correction.original_question.lower().strip() == question_lower:
            return {
                "id": correction.id,
                "answer": correction.corrected_answer,
                "correction_type": correction.correction_type,
                "priority": correction.priority,
            }

    return None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def generate_answer(question: str, db: AsyncSession, chat_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    start_time = time.time()

    trace = {
        "version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline": {},
        "sources": [],
        "rules_applied": [],
        "performance": {},
    }

    # --- Cache check ---
    question_hash = cache_key("chat", question)
    try:
        cached = await get_cached(question_hash)
        if cached:
            cached["trace"] = {"method": "cache", "cache_key": question_hash}
            cached["response_time_ms"] = int((time.time() - start_time) * 1000)
            return cached
    except Exception:
        pass

    # --- STEP 1: Query Analysis ---
    intent = detect_query_intent(question)
    trace["pipeline"]["query_analysis"] = intent

    # --- STEP 2a: Exact Correction Check (DB) ---
    exact_correction = await find_exact_correction(db, question)
    if exact_correction:
        elapsed = int((time.time() - start_time) * 1000)
        result = {
            "answer": exact_correction["answer"],
            "sources": [],
            "rules_applied": [],
            "confidence": 1.0,
            "response_time_ms": elapsed,
            "trace": {
                **trace,
                "pipeline": {
                    **trace["pipeline"],
                    "correction_check": {
                        "checked": True,
                        "method": "exact_match",
                        "correction_id": exact_correction["id"],
                        "used": True,
                    },
                },
            },
        }
        await _cache_result(question_hash, result)
        return result

    # --- STEP 2b: Vector Correction Check (Qdrant, cosine > 0.92) ---
    try:
        vector_correction = await search_corrections(question, score_threshold=0.92)
    except RuntimeError as e:
        logger.warning("Embeddings unavailable, skipping vector correction check: %s", e)
        vector_correction = None
    trace["pipeline"]["correction_check"] = {
        "checked": True,
        "best_match_score": vector_correction["score"] if vector_correction else None,
        "used": bool(vector_correction),
    }

    if vector_correction:
        elapsed = int((time.time() - start_time) * 1000)
        result = {
            "answer": vector_correction["answer"],
            "sources": [],
            "rules_applied": [],
            "confidence": 0.98,
            "response_time_ms": elapsed,
            "trace": {
                **trace,
                "pipeline": {
                    **trace["pipeline"],
                    "correction_check": {
                        "checked": True,
                        "method": "vector_match",
                        "correction_id": vector_correction.get("id"),
                        "score": vector_correction["score"],
                        "used": True,
                    },
                },
            },
        }
        await _cache_result(question_hash, result)
        return result

    # --- STEP 3: Corporate Rules Loading ---
    rules_data = await load_corporate_rules(db)
    trace["pipeline"]["rules_loaded"] = len(rules_data)
    trace["rules_applied"] = [
        {
            "rule_id": r["id"],
            "title": r["title"],
            "type": r["rule_type"],
            "priority": r["priority"],
        }
        for r in rules_data
    ]

    # --- STEP 4: Vector Search ---
    search_start = time.time()
    try:
        context_items = await search_knowledge(
            question,
            n_results=settings.RAG_TOP_K,
            categories=intent.get("categories"),
            score_threshold=settings.RAG_SCORE_THRESHOLD,
        )
    except RuntimeError as e:
        logger.warning("Embeddings unavailable, skipping RAG search: %s", e)
        context_items = []
    search_time = int((time.time() - search_start) * 1000)

    # --- STEP 4a: DB fallback if vector search returned nothing ---
    if not context_items:
        try:
            q_lower = question.lower()
            keywords = [w for w in q_lower.split() if len(w) > 3]
            ki_result = await db.execute(
                select(KnowledgeItem).where(KnowledgeItem.status == "approved").limit(500)
            )
            all_knowledge = ki_result.scalars().all()
            matched = []
            for ki in all_knowledge:
                content_lower = (ki.content or "").lower()
                title_lower = (ki.title or "").lower()
                score = sum(1 for kw in keywords if kw in content_lower or kw in title_lower)
                if score > 0:
                    matched.append((ki, score))
            matched.sort(key=lambda x: x[1], reverse=True)
            for ki, score in matched[:5]:
                context_items.append({
                    "content": ki.content,
                    "score": min(score / max(len(keywords), 1), 1.0),
                    "metadata": {
                        "type": "knowledge_item",
                        "knowledge_id": ki.id,
                        "document_id": ki.document_id,
                        "title": ki.title,
                        "source": ki.title or "База знаний",
                        "category": ki.category,
                        "priority": ki.priority,
                    },
                })
            if context_items:
                trace["pipeline"]["db_fallback"] = {"used": True, "results": len(context_items)}
        except Exception as e:
            logger.warning("DB fallback search failed: %s", e)

    trace["pipeline"]["rag_search"] = {
        "query_embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
        "results_count": len(context_items),
        "threshold": settings.RAG_SCORE_THRESHOLD,
        "categories_searched": intent.get("categories"),
        "search_time_ms": search_time,
    }

    trace["sources"] = [
        {
            "type": item["metadata"].get("type", "unknown"),
            "knowledge_id": item["metadata"].get("knowledge_id"),
            "document_id": item["metadata"].get("document_id"),
            "title": item["metadata"].get("title", item["metadata"].get("source", "")),
            "category": item["metadata"].get("category"),
            "score": round(item["score"], 4),
            "weighted_score": round(item.get("weighted_score", item["score"]), 4),
            "priority": item["metadata"].get("priority"),
            "chunk_preview": item["content"][:200],
        }
        for item in context_items
    ]

    # --- STEP 4b: Sales Data (if sales intent) ---
    sales_context = ""
    if intent.get("intent") == "sales_query":
        try:
            latest_report = await db.execute(
                select(SalesReport).order_by(SalesReport.id.desc()).limit(1)
            )
            report = latest_report.scalar_one_or_none()
            if report:
                analytics = await get_sales_analytics(db, report.id)
                if "error" not in analytics:
                    sales_context = _format_analytics_for_ai(analytics)
                    product_data = await get_product_analysis(db, report.id)
                    if product_data.get("products"):
                        sales_context += "\n\nТоп-10 продуктов по выручке:\n"
                        for p in product_data["products"][:10]:
                            sales_context += (
                                f"  {p['name']}: выручка {p['total_revenue']:,.0f}, "
                                f"маржа {p['avg_margin']:.1f}%, доля {p['revenue_share_pct']:.1f}%\n"
                            )
                    if product_data.get("sku_dependencies"):
                        sales_context += "\nЗависимость от SKU:\n"
                        for dep in product_data["sku_dependencies"]:
                            sales_context += f"  {dep['name']}: {dep['revenue_share_pct']:.1f}% выручки (риск: {dep['risk']})\n"
                    if len(sales_context) > 4000:
                        sales_context = sales_context[:4000]
                    trace["pipeline"]["sales_data"] = {"loaded": True, "report_id": report.id}
        except Exception as e:
            logger.warning("Failed to load sales data: %s", e)
            trace["pipeline"]["sales_data"] = {"loaded": False, "error": str(e)}

    # --- STEP 5: Context Assembly ---
    context_text = ""
    sources_response = []
    total_context_chars = 0

    if sales_context:
        context_text += f"\n--- АНАЛИТИКА ПРОДАЖ ---\n{sales_context}\n"
        total_context_chars += len(sales_context)
        sources_response.append({
            "document_id": None,
            "document_title": "Аналитика продаж (последний отчёт)",
            "relevance_score": 1.0,
            "chunk_preview": sales_context[:200],
        })

    for item in context_items:
        chunk = item["content"]
        if total_context_chars + len(chunk) > settings.MAX_CONTEXT_TOKENS * 4:
            break

        context_text += f"\n---\nИсточник: {item['metadata'].get('source', 'База знаний')}\n{chunk}\n"
        total_context_chars += len(chunk)

        sources_response.append({
            "document_id": item["metadata"].get("document_id"),
            "document_title": item["metadata"].get("source", item["metadata"].get("title", "База знаний")),
            "relevance_score": round(item["score"], 3),
            "chunk_preview": item["content"][:200],
        })

    trace["pipeline"]["context_tokens"] = total_context_chars // 4

    # --- STEP 6: LLM Generation ---
    system_prompt = _build_system_prompt(rules_data, has_sales_data=bool(sales_context))
    messages = [{"role": "system", "content": system_prompt}]

    if chat_history:
        for msg in chat_history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    if context_text:
        messages.append({
            "role": "user",
            "content": f"Контекст из базы знаний:\n{context_text}\n\nВопрос: {question}",
        })
    else:
        messages.append({"role": "user", "content": question})

    llm_start = time.time()
    answer = await chat_completion(messages=messages, max_tokens=2000, temperature=0.1)
    llm_time = int((time.time() - llm_start) * 1000)

    trace["pipeline"]["generation_time_ms"] = llm_time
    trace["model"] = settings.LLM_CHAT_MODEL
    trace["provider"] = settings.LLM_PROVIDER

    # --- Confidence calculation ---
    confidence = 0.0
    if context_items:
        top_scores = [item["score"] for item in context_items[:3]]
        confidence = min(sum(top_scores) / len(top_scores) + 0.3, 1.0)
    if sales_context:
        confidence = max(confidence, 0.85)
    if context_items and sales_context:
        confidence = 0.95
    if not context_items and not sales_context:
        q_lower = question.lower().strip()
        greetings = ["привет", "здравствуй", "добрый день", "добрый вечер", "доброе утро", "хай", "hello", "hi"]
        if any(g in q_lower for g in greetings):
            confidence = 0.9
        else:
            confidence = 0.4

    # --- STEP 7: Tracing ---
    elapsed = int((time.time() - start_time) * 1000)
    trace["performance"] = {
        "total_ms": elapsed,
        "search_ms": search_time,
        "llm_ms": llm_time,
    }

    rules_applied_response = [
        {
            "rule_id": r["id"],
            "title": r["title"],
            "rule_type": r["rule_type"],
            "priority": r["priority"],
        }
        for r in rules_data
    ]

    result = {
        "answer": answer,
        "sources": sources_response,
        "rules_applied": rules_applied_response,
        "confidence": round(confidence, 3),
        "response_time_ms": elapsed,
        "trace": trace,
    }

    await _cache_result(question_hash, result)
    return result


def _build_system_prompt(rules: List[Dict[str, Any]], has_sales_data: bool = False) -> str:
    prompt = (
        'Ты — внутренний корпоративный ИИ-ассистент компании ТД "Мир Мороженого" '
        '(дистрибьютор мороженого и продуктов питания, Владимирская область).\n\n'
        "ВАЖНО: Ты общаешься с СОТРУДНИКАМИ компании (руководители, менеджеры, "
        "торговые представители), а НЕ с покупателями. Ты НЕ продаёшь товары.\n\n"
        "ТВОИ ЗАДАЧИ:\n"
        "- Давать аналитику по продажам, клиентам, ТП (торговым представителям)\n"
        "- Отвечать на вопросы по внутренним документам и базе знаний\n"
        "- Давать управленческие рекомендации на основе данных\n"
        "- Помогать анализировать показатели и выявлять проблемы\n\n"
        "СТРОГИЕ ПРАВИЛА:\n"
        "1. Отвечай ТОЛЬКО на основании данных из предоставленного контекста "
        "(база знаний и аналитика продаж). НИКОГДА не придумывай информацию.\n"
        "2. Если данных недостаточно — задай уточняющий вопрос по теме. "
        "Например: «Вас интересует конкретный ТП или общая статистика?», "
        "«За какой период нужны данные?», «Уточните — маржинальность или выручка?»\n"
        "3. Если информации совсем нет — скажи: «По этой теме данных в базе пока нет. "
        "Попробуйте спросить о продажах, ТП, клиентах или продуктах.»\n"
        "4. Отвечай ИСКЛЮЧИТЕЛЬНО на русском языке. Никогда не используй иностранные слова "
        "(китайский, английский и др.) — всё на русском. Будь точен, конкретен, приводи цифры.\n"
        "5. Не упоминай источники в тексте ответа — они отображаются отдельно.\n"
        "6. ФОРМАТ ОТВЕТА: пиши ТОЛЬКО простым текстом. ЗАПРЕЩЕНО использовать "
        "markdown-разметку: никаких **, ##, |таблиц|, ```блоков кода```, "
        "списков с -, *. Используй обычный текст, нумерацию цифрами (1. 2. 3.), "
        "переносы строк для структуры. Числа форматируй с пробелами (1 000 000).\n"
        "7. Поддерживай контекст диалога — помни предыдущие вопросы и ответы.\n"
    )

    if has_sales_data:
        prompt += (
            "\nТебе доступны данные аналитики продаж из загруженных отчётов. "
            "Когда сотрудник спрашивает про продажи, выручку, прибыль, "
            "менеджеров (ТП), клиентов, маржу, ассортимент — используй данные "
            "из раздела АНАЛИТИКА ПРОДАЖ. Приводи конкретные цифры и имена.\n"
        )

    if rules:
        prompt += "\n--- КОРПОРАТИВНЫЕ ПРАВИЛА (обязательны к применению) ---\n"
        for r in rules:
            prompt += f"[{r['rule_type'].upper()}] {r['title']}: {r['content']}\n"

    return prompt


async def _cache_result(key: str, result: Dict[str, Any]):
    """Cache the answer result in Redis (TTL 5 minutes)."""
    try:
        cache_data = {
            "answer": result["answer"],
            "sources": result["sources"],
            "rules_applied": result["rules_applied"],
            "confidence": result["confidence"],
        }
        await set_cached(key, cache_data, ttl=300)
    except Exception:
        pass
