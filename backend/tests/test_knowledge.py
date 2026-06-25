"""Knowledge base: documents listing and knowledge-item CRUD.

The vector-DB indexing call is patched out so tests don't require Qdrant or the
embedding model.
"""
import pytest

from app.models.knowledge import KnowledgeItem


@pytest.fixture(autouse=True)
def _no_vector_db(monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.knowledge_service.add_knowledge_item_to_vector_db", _noop
    )


async def test_documents_list_empty(client, admin_headers):
    resp = await client.get("/api/knowledge/documents", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_knowledge_item(client, admin_headers):
    resp = await client.post(
        "/api/knowledge/items",
        headers=admin_headers,
        json={"title": "Цена пломбира", "content": "120 руб.", "category": "pricing", "priority": 70},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "Цена пломбира"
    assert body["status"] == "approved"
    assert body["priority"] == 70


async def test_create_requires_admin(client, employee_headers):
    resp = await client.post(
        "/api/knowledge/items",
        headers=employee_headers,
        json={"title": "x", "content": "y"},
    )
    assert resp.status_code == 403


async def test_list_and_filter_items(client, admin_headers, db_sessionmaker):
    async with db_sessionmaker() as s:
        s.add_all([
            KnowledgeItem(title="A", content="a", category="pricing", status="approved"),
            KnowledgeItem(title="B", content="b", category="other", status="pending_review"),
        ])
        await s.commit()

    all_items = await client.get("/api/knowledge/items", headers=admin_headers)
    assert all_items.status_code == 200
    assert {i["title"] for i in all_items.json()} == {"A", "B"}

    approved = await client.get("/api/knowledge/items?status=approved", headers=admin_headers)
    assert [i["title"] for i in approved.json()] == ["A"]


async def test_update_item_increments_version(client, admin_headers, db_sessionmaker):
    async with db_sessionmaker() as s:
        item = KnowledgeItem(title="Old", content="old body", category="other", status="approved", version=1)
        s.add(item)
        await s.commit()
        await s.refresh(item)
        item_id = item.id

    resp = await client.put(
        f"/api/knowledge/items/{item_id}",
        headers=admin_headers,
        json={"title": "New", "content": "new body"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "New"
    assert body["version"] == 2


async def test_delete_item_archives_it(client, admin_headers, db_sessionmaker):
    async with db_sessionmaker() as s:
        item = KnowledgeItem(title="Del", content="x", category="other", status="approved")
        s.add(item)
        await s.commit()
        await s.refresh(item)
        item_id = item.id

    resp = await client.delete(f"/api/knowledge/items/{item_id}", headers=admin_headers)
    assert resp.status_code == 200

    async with db_sessionmaker() as s:
        refreshed = await s.get(KnowledgeItem, item_id)
        assert refreshed.status == "archived"


async def test_update_missing_item_404(client, admin_headers):
    resp = await client.put(
        "/api/knowledge/items/999999",
        headers=admin_headers,
        json={"title": "x"},
    )
    assert resp.status_code == 404
