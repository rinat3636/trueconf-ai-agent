"""Authentication & authorization."""
import pytest


async def test_login_success_returns_tokens(client, admin_user):
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["username"] == "admin"
    assert body["user"]["role"] == "super_admin"


async def test_login_wrong_password_rejected(client, admin_user):
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


async def test_me_requires_token(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 403  # HTTPBearer rejects missing credentials


async def test_me_returns_current_user(client, admin_headers):
    resp = await client.get("/api/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


async def test_refresh_token_issues_new_access_token(client, admin_user):
    login = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    refresh = login.json()["refresh_token"]
    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


async def test_refresh_rejects_access_token_as_refresh(client, admin_user):
    login = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    access = login.json()["access_token"]
    resp = await client.post("/api/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401


async def test_admin_only_endpoint_forbidden_for_employee(client, employee_headers):
    resp = await client.get("/api/auth/users", headers=employee_headers)
    assert resp.status_code == 403


async def test_admin_can_list_users(client, admin_headers):
    resp = await client.get("/api/auth/users", headers=admin_headers)
    assert resp.status_code == 200
    usernames = [u["username"] for u in resp.json()]
    assert "admin" in usernames
