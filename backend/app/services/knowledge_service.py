import logging
import os
import uuid
from typing import List, Optional

import chromadb
from openai import AsyncOpenAI

from app.core.config import settings
from app.services.document_processor import extract_text, chunk_text

logger = logging.getLogger("knowledge_service")

client = AsyncOpenAI(
    api_key=settings.AITUNNEL_API_KEY,
    base_url=settings.AITUNNEL_BASE_URL,
)

chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
collection = chroma_client.get_or_create_collection(
    name="knowledge_base",
    metadata={"hnsw:space": "cosine"},
)

_use_api_embeddings: Optional[bool] = None


async def _check_embedding_support() -> bool:
    """Check if the configured API supports embeddings."""
    global _use_api_embeddings
    if _use_api_embeddings is not None:
        return _use_api_embeddings
    try:
        response = await client.embeddings.create(
            model=settings.LLM_EMBEDDING_MODEL,
            input="test",
        )
        if response.data and len(response.data[0].embedding) > 0:
            _use_api_embeddings = True
            logger.info("API embeddings available, using %s", settings.LLM_EMBEDDING_MODEL)
            return True
    except Exception as e:
        logger.info("API embeddings not available (%s), using ChromaDB built-in", e)
    _use_api_embeddings = False
    return False


async def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding from API. Returns None if API embeddings not available."""
    if not await _check_embedding_support():
        return None
    response = await client.embeddings.create(
        model=settings.LLM_EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


async def add_document_to_knowledge_base(
    file_path: str,
    document_id: int,
    category: Optional[str] = None,
) -> int:
    text = extract_text(file_path)
    chunks = chunk_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)

    for i, chunk in enumerate(chunks):
        embedding = await get_embedding(chunk)
        chunk_id = f"doc_{document_id}_chunk_{i}"
        metadata = {
            "document_id": str(document_id),
            "chunk_index": i,
            "source": os.path.basename(file_path),
        }
        if category:
            metadata["category"] = category

        upsert_kwargs = {
            "ids": [chunk_id],
            "documents": [chunk],
            "metadatas": [metadata],
        }
        if embedding is not None:
            upsert_kwargs["embeddings"] = [embedding]
        collection.upsert(**upsert_kwargs)

    return len(chunks)


async def add_knowledge_item_to_vector_db(
    knowledge_id: int,
    content: str,
    category: Optional[str] = None,
):
    embedding = await get_embedding(content)
    item_id = f"knowledge_{knowledge_id}"
    metadata = {"knowledge_id": str(knowledge_id), "source": "manual"}
    if category:
        metadata["category"] = category

    upsert_kwargs = {
        "ids": [item_id],
        "documents": [content],
        "metadatas": [metadata],
    }
    if embedding is not None:
        upsert_kwargs["embeddings"] = [embedding]
    collection.upsert(**upsert_kwargs)


async def add_correction_to_vector_db(
    correction_id: int,
    question: str,
    answer: str,
):
    combined = f"Вопрос: {question}\nОтвет: {answer}"
    embedding = await get_embedding(combined)
    item_id = f"correction_{correction_id}"
    upsert_kwargs = {
        "ids": [item_id],
        "documents": [combined],
        "metadatas": [{"correction_id": str(correction_id), "source": "correction"}],
    }
    if embedding is not None:
        upsert_kwargs["embeddings"] = [embedding]
    collection.upsert(**upsert_kwargs)


async def search_knowledge(
    query: str,
    n_results: int = 5,
    category: Optional[str] = None,
) -> List[dict]:
    embedding = await get_embedding(query)

    where_filter = None
    if category:
        where_filter = {"category": category}

    query_kwargs = {"n_results": n_results}
    if embedding is not None:
        query_kwargs["query_embeddings"] = [embedding]
    else:
        query_kwargs["query_texts"] = [query]
    if where_filter:
        query_kwargs["where"] = where_filter

    try:
        results = collection.query(**query_kwargs)
    except Exception:
        query_kwargs.pop("where", None)
        results = collection.query(**query_kwargs)

    items = []
    if results and results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 1.0
            items.append({
                "content": doc,
                "metadata": meta,
                "relevance": 1 - distance,
            })

    return items


async def generate_document_summary(text: str) -> str:
    if len(text) > 8000:
        text = text[:8000]

    response = await client.chat.completions.create(
        model=settings.LLM_CHAT_MODEL,
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
        temperature=0.3,
    )
    return response.choices[0].message.content


async def extract_knowledge_from_text(text: str) -> List[dict]:
    if len(text) > 8000:
        text = text[:8000]

    response = await client.chat.completions.create(
        model=settings.LLM_CHAT_MODEL,
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
        temperature=0.3,
    )

    result_text = response.choices[0].message.content
    knowledge_items = []

    parts = result_text.split("---")
    for part in parts:
        part = part.strip()
        if "ЗНАНИЕ:" in part:
            lines = part.split("\n", 1)
            title = lines[0].replace("ЗНАНИЕ:", "").strip()
            content = lines[1].strip() if len(lines) > 1 else title
            if title:
                knowledge_items.append({"title": title, "content": content})

    return knowledge_items


def delete_document_from_vector_db(document_id: int):
    try:
        existing = collection.get(where={"document_id": str(document_id)})
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass
