"""
TrueConf Chatbot via official python-trueconf-bot library.

Uses the TrueConf Chatbot Connector API (WebSocket on port 4309).
Requires a dedicated user account on TrueConf Server.

Handles:
  - WebSocket connection + auto-reconnect
  - Incoming messages → RAG pipeline → response
  - User mapping: TrueConf ID → users.trueconf_id
  - Markdown formatting support
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone

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


def _create_bot():
    """Create TrueConf Bot instance using the official library."""
    if not BOT_ENABLED:
        return None

    try:
        from trueconf import Bot, Dispatcher, Router, Message, F
        from trueconf.enums import ParseMode
    except ImportError:
        logger.error("python-trueconf-bot not installed. Run: pip install python-trueconf-bot")
        return None

    router = Router(name="ai_agent")
    dp = Dispatcher()
    dp.include_router(router)

    @router.message(F.text)
    async def on_text_message(message: Message):
        """Handle incoming text messages."""
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

    bot = Bot.from_credentials(
        server=settings.TRUECONF_SERVER_ADDRESS,
        username=settings.TRUECONF_BOT_USERNAME,
        password=settings.TRUECONF_BOT_PASSWORD,
        dispatcher=dp,
        verify_ssl=False,
        https=settings.TRUECONF_BOT_USE_HTTPS,
        web_port=settings.TRUECONF_BOT_WEB_PORT or None,
        receive_unread_messages=True,
        skip_self_messages=True,
        ws_max_retries=10,
        ws_max_delay=60,
    )

    return bot


# Module-level bot instance
trueconf_bot = _create_bot()


async def start_bot():
    """Start the TrueConf bot (WebSocket connection)."""
    if trueconf_bot is None:
        logger.info("TrueConf bot is not configured, skipping")
        return

    logger.info(
        "Starting TrueConf bot (server=%s, user=%s, https=%s)",
        settings.TRUECONF_SERVER_ADDRESS,
        settings.TRUECONF_BOT_USERNAME,
        settings.TRUECONF_BOT_USE_HTTPS,
    )

    try:
        await trueconf_bot.start()
        await trueconf_bot.run()
    except Exception as e:
        logger.error("TrueConf bot error: %s", e)
        raise


def stop_bot():
    """Signal the bot to stop."""
    if trueconf_bot is not None:
        try:
            asyncio.get_event_loop().create_task(trueconf_bot.shutdown())
        except Exception:
            pass
