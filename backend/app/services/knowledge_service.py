import os
import uuid
import logging
from typing import List, Optional, Dict, Any

from app.core.config import settings
from app.core.llm import chat_completion, light_completion, get_embedding
from app.core.qdrant import (
    upsert_vector, search_vectors, delete_by_filter,
    KNOWLEDGE_COLLECTION, CORRECTIONS_COLLECTION,
)
from app.services.document_processor import (
    extract_text, smart_chunk, compute_file_checksum,
    detect_document_category,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Qdrant vector operations
# ---------------------------------------------------------------------------

async def add_document_to_knowledge_base(
    file_path: str,
    document_id: int,
    category: Optional[str] = None,
) -> int:
    text = extract_text(file_path)
    if not category:
        category = detect_document_category(os.path.basename(file_path), text)

    chunks = smart_chunk(file_path, text, category)

    for i, chunk in enumerate(chunks):
        embedding = await get_embedding(chunk)
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"doc_{document_id}_chunk_{i}"))
        payload = {
            "document_id": document_id,
            "chunk_index": i,
            "source": os.path.basename(file_path),
            "content": chunk,
            "category": category or "general",
            "type": "document_chunk",
            "status": "approved",
        }

        upsert_vector(KNOWLEDGE_COLLECTION, point_id, embedding, payload)

    return len(chunks)


async def add_knowledge_item_to_vector_db(
    knowledge_id: int,
    content: str,
    title: str = "",
    category: Optional[str] = None,
    priority: int = 50,
):
    text_for_embedding = f"{title}\n{content}" if title else content
    embedding = await get_embedding(text_for_embedding)
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"knowledge_{knowledge_id}"))
    payload = {
        "knowledge_id": knowledge_id,
        "title": title,
        "source": "knowledge_item",
        "content": content,
        "content_preview": content[:500],
        "category": category or "general",
        "priority": priority,
        "type": "knowledge_item",
        "status": "approved",
    }

    upsert_vector(KNOWLEDGE_COLLECTION, point_id, embedding, payload)


async def add_correction_to_vector_db(
    correction_id: int,
    question: str,
    answer: str,
    correction_type: str = "answer_fix",
    priority: int = 95,
):
    combined = f"Вопрос: {question}\nОтвет: {answer}"
    embedding = await get_embedding(combined)
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"correction_{correction_id}"))
    payload = {
        "correction_id": correction_id,
        "original_question": question,
        "corrected_answer": answer,
        "content": combined,
        "correction_type": correction_type,
        "priority": priority,
        "is_active": True,
        "type": "correction",
    }
    upsert_vector(CORRECTIONS_COLLECTION, point_id, embedding, payload)


# ---------------------------------------------------------------------------
# RAG Search (from ARCHITECTURE.md 4.2, steps 2-4)
# ---------------------------------------------------------------------------

async def search_corrections(
    query: str,
    score_threshold: float = 0.92,
) -> Optional[Dict[str, Any]]:
    """STEP 2: Correction Check (HIGHEST PRIORITY).
    If question matches a correction with cosine > 0.92, return it immediately."""
    embedding = await get_embedding(query)

    results = search_vectors(
        CORRECTIONS_COLLECTION,
        embedding,
        limit=1,
        score_threshold=score_threshold,
        filters={"is_active": True},
    )

    if results:
        return {
            "id": results[0]["id"],
            "answer": results[0]["payload"].get("corrected_answer", ""),
            "question": results[0]["payload"].get("original_question", ""),
            "score": results[0]["score"],
            "correction_type": results[0]["payload"].get("correction_type"),
        }
    return None


async def search_knowledge(
    query: str,
    n_results: int = 10,
    category: Optional[str] = None,
    categories: Optional[List[str]] = None,
    score_threshold: float = 0.35,
) -> List[Dict[str, Any]]:
    """STEP 4: Vector Search.
    Search knowledge_base with category filtering and priority-weighted reranking."""
    embedding = await get_embedding(query)

    filters = {"status": "approved"}
    if category:
        filters["category"] = category
    elif categories:
        filters["category"] = categories

    results = search_vectors(
        KNOWLEDGE_COLLECTION,
        embedding,
        limit=n_results * 2,
        score_threshold=score_threshold,
        filters=filters,
    )

    for r in results:
        priority = r["payload"].get("priority", 50)
        r["weighted_score"] = r["score"] * 0.6 + priority * 0.004

    results.sort(key=lambda x: x["weighted_score"], reverse=True)

    deduplicated = []
    seen_content = []
    for r in results:
        content = r["payload"].get("content", "")[:200]
        is_dup = False
        for seen in seen_content:
            if _text_similarity(content, seen) > 0.9:
                is_dup = True
                break
        if not is_dup:
            deduplicated.append(r)
            seen_content.append(content)
        if len(deduplicated) >= n_results:
            break

    return [
        {
            "content": r["payload"].get("content", ""),
            "metadata": r["payload"],
            "score": r["score"],
            "weighted_score": r["weighted_score"],
        }
        for r in deduplicated
    ]


