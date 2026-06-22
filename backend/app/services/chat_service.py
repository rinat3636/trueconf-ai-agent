import time
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.llm import chat_completion
from app.models.knowledge import CorporateRule, AnswerCorrection
from app.services.knowledge_service import search_knowledge, search_corrections


async def get_corporate_rules(db: AsyncSession) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(CorporateRule).where(CorporateRule.is_active == True)
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
        }
        for r in rules
    ]


async def find_exact_correction(db: AsyncSession, question: str) -> Optional[str]:
    result = await db.execute(
        select(AnswerCorrection).where(AnswerCorrection.is_active == True)
    )
    corrections = result.scalars().all()

    question_lower = question.lower().strip()
    for correction in corrections:
        if correction.original_question.lower().strip() == question_lower:
            return correction.corrected_answer

    return None


async def generate_answer(question: str, db: AsyncSession) -> Dict[str, Any]:
    start_time = time.time()
    trace = {"steps": [], "sources": [], "rules": []}

    exact_correction = await find_exact_correction(db, question)
    if exact_correction:
        elapsed = int((time.time() - start_time) * 1000)
        return {
            "answer": exact_correction,
            "sources": [],
            "rules_applied": [],
            "confidence": 1.0,
            "response_time_ms": elapsed,
            "trace": {"method": "exact_correction"},
        }
    trace["steps"].append("no_exact_correction")

    vector_correction = await search_corrections(question, score_threshold=0.90)
    if vector_correction:
        elapsed = int((time.time() - start_time) * 1000)
        return {
            "answer": vector_correction.get("answer", ""),
            "sources": [],
            "rules_applied": [],
            "confidence": 0.95,
            "response_time_ms": elapsed,
            "trace": {"method": "vector_correction", "score": vector_correction.get("score")},
        }
    trace["steps"].append("no_vector_correction")

    rules_data = await get_corporate_rules(db)
    trace["rules"] = [{"id": r["id"], "title": r["title"]} for r in rules_data]

    context_items = await search_knowledge(question, n_results=10)
    trace["sources"] = [
        {
            "content_preview": item["content"][:100],
            "score": item["score"],
            "metadata": {k: v for k, v in item["metadata"].items() if k != "content"},
        }
        for item in context_items
    ]

    context_text = ""
    sources = []
    for item in context_items:
        context_text += f"\n---\n{item['content']}\n"
        meta = item["metadata"]
        sources.append({
            "document_id": meta.get("document_id"),
            "document_title": meta.get("source", "База знаний"),
            "relevance_score": round(item["score"], 3),
            "chunk_preview": item["content"][:200],
        })

    system_prompt = (
        "Ты - корпоративный ИИ-ассистент компании ТД \"Мир Мороженого\". "
        "Ты отвечаешь ТОЛЬКО на основании предоставленной базы знаний. "
        "Если информации нет в базе знаний, ответь: "
        '"Информация отсутствует в базе знаний."\n'
        "Отвечай на русском языке. Будь точен и конкретен.\n"
        "Указывай источник информации, если он известен.\n"
    )

    if rules_data:
        system_prompt += "\nКорпоративные правила (обязательны к применению):\n"
        for r in rules_data:
            system_prompt += f"- [{r['rule_type']}] {r['title']}: {r['content']}\n"

    messages = [{"role": "system", "content": system_prompt}]

    if context_text:
        messages.append({
            "role": "user",
            "content": f"Контекст из базы знаний:\n{context_text}\n\nВопрос: {question}",
        })
    else:
        messages.append({"role": "user", "content": question})

    answer = await chat_completion(messages=messages, max_tokens=2000, temperature=0.1)

    confidence = 0.0
    if context_items:
        confidence = max(item["score"] for item in context_items)
    if not context_items:
        confidence = 0.1

    elapsed = int((time.time() - start_time) * 1000)

    rules_applied = [
        {
            "rule_id": r["id"],
            "title": r["title"],
            "rule_type": r["rule_type"],
            "priority": r["priority"],
        }
        for r in rules_data
    ]

    return {
        "answer": answer,
        "sources": sources,
        "rules_applied": rules_applied,
        "confidence": round(confidence, 3),
        "response_time_ms": elapsed,
        "trace": trace,
    }
