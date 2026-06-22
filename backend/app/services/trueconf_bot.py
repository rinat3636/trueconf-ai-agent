"""
TrueConf Server Bot Integration.

Handles OAuth2 authentication with TrueConf Server API v3.10,
message polling, and automatic AI responses.

TrueConf API docs: https://developers.trueconf.com/api/server/
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session
from app.models.user import User
from app.models.analytics import ChatMessage

logger = logging.getLogger("trueconf_bot")


class TrueConfAuth:
    """Manages OAuth2 tokens for TrueConf Server API."""

    def __init__(self):
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.expires_at: float = 0

    @property
    def token_url(self) -> str:
        return f"{settings.TRUECONF_SERVER_URL}/oauth2/v1/token"

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 60

    async def authenticate(self) -> bool:
        """Get initial access token using client credentials + password grant."""
        try:
            async with httpx.AsyncClient(verify=settings.TRUECONF_VERIFY_SSL) as client:
                response = await client.post(
                    self.token_url,
                    data={
                        "grant_type": "password",
                        "client_id": settings.TRUECONF_CLIENT_ID,
                        "client_secret": settings.TRUECONF_CLIENT_SECRET,
                        "username": settings.TRUECONF_BOT_USER,
                        "password": settings.TRUECONF_BOT_PASSWORD,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=15,
                )
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data["access_token"]
                    self.refresh_token = data.get("refresh_token")
                    self.expires_at = time.time() + data.get("expires_in", 3600)
                    logger.info("TrueConf OAuth2: authenticated successfully")
                    return True
                else:
                    logger.error(
                        "TrueConf OAuth2 failed: %s %s",
                        response.status_code,
                        response.text,
                    )
                    return False
        except Exception as e:
            logger.error("TrueConf OAuth2 error: %s", e)
            return False

    async def refresh(self) -> bool:
        """Refresh the access token."""
        if not self.refresh_token:
            return await self.authenticate()
        try:
            async with httpx.AsyncClient(verify=settings.TRUECONF_VERIFY_SSL) as client:
                response = await client.post(
                    self.token_url,
                    data={
                        "grant_type": "refresh_token",
                        "client_id": settings.TRUECONF_CLIENT_ID,
                        "client_secret": settings.TRUECONF_CLIENT_SECRET,
                        "refresh_token": self.refresh_token,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=15,
                )
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data["access_token"]
                    self.refresh_token = data.get("refresh_token", self.refresh_token)
                    self.expires_at = time.time() + data.get("expires_in", 3600)
                    logger.info("TrueConf OAuth2: token refreshed")
                    return True
                else:
                    logger.warning("TrueConf token refresh failed, re-authenticating")
                    return await self.authenticate()
        except Exception as e:
            logger.error("TrueConf token refresh error: %s", e)
            return await self.authenticate()

    async def get_token(self) -> Optional[str]:
        """Return a valid access token, refreshing if necessary."""
        if self.is_expired:
            if self.access_token:
                success = await self.refresh()
            else:
                success = await self.authenticate()
            if not success:
                return None
        return self.access_token


class TrueConfBot:
    """TrueConf Server bot that handles messaging via API v3.10."""

    def __init__(self):
        self.auth = TrueConfAuth()
        self.base_url = settings.TRUECONF_SERVER_URL
        self.api_base = f"{self.base_url}/api/v3.10"
        self.enabled = settings.TRUECONF_ENABLED
        self.poll_interval = settings.TRUECONF_POLL_INTERVAL
        self._running = False
        self._last_message_ids: dict[str, int] = {}
        self._known_chats: set[str] = set()

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def start(self):
        """Start the bot: authenticate and begin polling."""
        if not self.enabled:
            logger.info("TrueConf bot is disabled (TRUECONF_ENABLED=false)")
            return

        if not settings.TRUECONF_CLIENT_ID or not settings.TRUECONF_CLIENT_SECRET:
            logger.warning("TrueConf credentials not configured, bot disabled")
            return

        logger.info("Starting TrueConf bot...")
        success = await self.auth.authenticate()
        if not success:
            logger.error("TrueConf bot failed to authenticate, will retry in background")

        self._running = True
        asyncio.create_task(self._poll_loop())
        logger.info("TrueConf bot started, polling every %ds", self.poll_interval)

    async def stop(self):
        """Stop the bot polling loop."""
        self._running = False
        logger.info("TrueConf bot stopped")

    async def _api_get(self, path: str, params: dict = None) -> Optional[dict]:
        """Make authenticated GET request to TrueConf API."""
        token = await self.auth.get_token()
        if not token:
            return None
        try:
            async with httpx.AsyncClient(verify=settings.TRUECONF_VERIFY_SSL) as client:
                response = await client.get(
                    f"{self.api_base}{path}",
                    headers=self._headers(token),
                    params=params,
                    timeout=15,
                )
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    await self.auth.authenticate()
                    return None
                else:
                    logger.debug("API GET %s: %s", path, response.status_code)
                    return None
        except Exception as e:
            logger.debug("API GET %s error: %s", path, e)
            return None

    async def _api_post(self, path: str, json_data: dict = None) -> Optional[dict]:
        """Make authenticated POST request to TrueConf API."""
        token = await self.auth.get_token()
        if not token:
            return None
        try:
            async with httpx.AsyncClient(verify=settings.TRUECONF_VERIFY_SSL) as client:
                response = await client.post(
                    f"{self.api_base}{path}",
                    headers=self._headers(token),
                    json=json_data,
                    timeout=30,
                )
                if response.status_code in (200, 201):
                    return response.json()
                elif response.status_code == 401:
                    await self.auth.authenticate()
                    return None
                else:
                    logger.debug(
                        "API POST %s: %s %s",
                        path,
                        response.status_code,
                        response.text[:200],
                    )
                    return None
        except Exception as e:
            logger.debug("API POST %s error: %s", path, e)
            return None

    async def get_bot_user_info(self) -> Optional[dict]:
        """Get info about the bot's own user account."""
        return await self._api_get(f"/users/{settings.TRUECONF_BOT_USER}")

    async def get_chats(self) -> list:
        """Get list of chats the bot is participating in."""
        data = await self._api_get(
            f"/users/{settings.TRUECONF_BOT_USER}/chats",
            params={"page_size": 100},
        )
        if data and "list" in data:
            return data["list"]
        if data and "chats" in data:
            return data["chats"]
        if isinstance(data, list):
            return data
        return []

    async def get_chat_messages(
        self, chat_id: str, last_id: int = 0, limit: int = 50
    ) -> list:
        """Get messages from a specific chat."""
        params = {"page_size": limit}
        if last_id:
            params["from_id"] = last_id

        data = await self._api_get(
            f"/chats/{chat_id}/messages",
            params=params,
        )
        if data and "list" in data:
            return data["list"]
        if data and "messages" in data:
            return data["messages"]
        if isinstance(data, list):
            return data
        return []

    async def send_message(self, chat_id: str, text: str) -> bool:
        """Send a text message to a chat."""
        result = await self._api_post(
            f"/chats/{chat_id}/messages",
            json_data={"text": text},
        )
        if result is not None:
            logger.info("Sent message to chat %s", chat_id)
            return True

        result = await self._api_post(
            f"/chats/{chat_id}/send",
            json_data={"message": text},
        )
        if result is not None:
            logger.info("Sent message to chat %s (alt endpoint)", chat_id)
            return True

        return False

    async def send_direct_message(self, user_id: str, text: str) -> bool:
        """Send a direct message to a user."""
        result = await self._api_post(
            f"/users/{settings.TRUECONF_BOT_USER}/chats/{user_id}/messages",
            json_data={"text": text},
        )
        if result is not None:
            return True
        return await self.send_message(user_id, text)

    async def _get_or_create_bot_db_user(self) -> int:
        """Get or create a DB user for the TrueConf bot."""
        async with async_session() as db:
            result = await db.execute(
                select(User).where(User.username == f"trueconf_bot")
            )
            user = result.scalar_one_or_none()
            if user:
                return user.id

            from app.core.security import get_password_hash
            bot_user = User(
                username="trueconf_bot",
                email="bot@trueconf.local",
                full_name="TrueConf AI Bot",
                hashed_password=get_password_hash("bot-internal-only"),
                role="employee",
            )
            db.add(bot_user)
            await db.commit()
            await db.refresh(bot_user)
            return bot_user.id

    async def handle_incoming_message(
        self,
        chat_id: str,
        sender_id: str,
        message_text: str,
        is_group: bool = False,
    ) -> Optional[str]:
        """Process an incoming message and generate AI response."""
        if sender_id == settings.TRUECONF_BOT_USER:
            return None

        if not message_text or not message_text.strip():
            return None

        if is_group:
            bot_mention = f"@{settings.TRUECONF_BOT_USER}"
            if bot_mention not in message_text and not message_text.startswith("/"):
                return None
            message_text = message_text.replace(bot_mention, "").strip()

        logger.info(
            "Processing message from %s in %s: %s",
            sender_id,
            chat_id,
            message_text[:100],
        )

        try:
            from app.services.chat_service import generate_answer

            bot_user_id = await self._get_or_create_bot_db_user()

            async with async_session() as db:
                user_msg = ChatMessage(
                    user_id=bot_user_id,
                    session_id=f"trueconf_{chat_id}",
                    role="user",
                    content=f"[{sender_id}] {message_text}",
                )
                db.add(user_msg)

                answer, sources, session_id = await generate_answer(
                    message_text, db, f"trueconf_{chat_id}"
                )

                assistant_msg = ChatMessage(
                    user_id=bot_user_id,
                    session_id=session_id,
                    role="assistant",
                    content=answer,
                    sources=sources,
                )
                db.add(assistant_msg)
                await db.commit()

            return answer

        except Exception as e:
            logger.error("Error processing message: %s", e)
            return "Произошла ошибка при обработке запроса. Попробуйте позже."

    async def _poll_loop(self):
        """Background loop that polls for new messages."""
        logger.info("TrueConf poll loop started")

        while self._running:
            try:
                await self._poll_once()
            except Exception as e:
                logger.error("Poll loop error: %s", e)

            await asyncio.sleep(self.poll_interval)

        logger.info("TrueConf poll loop stopped")

    async def _poll_once(self):
        """Single poll iteration: check for new messages in all chats."""
        token = await self.auth.get_token()
        if not token:
            logger.debug("No valid token, skipping poll")
            return

        chats = await self.get_chats()
        for chat_info in chats:
            chat_id = chat_info.get("id") or chat_info.get("chat_id", "")
            if not chat_id:
                continue

            is_group = chat_info.get("type", "") in ("group", "conference")
            last_id = self._last_message_ids.get(chat_id, 0)
            messages = await self.get_chat_messages(chat_id, last_id=last_id)

            for msg in messages:
                msg_id = msg.get("id") or msg.get("message_id", 0)
                sender = msg.get("sender") or msg.get("from", "")
                text = msg.get("text") or msg.get("message", "")

                if isinstance(msg_id, int) and msg_id <= last_id:
                    continue
                if sender == settings.TRUECONF_BOT_USER:
                    continue

                response = await self.handle_incoming_message(
                    chat_id, sender, text, is_group
                )
                if response:
                    await self.send_message(chat_id, response)

                if isinstance(msg_id, int):
                    self._last_message_ids[chat_id] = max(
                        self._last_message_ids.get(chat_id, 0), msg_id
                    )

    async def get_status(self) -> dict:
        """Return bot status info for monitoring."""
        token = await self.auth.get_token()
        connected = token is not None

        return {
            "enabled": self.enabled,
            "connected": connected,
            "running": self._running,
            "server_url": self.base_url,
            "bot_user": settings.TRUECONF_BOT_USER,
            "poll_interval": self.poll_interval,
            "active_chats": len(self._last_message_ids),
        }


trueconf_bot = TrueConfBot()