def _text_similarity(a: str, b: str) -> float:
    """Simple Jaccard similarity for deduplication."""
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    if not a_words or not b_words:
        return 0.0
    intersection = a_words & b_words
    union = a_words | b_words
    return len(intersection) / len(union) if union else 0.0


# ---------------------------------------------------------------------------
# Query intent analysis (STEP 1)
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS = {
    "product_catalog": ["продукт", "мороженое", "sku", "артикул", "состав", "штрихкод",
                        "пломбир", "эскимо", "стаканчик", "десерт", "рожок", "брикет"],
    "logistics": ["логист", "доставк", "паллет", "коробк", "хранен", "размер", "упаковк"],
    "policy": ["пдз", "задолженност", "кредитн", "лимит", "отсрочк", "стоп-лист",
                "политик", "регламент"],
    "commercial": ["коммерч", "предложен", "условия", "бонус", "акци", "сотрудничеств"],
    "certification": ["деклар", "сертификат", "гост", "соответств"],
    "contacts": ["телефон", "почт", "email", "контакт", "номер"],
    "sales_data": ["продаж", "выручк", "прибыл", "маржа", "рентабельн", "тоннаж", "тп"],
    "product_knowledge": ["классифик", "молочн", "сливочн", "змж", "бзмж", "сорбет"],
    "sales_methodology": ["методолог", "техник продаж", "скрипт", "возражен"],
}


def detect_query_intent(question: str) -> Dict[str, Any]:
    """STEP 1: Query Analysis.
    Determine intent and relevant categories from the question."""
    q_lower = question.lower()

    detected_categories = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in q_lower:
                if cat not in detected_categories:
                    detected_categories.append(cat)
                break

    is_sales = any(kw in q_lower for kw in [
        "продаж", "выручк", "прибыл", "маржа", "тп ", "менеджер",
        "клиент", "аналитик", "отчёт", "отчет", "рейтинг", "топ",
        "продать", "sku", "ассортимент", "товар", "продукт",
        "лучший", "худший", "слабый", "сильный", "рост",
    ])

    intent = "sales_query" if is_sales else "knowledge_query"

    return {
        "intent": intent,
        "categories": detected_categories or None,
    }


# ---------------------------------------------------------------------------
# Conflict detection (from ARCHITECTURE.md 6.3)
# ---------------------------------------------------------------------------

