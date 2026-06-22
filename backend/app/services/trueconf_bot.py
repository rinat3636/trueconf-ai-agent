"""
TrueConf Chatbot Connector (ARCHITECTURE.md Phase 5).

Integration with TrueConf Server via REST API + polling.
Handles:
  - Incoming messages → RAG pipeline → response
  - User mapping: TrueConf ID → users.trueconf_id
  - Rich formatting (markdown → TrueConf)
  - Connection monitoring + reconnect
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage

logger = logging.getLogger(__name__)


class TrueConfBot:
    def __init__(self):
        self.api_url = settings.TRUECONF_API_URL.rstrip("/") if settings.TRUECONF_API_URL else ""
        self.api_key = settings.TRUECONF_API_KEY
        self.bot_id = settings.TRUECONF_BOT_ID
        self.enabled = bool(self.api_url and self.api_key)
        self._running = False
        self._poll_interval = 5
        self._max_retries = 10
        self._retry_delay = 30

    @property
    def headers(self) -> dict:
        return {
            "X-Auth-Token": self.api_key,
            "Content-Type": "application/json",
        }

    async def send_message(self, chat_id: str, text: str) -> bool:
        if not self.enabled:
            return False

        text = self._format_for_trueconf(text)

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.post(
                    f"{self.api_url}/api/v3.10/chats/{chat_id}/messages",
                    headers=self.headers,
                    json={"text": text},
                )
                if response.status_code in (200, 201):
                    logger.info(f"Message sent to chat {chat_id}")
                    return True
                logger.warning(f"Failed to send message: {response.status_code} {response.text}")
                return False
            except Exception as e:
                logger.error(f"Error sending message to TrueConf: {e}")
                return False

    async def get_messages(self, chat_id: str, limit: int = 50) -> list:
        if not self.enabled:
            return []

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(
                    f"{self.api_url}/api/v3.10/chats/{chat_id}/messages",
                    headers=self.headers,
                    params={"limit": limit},
                )
                if response.status_code == 200:
                    return response.json().get("messages", [])
                return []
            except Exception as e:
                logger.error(f"Error getting messages: {e}")
                return []

    async def get_chats(self) -> list:
        if not self.enabled:
            return []

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(
                    f"{self.api_url}/api/v3.10/chats",
                    headers=self.headers,
                )
                if response.status_code == 200:
                    return response.json().get("chats", [])
                return []
            except Exception as e:
                logger.error(f"Error getting chats: {e}")
                return []

    async def handle_incoming_message(
        self,
        chat_id: str,
        user_id: str,
        message: str,
        is_group: bool = False,
    ) -> Optional[str]:
        """Process incoming message from TrueConf chat.
        1. Map TrueConf user to internal user
        2. Create/get chat session
        3. Run RAG pipeline
        4. Send response back
        """
        from app.services.chat_service import generate_answer

        async with async_session() as db:
            user = await self._get_or_create_user(db, user_id)
            if not user:
                return "Ошибка: не удалось идентифицировать пользователя."

            session = await self._get_or_create_session(db, user.id, chat_id)

            user_msg = ChatMessage(
                session_id=session.id,
                role="user",
                content=message,
            )
            db.add(user_msg)
            await db.flush()

            try:
                answer_data = await generate_answer(message, db)
            except Exception as e:
                logger.error(f"RAG pipeline error for TrueConf message: {e}")
                answer_data = {
                    "answer": "Произошла ошибка при обработке запроса. Попробуйте позже.",
                    "sources": [],
                    "rules_applied": [],
                    "confidence": 0.0,
                    "response_time_ms": 0,
                    "trace": {"error": str(e)},
                }

            assistant_msg = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=answer_data["answer"],
                trace=answer_data.get("trace", {}),
                response_time_ms=answer_data.get("response_time_ms", 0),
            )
            db.add(assistant_msg)

            session.last_activity_at = datetime.now(timezone.utc)
            await db.commit()

            return answer_data["answer"]

    async def _get_or_create_user(self, db: AsyncSession, trueconf_id: str) -> Optional[User]:
        result = await db.execute(
            select(User).where(User.trueconf_id == trueconf_id)
        )
        user = result.scalar_one_or_none()
        if user:
            return user

        user = User(
            username=f"tc_{trueconf_id}",
            trueconf_id=trueconf_id,
            full_name=trueconf_id,
            hashed_password="trueconf_auth",
            role="employee",
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        logger.info(f"Created user for TrueConf ID: {trueconf_id}")
        return user

    async def _get_or_create_session(
        self, db: AsyncSession, user_id: int, chat_id: str,
    ) -> ChatSession:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.user_id == user_id,
                ChatSession.channel == "trueconf",
            ).order_by(ChatSession.last_activity_at.desc()).limit(1)
        )
        session = result.scalar_one_or_none()

        if session:
            return session

        session = ChatSession(
            user_id=user_id,
            channel="trueconf",
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return session

    def _format_for_trueconf(self, text: str) -> str:
        """Convert markdown to TrueConf-friendly text."""
        text = text.replace("**", "")
        text = text.replace("```", "")
        if len(text) > 4000:
            text = text[:3997] + "..."
        return text

    async def start_polling(self):
        """Start polling for new messages from TrueConf.
        Runs as a background task."""
        if not self.enabled:
            logger.info("TrueConf bot is not configured, skipping polling")
            return

        self._running = True
        retries = 0
        logger.info("TrueConf bot polling started")

        while self._running:
            try:
                chats = await self.get_chats()
                for chat in chats:
                    chat_id = chat.get("chatID", "")
                    if not chat_id:
                        continue

                    messages = await self.get_messages(chat_id, limit=5)
                    for msg in messages:
                        sender = msg.get("senderId", "")
                        if sender == self.bot_id:
                            continue

                        text = msg.get("text", "").strip()
                        if not text:
                            continue

                        response = await self.handle_incoming_message(
                            chat_id=chat_id,
                            user_id=sender,
                            message=text,
                        )
                        if response:
                            await self.send_message(chat_id, response)

                retries = 0
                await asyncio.sleep(self._poll_interval)

            except Exception as e:
                retries += 1
                logger.error(f"TrueConf polling error (attempt {retries}): {e}")
                if retries >= self._max_retries:
                    logger.critical("TrueConf polling max retries reached, stopping")
                    break
                await asyncio.sleep(self._retry_delay)

        self._running = False
        logger.info("TrueConf bot polling stopped")

    def stop_polling(self):
        self._running = False


trueconf_bot = TrueConfBot()
