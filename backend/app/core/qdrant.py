from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

from app.core.config import settings

KNOWLEDGE_COLLECTION = "knowledge_base"
CORRECTIONS_COLLECTION = "answer_corrections"
VECTOR_SIZE = 384  # multilingual-e5-small (fastembed)

_client: Optional[QdrantClient] = None


def get_qdrant() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.QDRANT_URL)
    return _client


def init_collections():
    client = get_qdrant()

    for collection_name in [KNOWLEDGE_COLLECTION, CORRECTIONS_COLLECTION]:
        collections = [c.name for c in client.get_collections().collections]
        if collection_name in collections:
            info = client.get_collection(collection_name)
            existing_size = info.config.params.vectors.size
            if existing_size != VECTOR_SIZE:
                client.delete_collection(collection_name)
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                )
        else:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )


def upsert_vector(collection: str, point_id: str, vector: list[float], payload: dict):
    client = get_qdrant()
    client.upsert(
        collection_name=collection,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
        ],
    )


def search_vectors(
    collection: str,
    vector: list[float],
    limit: int = 10,
    score_threshold: float = 0.35,
    filters: Optional[dict] = None,
) -> list[dict]:
    client = get_qdrant()

    qdrant_filter = None
    if filters:
        conditions = []
        for key, value in filters.items():
            if isinstance(value, list):
                for v in value:
                    conditions.append(FieldCondition(key=key, match=MatchValue(value=v)))
            else:
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
        if conditions:
            qdrant_filter = Filter(should=conditions) if len(conditions) > 1 and "category" in filters else Filter(must=conditions)

    results = client.search(
        collection_name=collection,
        query_vector=vector,
        limit=limit,
        score_threshold=score_threshold,
        query_filter=qdrant_filter,
    )

    return [
        {
            "id": str(r.id),
            "score": r.score,
            "payload": r.payload,
        }
        for r in results
    ]


def delete_vectors(collection: str, point_ids: list[str]):
    client = get_qdrant()
    client.delete(
        collection_name=collection,
        points_selector=point_ids,
    )


def delete_by_filter(collection: str, key: str, value):
    client = get_qdrant()
    client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[FieldCondition(key=key, match=MatchValue(value=value))]
        ),
    )
