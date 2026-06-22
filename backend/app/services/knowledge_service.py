import os
import uuid
from typing import List, Optional

from app.core.llm import chat_completion, get_embedding
from app.core.qdrant import (
    upsert_vector, search_vectors, delete_by_filter,
    KNOWLEDGE_COLLECTION, CORRECTIONS_COLLECTION,
)
from app.services.document_processor import extract_text, chunk_text
from app.core.config import settings


async def add_document_to_knowledge_base(
    file_path: str,
    document_id: int,
    category: Optional[str] = None,
) -> int:
    text = extract_text(file_path)
    chunks = chunk_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)

    for i, chunk in enumerate(chunks):
        embedding = await get_embedding(chunk)
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"doc_{document_id}_chunk_{i}"))
        payload = {
            "document_id": document_id,
            "chunk_index": i,
            "source": os.path.basename(file_path),
            "content": chunk,
            "type": "document_chunk",
        }
        if category:
            payload["category"] = category

        upsert_vector(KNOWLEDGE_COLLECTION, point_id, embedding, payload)

    return len(chunks)


async def add_knowledge_item_to_vector_db(
    knowledge_id: int,
    content: str,
    category: Optional[str] = None,
):
    embedding = await get_embedding(content)
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"knowledge_{knowledge_id}"))
    payload = {
        "knowledge_id": knowledge_id,
        "source": "manual",
        "content": content,
        "type": "knowledge_item",
    }
    if category:
        payload["category"] = category

    upsert_vector(KNOWLEDGE_COLLECTION, point_id, embedding, payload)


async def add_correction_to_vector_db(
    correction_id: int,
    question: str,
    answer: str,
):
    combined = f"Вопрос: {question}\nОтвет: {answer}"
    embedding = await get_embedding(combined)
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"correction_{correction_id}"))
    payload = {
        "correction_id": correction_id,
        "question": question,
        "answer": answer,
        "content": combined,
        "type": "correction",
    }
    upsert_vector(CORRECTIONS_COLLECTION, point_id, embedding, payload)


async def search_knowledge(
    query: str,
    n_results: int = 10,
    category: Optional[str] = None,
    score_threshold: float = 0.35,
) -> List[dict]:
    embedding = await get_embedding(query)

    filters = {}
    if category:
        filters["category"] = category

    results = search_vectors(
        KNOWLEDGE_COLLECTION,
        embedding,
        limit=n_results,
        score_threshold=score_threshold,
        filters=filters if filters else None,
    )

    return [
        {
            "content": r["payload"].get("content", ""),
            "metadata": r["payload"],
            "score": r["score"],
        }
        for r in results
    ]


async def search_corrections(
    query: str,
    score_threshold: float = 0.85,
) -> Optional[dict]:
    embedding = await get_embedding(query)

    results = search_vectors(
        CORRECTIONS_COLLECTION,
        embedding,
        limit=1,
        score_threshold=score_threshold,
    )

    if results:
        return results[0]["payload"]
    return None


def delete_document_from_vector_db(document_id: int):
    try:
        delete_by_filter(KNOWLEDGE_COLLECTION, "document_id", document_id)
    except Exception:
        pass


async def generate_document_summary(text: str) -> str:
    if len(text) > 8000:
        text = text[:8000]

    return await chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты - ИИ-ассистент для анализа корпоративных документов. "
                    "Создай краткое описание документа на русском языке. "
                    "Выдели ключевые факты и информацию."
                ),
            },
            {
                "role": "user",
                "content": f"Проанализируй документ и создай краткое описание:\n\n{text}",
            },
        ],
        max_tokens=1000,
    )


async def extract_knowledge_from_text(text: str) -> List[dict]:
    if len(text) > 8000:
        text = text[:8000]

    result_text = await chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты - ИИ-ассистент для извлечения знаний из корпоративных документов. "
                    "Извлеки из текста ключевые факты, правила, инструкции и информацию. "
                    "Каждый элемент знаний должен быть самостоятельным и понятным. "
                    "Верни результат в формате:\n"
                    "ЗНАНИЕ: [заголовок]\n[содержание]\n---\n"
                    "Извлеки от 3 до 10 элементов знаний."
                ),
            },
            {
                "role": "user",
                "content": f"Извлеки знания из этого документа:\n\n{text}",
            },
        ],
        max_tokens=2000,
    )

    knowledge_items = []
    parts = result_text.split("---")
    for part in parts:
        part = part.strip()
        if "ЗНАНИЕ:" in part:
            lines = part.split("\n", 1)
            title = lines[0].replace("ЗНАНИЕ:", "").strip()
            content = lines[1].strip() if len(lines) > 1 else title
            if title:
                knowledge_items.append({
                    "title": title,
                    "content": content,
                    "source_chunk": part,
                })

    return knowledge_items
