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
import os
import uuid
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings, UPLOAD_DIR
from app.core.database import async_session
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.models.knowledge import Document as DocModel

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

        # Load chat history for context
        history_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .where(ChatMessage.id != user_msg.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(10)
        )
        history_msgs = list(reversed(history_result.scalars().all()))
        chat_history = [
            {"role": m.role, "content": m.content}
            for m in history_msgs
        ]

        try:
            answer_data = await generate_answer(message_text, db, chat_history=chat_history, channel="trueconf")
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


async def _process_trueconf_file(message, sender_id: str, doc):
    """Download a file from TrueConf and process it into the knowledge base."""
    from app.services.self_learning import process_document_pipeline

    try:
        unique_name = f"{uuid.uuid4()}{os.path.splitext(doc.file_name or '')[1]}"
        dest_dir = UPLOAD_DIR / "documents"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / unique_name

        downloaded = await message.bot.download_file_by_id(doc.file_id, str(dest_path))
        if not downloaded:
            logger.warning("Failed to download file %s from TrueConf", doc.file_name)
            try:
                await message.answer(text="❌ Не удалось скачать файл.")
            except Exception:
                pass
            return

        file_size = dest_path.stat().st_size if dest_path.exists() else 0

        async with async_session() as db:
            user = await _get_or_create_user(db, sender_id)
            user_id = user.id if user else None

            db_doc = DocModel(
                filename=unique_name,
                original_filename=doc.file_name or unique_name,
                file_type=os.path.splitext(doc.file_name or "")[1].lstrip(".").lower(),
                file_size=file_size,
                file_path=str(dest_path),
                status="processing",
                uploaded_by=user_id or 1,
            )
            db.add(db_doc)
            await db.commit()
            await db.refresh(db_doc)
            doc_id = db_doc.id

        async with async_session() as db:
            await process_document_pipeline(doc_id, str(dest_path), db, user_id=user_id)

        logger.info("TrueConf file processed: %s (doc_id=%d)", doc.file_name, doc_id)
        try:
            await message.answer(
                text=f"✅ Файл \"{doc.file_name}\" обработан и добавлен в базу знаний."
            )
        except Exception:
            pass

    except Exception as e:
        logger.error("Error processing TrueConf file %s: %s", doc.file_name, e)
        try:
            await message.answer(text=f"❌ Ошибка обработки файла: {str(e)[:200]}")
        except Exception:
            pass


async def _try_learn_from_chat(sender_id: str, message_text: str):
    """Evaluate if a chat message contains useful knowledge and extract it."""
    from app.core.llm import light_completion
    from app.models.knowledge import ModerationQueue
    from app.models.system import SystemSetting

    if len(message_text) < 50:
        return

    try:
        # Check if self-learning is enabled in bot settings
        async with async_session() as db:
            result = await db.execute(
                select(SystemSetting).where(SystemSetting.key == "bot_settings")
            )
            setting = result.scalar_one_or_none()
            if setting and isinstance(setting.value, dict):
                if not setting.value.get("enable_self_learning", True):
                    return
        evaluation = await light_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты — фильтр полезности для корпоративной базы знаний "
                        "компании-дистрибьютора мороженого ТД \"Мир Мороженого\".\n"
                        "Определи, содержит ли сообщение ПОЛЕЗНУЮ бизнес-информацию, "
                        "которую стоит сохранить в базу знаний.\n\n"
                        "ПОЛЕЗНО: факты о продукции, ценах, клиентах, процедурах, "
                        "правилах работы, логистике, контактах, методологиях продаж.\n"
                        "НЕ ПОЛЕЗНО: приветствия, вопросы, жалобы, личные сообщения, "
                        "команды боту, общие фразы, обсуждение погоды и т.п.\n\n"
                        "Ответь СТРОГО одним словом: ПОЛЕЗНО или БЕСПОЛЕЗНО"
                    ),
                },
                {"role": "user", "content": message_text},
            ],
            max_tokens=10,
        )

        if "ПОЛЕЗНО" not in evaluation.upper():
            return

        # Extract knowledge from the useful message
        knowledge_text = await light_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Извлеки из сообщения ключевую бизнес-информацию в формате:\n"
                        "ЗАГОЛОВОК: [краткий заголовок]\n"
                        "КАТЕГОРИЯ: [product_catalog|logistics|policy|commercial|"
                        "contacts|sales_methodology|product_knowledge|general]\n"
                        "СОДЕРЖАНИЕ: [полная информация, переформулированная как "
                        "самостоятельный факт для базы знаний]\n\n"
                        "Если сообщение содержит несколько фактов, выдели каждый отдельно "
                        "через ---"
                    ),
                },
                {"role": "user", "content": message_text},
            ],
            max_tokens=1000,
        )

        items = _parse_chat_knowledge(knowledge_text)
        if not items:
            return

        async with async_session() as db:
            for item in items:
                mod_entry = ModerationQueue(
                    item_type="chat_learned",
                    item_id=0,
                    action="add_from_trueconf_chat",
                    payload={
                        "title": item["title"],
                        "content": item["content"],
                        "category": item["category"],
                        "source_user": sender_id,
                        "source_text": message_text[:500],
                    },
                    status="pending",
                )
                db.add(mod_entry)
            await db.commit()

        logger.info(
            "Extracted %d knowledge items from TrueConf chat (user=%s)",
            len(items), sender_id,
        )

    except Exception as e:
        logger.debug("Chat learning evaluation failed: %s", e)


