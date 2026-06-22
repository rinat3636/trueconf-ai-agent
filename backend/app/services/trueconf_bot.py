"""
TrueConf Chatbot Connector with OAuth2 authentication.

Integration with TrueConf Server via REST API v3.10.
Handles:
  - OAuth2 client_credentials token management
  - Incoming messages → RAG pipeline → response
  - User mapping: TrueConf ID → users.trueconf_id
  - Rich formatting (markdown → TrueConf)
  - Connection monitoring + reconnect
"""

import asyncio
import logging
import time
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
        self.client_id = settings.TRUECONF_CLIENT_ID
        self.client_secret = settings.TRUECONF_CLIENT_SECRET
        self.redirect_uri = settings.TRUECONF_OAUTH_REDIRECT_URI
        self.bot_id = settings.TRUECONF_BOT_ID
        self.enabled = bool(self.api_url and self.client_id and self.client_secret)

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._running = False
        self._poll_interval = 5
        self._max_retries = 10
        self._retry_delay = 30
        self._processed_messages: set = set()

    async def _get_access_token(self) -> Optional[str]:
        """Get OAuth2 access token using client_credentials grant."""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        async with httpx.AsyncClient(timeout=5, verify=False) as client:
            try:
                response = await client.post(
                    f"{self.api_url}/oauth2/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if response.status_code == 200:
                    data = response.json()
                    self._access_token = data.get("access_token")
                    expires_in = data.get("expires_in", 3600)
                    self._token_expires_at = time.time() + expires_in
                    logger.info("OAuth2 token obtained, expires in %ds", expires_in)
                    return self._access_token
                else:
                    logger.error(
                        "OAuth2 token request failed: %d %s",
                        response.status_code, response.text,
                    )
                    return None
            except Exception as e:
                logger.error("OAuth2 token request error: %s", e)
                return None

    @property
    async def headers(self) -> dict:
        token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {token}" if token else "",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs) -> Optional[httpx.Response]:
        """Make authenticated request to TrueConf API."""
        token = await self._get_access_token()
        if not token:
            return None

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            try:
                response = await client.request(
                    method,
                    f"{self.api_url}/api/v3.10{path}",
                    headers=headers,
                    **kwargs,
                )
                if response.status_code == 401:
                    self._access_token = None
                    token = await self._get_access_token()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        response = await client.request(
                            method,
                            f"{self.api_url}/api/v3.10{path}",
                            headers=headers,
                            **kwargs,
                        )
                return response
            except Exception as e:
                logger.error("TrueConf API request error (%s %s): %s", method, path, e)
                return None

    async def send_message(self, chat_id: str, text: str) -> bool:
        if not self.enabled:
            return False

        text = self._format_for_trueconf(text)

        response = await self._request(
            "POST",
            f"/chats/{chat_id}/messages",
            json={"text": text},
        )
        if response and response.status_code in (200, 201):
            logger.info("Message sent to chat %s", chat_id)
            return True
        logger.warning(
            "Failed to send message: %s",
            response.text if response else "no response",
        )
        return False

    async def get_messages(self, chat_id: str, limit: int = 50) -> list:
        if not self.enabled:
            return []

        response = await self._request(
            "GET",
            f"/chats/{chat_id}/messages",
            params={"limit": limit},
        )
        if response and response.status_code == 200:
            return response.json().get("messages", [])
        return []

    async def get_chats(self) -> list:
        if not self.enabled:
            return []

        response = await self._request("GET", "/chats")
        if response and response.status_code == 200:
            return response.json().get("chats", [])
        return []

    async def get_users(self) -> list:
        if not self.enabled:
            return []

        response = await self._request("GET", "/users")
        if response and response.status_code == 200:
            return response.json().get("users", [])
        return []

    async def check_connection(self) -> dict:
        """Check if TrueConf Server is reachable and token is valid."""
        if not self.enabled:
            return {"status": "disabled", "message": "TrueConf not configured"}

        token = await self._get_access_token()
        if not token:
            return {"status": "error", "message": "Cannot obtain OAuth2 token"}

        response = await self._request("GET", "/server/info")
        if response and response.status_code == 200:
            info = response.json()
            return {
                "status": "connected",
                "server_id": info.get("server_id", ""),
                "server_name": info.get("server_name", ""),
            }
        return {
            "status": "error",
            "message": f"Server returned {response.status_code}" if response else "No response",
        }

    async def handle_incoming_message(
        self,
        chat_id: str,
        user_id: str,
        message: str,
        is_group: bool = False,
    ) -> Optional[str]:
        """Process incoming message from TrueConf chat."""
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
                logger.error("RAG pipeline error for TrueConf message: %s", e)
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
        logger.info("Created user for TrueConf ID: %s", trueconf_id)
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
        """Start polling for new messages from TrueConf."""
        if not self.enabled:
            logger.info("TrueConf bot is not configured, skipping polling")
            return

        conn = await self.check_connection()
        if conn["status"] != "connected":
            logger.warning("TrueConf Server not reachable: %s", conn)

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
                        msg_id = msg.get("messageID", "")
                        sender = msg.get("senderId", "")
                        if sender == self.bot_id:
                            continue
                        if msg_id in self._processed_messages:
                            continue

                        text = msg.get("text", "").strip()
                        if not text:
                            continue

                        self._processed_messages.add(msg_id)
                        if len(self._processed_messages) > 10000:
                            self._processed_messages = set(
                                list(self._processed_messages)[-5000:]
                            )

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
                logger.error("TrueConf polling error (attempt %d): %s", retries, e)
                if retries >= self._max_retries:
                    logger.critical("TrueConf polling max retries reached, stopping")
                    break
                await asyncio.sleep(self._retry_delay)

        self._running = False
        logger.info("TrueConf bot polling stopped")

    def stop_polling(self):
        self._running = False


trueconf_bot = TrueConfBot()
