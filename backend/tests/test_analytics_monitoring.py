"""Sales analytics listing + monitoring/health endpoints."""
import pytest

from app.models.analytics import SalesReport


async def test_reports_list_empty(client, admin_headers):
    resp = await client.get("/api/analytics/reports", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_reports_list_returns_seeded_report(client, admin_headers, db_sessionmaker, admin_user):
    async with db_sessionmaker() as s:
        s.add(SalesReport(
            uploaded_by=admin_user["id"],
            filename="q1.xlsx",
            original_filename="q1.xlsx",
            file_path="/tmp/q1.xlsx",
            status="processed",
            total_revenue=1000.0,
        ))
        await s.commit()

    resp = await client.get("/api/analytics/reports", headers=admin_headers)
    assert resp.status_code == 200
    reports = resp.json()
    assert len(reports) == 1
    assert reports[0]["original_filename"] == "q1.xlsx"


async def test_get_missing_report_404(client, admin_headers):
    resp = await client.get("/api/analytics/reports/999999", headers=admin_headers)
    assert resp.status_code == 404


async def test_health_endpoint_reports_service_keys(client):
    """Health is public and must always answer with a per-service breakdown."""
    resp = await client.get("/api/monitoring/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ok", "degraded"}
    for svc in ("mysql", "redis", "qdrant", "trueconf"):
        assert svc in body["services"]


async def test_stats_requires_admin(client, employee_headers):
    resp = await client.get("/api/monitoring/stats", headers=employee_headers)
    assert resp.status_code == 403


async def test_stats_counts_users(client, admin_headers):
    resp = await client.get("/api/monitoring/stats", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_users"] >= 1
    assert "total_documents" in body
    assert "total_knowledge_items" in body
