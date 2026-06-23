"""
TrueConf Chatbot via official python-trueconf-bot library.

Uses the TrueConf Chatbot Connector API (WebSocket on port 4309).
Requires a dedicated user account on TrueConf Server.

Handles:
  - Token acquisition (HTTP or HTTPS, configurable port)
  - WebSocket connection + auto-reconnect with retry
  - Incoming messages → RAG pipeline → response
  - User mapping: TrueConf ID → users.trueconf_id
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

BOT_ENABLED = bool(
    settings.TRUECONF_SERVER_ADDRESS
    and settings.TRUECONF_BOT_USERNAME
    and settings.TRUECONF_BOT_PASSWORD
)

# Module-level reference, initialized lazily in start_bot()
trueconf_bot = None


async def _get_or_create_user(db: AsyncSession, trueconf_id: str) -> Optional[User]:
    result = await db.execute(
        select(User).where(User.trueconf_id == trueconf_id)
    )
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(
        username=f"tc_{trueconf_id.split('@')[0] if '@' in trueconf_id else trueconf_id}",
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
    db: AsyncSession, user_id: int, chat_id: str,
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


async def handle_incoming_message(
    chat_id: str,
    user_id: str,
    message_text: str,
) -> Optional[str]:
    """Process incoming message from TrueConf chat via RAG pipeline."""
    from app.services.chat_service import generate_answer

    async with async_session() as db:
        user = await _get_or_create_user(db, user_id)
        if not user:
            return "Ошибка: не удалось идентифицировать пользователя."

        session = await _get_or_create_session(db, user.id, chat_id)

        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=message_text,
        )
        db.add(user_msg)
        await db.flush()

        try:
            answer_data = await generate_answer(message_text, db)
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


def _get_token_sync(
    server: str,
    username: str,
    password: str,
    use_https: bool,
    port: int,
) -> Optional[str]:
    """
    Get OAuth2 token from Bridge API.

    The official library's _get_auth_token always uses HTTPS:443.
    This function supports HTTP:4309 for local network deployments.
    """
    protocol = "https" if use_https else "http"
    if port == 0:
        port = 443 if use_https else 4309
    url = f"{protocol}://{server}:{port}/bridge/api/client/v1/oauth/token"

    logger.info("Requesting token from %s for user=%s", url, username)

    with httpx.Client(timeout=10.0, verify=False) as client:
        resp = client.post(url, json={
            "client_id": "chat_bot",
            "grant_type": "password",
            "username": username,
            "password": password,
        })
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if token:
            logger.info("Token obtained successfully for user=%s", username)
        return token


def _create_bot(token: str):
    """Create Bot instance with pre-acquired token."""
    from trueconf import Bot, Dispatcher, Router, Message, F
    from trueconf.enums import ParseMode

    router = Router(name="ai_agent")
    dp = Dispatcher()
    dp.include_router(router)

    @router.message(F.text)
    async def on_text_message(message: Message):
        sender_id = message.from_user.id if message.from_user else ""
        chat_id = message.chat_id or ""
        text = message.text or ""

        if not text.strip():
            return

        logger.info(
            "TrueConf message from %s in chat %s: %s",
            sender_id, chat_id, text[:100],
        )

        response = await handle_incoming_message(
            chat_id=chat_id,
            user_id=sender_id,
            message_text=text.strip(),
        )

        if response:
            try:
                await message.answer(text=response, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                try:
                    await message.answer(text=response)
                except Exception as e:
                    logger.error("Failed to send response: %s", e)

    use_https = settings.TRUECONF_BOT_USE_HTTPS
    web_port = settings.TRUECONF_BOT_WEB_PORT or None

    bot = Bot(
        server=settings.TRUECONF_SERVER_ADDRESS,
        token=token,
        dispatcher=dp,
        verify_ssl=False,
        https=use_https,
        web_port=web_port,
        receive_unread_messages=True,
        skip_self_messages=True,
        ws_max_retries=10,
        ws_max_delay=60,
    )

    return bot


async def start_bot():
    """Start the TrueConf bot with retry logic."""
    global trueconf_bot

    if not BOT_ENABLED:
        logger.info("TrueConf bot is not configured, skipping")
        return

    max_retries = 10
    retry_delay = 30

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "TrueConf bot connecting (attempt %d/%d, server=%s, user=%s, https=%s)",
                attempt, max_retries,
                settings.TRUECONF_SERVER_ADDRESS,
                settings.TRUECONF_BOT_USERNAME,
                settings.TRUECONF_BOT_USE_HTTPS,
            )

            token = await asyncio.to_thread(
                _get_token_sync,
                settings.TRUECONF_SERVER_ADDRESS,
                settings.TRUECONF_BOT_USERNAME,
                settings.TRUECONF_BOT_PASSWORD,
                settings.TRUECONF_BOT_USE_HTTPS,
                settings.TRUECONF_BOT_WEB_PORT,
            )

            if not token:
                raise RuntimeError("Empty token received")

            trueconf_bot = _create_bot(token)
            logger.info("TrueConf bot authenticated, starting WebSocket...")

            await trueconf_bot.start()
            await trueconf_bot.run()

        except asyncio.CancelledError:
            logger.info("TrueConf bot task cancelled")
            return
        except Exception as e:
            logger.error(
                "TrueConf bot error (attempt %d/%d): %s",
                attempt, max_retries, e,
            )
            if attempt < max_retries:
                logger.info("Retrying in %ds...", retry_delay)
                await asyncio.sleep(retry_delay)
            else:
                logger.critical("TrueConf bot max retries reached, giving up")


def stop_bot():
    """Signal the bot to stop."""
    global trueconf_bot
    if trueconf_bot is not None:
        try:
            asyncio.get_event_loop().create_task(trueconf_bot.shutdown())
        except Exception:
            pass