def _parse_chat_knowledge(text: str) -> list:
    """Parse LLM-extracted knowledge from chat message."""
    VALID_CATEGORIES = {
        "product_catalog", "logistics", "policy", "commercial",
        "contacts", "sales_methodology", "product_knowledge", "general",
    }
    items = []
    for block in text.split("---"):
        block = block.strip()
        if not block:
            continue
        title = ""
        category = "general"
        content = ""
        for line in block.split("\n"):
            line = line.strip()
            if line.upper().startswith("ЗАГОЛОВОК:"):
                title = line.split(":", 1)[1].strip()
            elif line.upper().startswith("КАТЕГОРИЯ:"):
                cat = line.split(":", 1)[1].strip().lower()
                if cat in VALID_CATEGORIES:
                    category = cat
            elif line.upper().startswith("СОДЕРЖАНИЕ:"):
                content = line.split(":", 1)[1].strip()
            elif content:
                content += "\n" + line
        if title and content and len(content) >= 20:
            items.append({"title": title, "content": content, "category": category})
    return items


def _create_bot(token: str = None, use_credentials: bool = False):
    """Create Bot instance with pre-acquired token or credentials."""
    from trueconf import Bot, Dispatcher, Router, Message, F
    from trueconf.enums import ParseMode
    from trueconf.types.message import MessageType

    router = Router(name="ai_agent")
    dp = Dispatcher()
    dp.include_router(router)

    BOT_PREFIX = "aibot"

    @router.message(F.text)
    async def on_text_message(message: Message):
        sender_id = message.from_user.id if message.from_user else ""
        chat_id = message.chat_id or ""
        text = message.text or ""

        if not text.strip():
            return

        stripped = text.strip()

        # In group chats: only respond if message starts with "aibot"
        # In P2P chats: respond to everything
        is_p2p = chat_id.startswith("chat_p2p_")
        if not is_p2p:
            lower = stripped.lower()
            if not lower.startswith(BOT_PREFIX):
                return
            # Strip the "aibot" prefix and any following whitespace/punctuation
            stripped = stripped[len(BOT_PREFIX):].lstrip(" ,:")
            if not stripped:
                stripped = "Привет"

        logger.info(
            "TrueConf message from %s in chat %s (p2p=%s): %s",
            sender_id, chat_id, is_p2p, stripped[:100],
        )

        response = await handle_incoming_message(
            chat_id=chat_id,
            user_id=sender_id,
            message_text=stripped,
        )

        if response:
            try:
                await message.answer(text=response, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                try:
                    await message.answer(text=response)
                except Exception as e:
                    logger.error("Failed to send response: %s", e)

        # After responding, try to extract useful knowledge from the conversation
        asyncio.create_task(_try_learn_from_chat(sender_id, stripped))

    @router.message(F.content_type.is_(MessageType.ATTACHMENT))
    async def on_file_message(message: Message):
        """Handle file attachments: download and process into knowledge base."""
        sender_id = message.from_user.id if message.from_user else ""
        chat_id = message.chat_id or ""
        doc = message.document
        if not doc:
            return

        ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".csv"}
        file_ext = os.path.splitext(doc.file_name or "")[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            logger.info("Skipping unsupported file type: %s", doc.file_name)
            return

        logger.info(
            "TrueConf file from %s in chat %s: %s (%s bytes)",
            sender_id, chat_id, doc.file_name, doc.file_size,
        )

        try:
            await message.answer(text="📄 Получил файл, обрабатываю...")
        except Exception:
            pass

        asyncio.create_task(
            _process_trueconf_file(message, sender_id, doc)
        )

    use_https = settings.TRUECONF_BOT_USE_HTTPS
    web_port = settings.TRUECONF_BOT_WEB_PORT or None

    if use_credentials:
        logger.info("Using Bot.from_credentials() for auth")
        bot = Bot.from_credentials(
            server=settings.TRUECONF_SERVER_ADDRESS,
            username=settings.TRUECONF_BOT_USERNAME,
            password=settings.TRUECONF_BOT_PASSWORD,
            dispatcher=dp,
            verify_ssl=False,
            https=use_https,
            web_port=web_port,
            receive_unread_messages=True,
            skip_self_messages=True,
            ws_max_retries=10,
            ws_max_delay=60,
            debug=True,
        )
    else:
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
            debug=True,
        )

    # The library's check_version() calls /api/v4/server which only exists
    # on the admin API (port 4307), not on Bridge (port 4309).
    # Skip it to avoid 404 errors when connecting via Bridge directly.
    async def _noop():
        pass
    bot.check_version = _noop

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

            # Acquire the token ourselves on the configured web port, then
            # connect with it. The library's from_credentials() always requests
            # the token on HTTPS:443, which fails when the TrueConf server is
            # reached directly on a non-standard port (e.g. 4443).
            token = await asyncio.to_thread(
                _get_token_sync,
                settings.TRUECONF_SERVER_ADDRESS,
                settings.TRUECONF_BOT_USERNAME,
                settings.TRUECONF_BOT_PASSWORD,
                settings.TRUECONF_BOT_USE_HTTPS,
                settings.TRUECONF_BOT_WEB_PORT or 0,
            )
            if not token:
                raise RuntimeError("Failed to obtain TrueConf token")
            trueconf_bot = _create_bot(token=token)
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