async def find_similar_knowledge(
    content: str,
    threshold: float = 0.85,
    exclude_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Find existing knowledge items similar to new content (for conflict detection)."""
    embedding = await get_embedding(content)

    results = search_vectors(
        KNOWLEDGE_COLLECTION,
        embedding,
        limit=5,
        score_threshold=threshold,
        filters={"status": "approved"},
    )

    similar_items = []
    for r in results:
        kid = r["payload"].get("knowledge_id")
        if exclude_id and kid == exclude_id:
            continue
        similar_items.append({
            "id": r["id"],
            "knowledge_id": kid,
            "content": r["payload"].get("content", ""),
            "title": r["payload"].get("title", ""),
            "score": r["score"],
            "category": r["payload"].get("category"),
        })

    return similar_items


async def check_conflict_with_llm(
    new_content: str,
    existing_content: str,
) -> Dict[str, Any]:
    """Use LLM to compare two knowledge fragments and determine conflict type."""
    prompt = f"""Сравни два фрагмента знаний и определи тип отношения между ними.

Новый фрагмент:
{new_content[:2000]}

Существующий фрагмент:
{existing_content[:2000]}

Ответь ОДНИМ словом:
- no_conflict — информация не пересекается
- contradiction — информация противоречит друг другу
- duplicate — это одно и то же содержание
- partial_overlap — частичное пересечение, есть общая информация

Ответ:"""

    result = await light_completion(
        messages=[
            {"role": "system", "content": "Ты — система анализа конфликтов знаний. Ответь ОДНИМ словом."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=20,
        temperature=0.0,
    )

    result_lower = result.strip().lower()
    for conflict_type in ["contradiction", "duplicate", "partial_overlap", "no_conflict"]:
        if conflict_type in result_lower:
            return {"conflict_type": conflict_type, "raw_response": result.strip()}

    return {"conflict_type": "no_conflict", "raw_response": result.strip()}


async def run_conflict_detection(
    new_content: str,
    new_item_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Full conflict detection pipeline:
    1. Vector search for similar items (cosine > 0.85)
    2. LLM comparison for each similar item
    Returns list of detected conflicts."""
    similar = await find_similar_knowledge(new_content, threshold=0.85, exclude_id=new_item_id)

    conflicts = []
    for item in similar:
        llm_result = await check_conflict_with_llm(new_content, item["content"])
        if llm_result["conflict_type"] != "no_conflict":
            conflicts.append({
                "existing_item_id": item["knowledge_id"],
                "existing_title": item.get("title", ""),
                "similarity_score": item["score"],
                "conflict_type": llm_result["conflict_type"],
            })

    return conflicts


# ---------------------------------------------------------------------------
# Self-learning: knowledge extraction from documents (ARCHITECTURE.md 6.3)
# ---------------------------------------------------------------------------

async def extract_knowledge_from_text(text: str) -> List[dict]:
    """Extract structured knowledge items from document text via LLM."""
    if len(text) > 8000:
        text = text[:8000]

    result_text = await light_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — ИИ-ассистент для извлечения знаний из корпоративных документов "
                    "компании-дистрибьютора мороженого ТД \"Мир Мороженого\".\n"
                    "Извлеки из текста ключевые факты, правила, инструкции и информацию.\n"
                    "Каждый элемент знаний должен быть самостоятельным и понятным без контекста.\n"
                    "Определи категорию для каждого знания.\n\n"
                    "Верни результат в формате:\n"
                    "ЗНАНИЕ: [заголовок]\n"
                    "КАТЕГОРИЯ: [product_catalog|logistics|policy|commercial|certification|"
                    "contacts|sales_methodology|product_knowledge|general]\n"
                    "[содержание]\n---\n"
                    "Извлеки от 3 до 10 элементов знаний."
                ),
            },
            {
                "role": "user",
                "content": f"Извлеки знания из этого документа:\n\n{text}",
            },
        ],
        max_tokens=3000,
    )

    knowledge_items = []
    parts = result_text.split("---")
    for part in parts:
        part = part.strip()
        if "ЗНАНИЕ:" not in part:
            continue

        lines = part.split("\n")
        title = ""
        category = "general"
        content_lines = []

        for line in lines:
            line = line.strip()
            if line.startswith("ЗНАНИЕ:"):
                title = line.replace("ЗНАНИЕ:", "").strip()
            elif line.startswith("КАТЕГОРИЯ:"):
                cat = line.replace("КАТЕГОРИЯ:", "").strip().lower()
                if cat in CATEGORY_KEYWORDS:
                    category = cat
            elif line:
                content_lines.append(line)

        content = "\n".join(content_lines).strip()
        if title and content:
            knowledge_items.append({
                "title": title,
                "content": content,
                "category": category,
                "source_chunk": part,
            })

    return knowledge_items


async def generate_document_summary(text: str) -> str:
    """Generate a brief summary of a document via LLM."""
    if len(text) > 8000:
        text = text[:8000]

    return await light_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — ИИ-ассистент для анализа корпоративных документов "
                    "компании ТД \"Мир Мороженого\" (дистрибьютор мороженого). "
                    "Создай краткое описание документа на русском языке. "
                    "Выдели ключевые факты и информацию. "
                    "Определи, к какой области относится документ."
                ),
            },
            {
                "role": "user",
                "content": f"Проанализируй документ и создай краткое описание:\n\n{text}",
            },
        ],
        max_tokens=1000,
    )


async def analyze_unanswered_questions(
    questions: List[str],
) -> List[Dict[str, str]]:
    """Analyze questions that the bot couldn't answer (confidence < 0.3).
    Returns suggestions for what knowledge is missing."""
    if not questions:
        return []

    questions_text = "\n".join(f"- {q}" for q in questions[:20])

    result = await light_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — аналитик базы знаний. Проанализируй вопросы, на которые "
                    "ИИ-ассистент не смог ответить, и определи, какие знания отсутствуют.\n"
                    "Для каждого пробела верни:\n"
                    "ПРОБЕЛ: [описание недостающей информации]\n"
                    "РЕКОМЕНДАЦИЯ: [что нужно добавить в базу знаний]\n---"
                ),
            },
            {
                "role": "user",
                "content": f"Вопросы без ответа:\n{questions_text}",
            },
        ],
        max_tokens=2000,
    )

    gaps = []
    for part in result.split("---"):
        part = part.strip()
        gap_desc = ""
        recommendation = ""
        for line in part.split("\n"):
            line = line.strip()
            if line.startswith("ПРОБЕЛ:"):
                gap_desc = line.replace("ПРОБЕЛ:", "").strip()
            elif line.startswith("РЕКОМЕНДАЦИЯ:"):
                recommendation = line.replace("РЕКОМЕНДАЦИЯ:", "").strip()
        if gap_desc:
            gaps.append({"gap": gap_desc, "recommendation": recommendation})

    return gaps


def delete_document_from_vector_db(document_id: int):
    try:
        delete_by_filter(KNOWLEDGE_COLLECTION, "document_id", document_id)
    except Exception:
        pass
