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
from app.models.knowledge import CorporateRule, AnswerCorrection
from app.services.knowledge_service import (
    search_knowledge,
    search_corrections,
    detect_query_intent,
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

async def generate_answer(question: str, db: AsyncSession) -> Dict[str, Any]:
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
    vector_correction = await search_corrections(question, score_threshold=0.92)
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
    context_items = await search_knowledge(
        question,
        n_results=settings.RAG_TOP_K,
        categories=intent.get("categories"),
        score_threshold=settings.RAG_SCORE_THRESHOLD,
    )
    search_time = int((time.time() - search_start) * 1000)

    trace["pipeline"]["rag_search"] = {
        "query_embedding_model": settings.LLM_EMBEDDING_MODEL,
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

    # --- STEP 5: Context Assembly ---
    context_text = ""
    sources_response = []
    total_context_chars = 0

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
    system_prompt = _build_system_prompt(rules_data)
    messages = [{"role": "system", "content": system_prompt}]

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
        confidence = sum(top_scores) / len(top_scores)
    if not context_items:
        confidence = 0.1

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


def _build_system_prompt(rules: List[Dict[str, Any]]) -> str:
    prompt = (
        'Ты — корпоративный ИИ-ассистент компании ТД "Мир Мороженого" '
        '(дистрибьютор мороженого и продуктов питания, Владимирская область).\n'
        "Ты отвечаешь ТОЛЬКО на основании предоставленного контекста из базы знаний.\n"
        "Если информации нет в предоставленном контексте, отвечай: "
        '"Информация отсутствует в базе знаний."\n'
        "Указывай источники информации, если они известны.\n"
        "Отвечай на русском языке. Будь точен и конкретен.\n"
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
