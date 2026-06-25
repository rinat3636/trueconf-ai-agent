"""Knowledge conflicts — the feature added in PR #28.

Verifies the conflict cards are populated with titles and content (including the
read-time fallback for legacy rows whose preview columns are NULL), and that the
quick-resolve actions change item/conflict state.
"""
import pytest
import pytest_asyncio

from app.models.knowledge import KnowledgeConflict, KnowledgeItem


async def _seed_items(maker, *, new_content, existing_content):
    async with maker() as s:
        existing = KnowledgeItem(
            title="Существующее знание о ценах",
            content=existing_content,
            category="other",
            status="approved",
        )
        new = KnowledgeItem(
            title="Новое знание о ценах",
            content=new_content,
            category="other",
            status="pending_review",
        )
        s.add_all([existing, new])
        await s.commit()
        await s.refresh(existing)
        await s.refresh(new)
        return new.id, existing.id


async def _seed_conflict(maker, new_id, existing_id, **kwargs):
    async with maker() as s:
        conflict = KnowledgeConflict(
            new_item_id=new_id,
            existing_item_id=existing_id,
            conflict_type=kwargs.get("conflict_type", "partial_overlap"),
            similarity_score=kwargs.get("similarity_score", 0.91),
            new_content_preview=kwargs.get("new_content_preview"),
            existing_content_preview=kwargs.get("existing_content_preview"),
            resolution="pending",
        )
        s.add(conflict)
        await s.commit()
        await s.refresh(conflict)
        return conflict.id


async def test_legacy_conflict_falls_back_to_item_content(client, admin_headers, db_sessionmaker):
    """Old rows have NULL previews; the API must backfill from item content + titles."""
    new_id, existing_id = await _seed_items(
        db_sessionmaker,
        new_content="Новая цена пломбира 120 рублей за единицу.",
        existing_content="Старая цена пломбира 95 рублей за единицу.",
    )
    cid = await _seed_conflict(
        db_sessionmaker, new_id, existing_id,
        new_content_preview=None, existing_content_preview=None,
    )

    resp = await client.get("/api/knowledge/conflicts?resolution=pending", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    conflicts = resp.json()
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c["id"] == cid
    assert c["conflict_type"] == "partial_overlap"
    # Titles enriched from KnowledgeItem
    assert c["new_title"] == "Новое знание о ценах"
    assert c["existing_title"] == "Существующее знание о ценах"
    # Previews backfilled from item content (this is exactly what was broken before)
    assert c["new_content_preview"] == "Новая цена пломбира 120 рублей за единицу."
    assert c["existing_content_preview"] == "Старая цена пломбира 95 рублей за единицу."


async def test_stored_preview_is_returned_verbatim(client, admin_headers, db_sessionmaker):
    new_id, existing_id = await _seed_items(
        db_sessionmaker,
        new_content="full new body",
        existing_content="full existing body",
    )
    await _seed_conflict(
        db_sessionmaker, new_id, existing_id,
        conflict_type="contradiction",
        new_content_preview="STORED new preview",
        existing_content_preview="STORED existing preview",
    )

    resp = await client.get("/api/knowledge/conflicts", headers=admin_headers)
    c = resp.json()[0]
    assert c["conflict_type"] == "contradiction"
    assert c["new_content_preview"] == "STORED new preview"
    assert c["existing_content_preview"] == "STORED existing preview"


async def test_get_single_conflict_and_404(client, admin_headers, db_sessionmaker):
    new_id, existing_id = await _seed_items(
        db_sessionmaker, new_content="n", existing_content="e",
    )
    cid = await _seed_conflict(db_sessionmaker, new_id, existing_id)

    ok = await client.get(f"/api/knowledge/conflicts/{cid}", headers=admin_headers)
    assert ok.status_code == 200
    assert ok.json()["id"] == cid

    missing = await client.get("/api/knowledge/conflicts/999999", headers=admin_headers)
    assert missing.status_code == 404


async def test_resolve_keep_old_rejects_new_item(client, admin_headers, db_sessionmaker):
    new_id, existing_id = await _seed_items(
        db_sessionmaker, new_content="n", existing_content="e",
    )
    cid = await _seed_conflict(db_sessionmaker, new_id, existing_id)

    resp = await client.post(
        f"/api/knowledge/conflicts/{cid}/resolve",
        headers=admin_headers,
        json={"resolution": "keep_old"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "resolved", "resolution": "keep_old"}

    # New item rejected
    async with db_sessionmaker() as s:
        new_item = await s.get(KnowledgeItem, new_id)
        assert new_item.status == "rejected"
        conflict = await s.get(KnowledgeConflict, cid)
        assert conflict.resolution == "keep_old"

    # No longer listed among pending
    pending = await client.get("/api/knowledge/conflicts?resolution=pending", headers=admin_headers)
    assert all(c["id"] != cid for c in pending.json())


async def test_resolve_replace_old_archives_old_approves_new(client, admin_headers, db_sessionmaker):
    new_id, existing_id = await _seed_items(
        db_sessionmaker, new_content="n", existing_content="e",
    )
    cid = await _seed_conflict(db_sessionmaker, new_id, existing_id)

    resp = await client.post(
        f"/api/knowledge/conflicts/{cid}/resolve",
        headers=admin_headers,
        json={"resolution": "replace_old"},
    )
    assert resp.status_code == 200

    async with db_sessionmaker() as s:
        old_item = await s.get(KnowledgeItem, existing_id)
        new_item = await s.get(KnowledgeItem, new_id)
        assert old_item.status == "archived"
        assert new_item.status == "approved"


async def test_conflicts_require_admin(client, employee_headers, db_sessionmaker):
    resp = await client.get("/api/knowledge/conflicts", headers=employee_headers)
    assert resp.status_code == 403
