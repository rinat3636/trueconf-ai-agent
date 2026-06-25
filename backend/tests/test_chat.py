"""Chat endpoint. The LLM/RAG pipeline (generate_answer) is patched so the test
asserts the endpoint's own behaviour: session creation, message persistence and
response shaping — without calling the real model."""
import pytest

from app.models.chat import ChatMessage, ChatSession


@pytest.fixture(autouse=True)
def _fake_answer(monkeypatch):
    async def _generate(message, db, chat_history=None):
        return {
            "answer": f"Эхо: {message}",
            "sources": [],
            "rules_applied": [],
            "confidence": 0.87,
            "response_time_ms": 12,
            "trace": {"mocked": True},
        }

    monkeypatch.setattr("app.api.chat.generate_answer", _generate)


async def test_ask_creates_session_and_returns_answer(client, employee_headers, db_sessionmaker):
    resp = await client.post(
        "/api/chat/ask",
        headers=employee_headers,
        json={"message": "Какая цена пломбира?", "channel": "web"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["answer"] == "Эхо: Какая цена пломбира?"
    assert body["confidence"] == 0.87
    assert isinstance(body["session_id"], int)
    assert isinstance(body["message_id"], int)

    # Both user and assistant messages persisted
    async with db_sessionmaker() as s:
        from sqlalchemy import select
        msgs = (await s.execute(select(ChatMessage).where(ChatMessage.session_id == body["session_id"]))).scalars().all()
        roles = sorted(m.role for m in msgs)
        assert roles == ["assistant", "user"]


async def test_ask_requires_auth(client):
    resp = await client.post("/api/chat/ask", json={"message": "hi"})
    assert resp.status_code == 403


async def test_ask_rejects_too_long_message(client, employee_headers):
    resp = await client.post(
        "/api/chat/ask",
        headers=employee_headers,
        json={"message": "x" * 5001},
    )
    assert resp.status_code == 400


async def test_ask_unknown_session_404(client, employee_headers):
    resp = await client.post(
        "/api/chat/ask",
        headers=employee_headers,
        json={"message": "hi", "session_id": 999999},
    )
    assert resp.status_code == 404
