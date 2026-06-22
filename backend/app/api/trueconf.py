"""TrueConf bot management and webhook endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.models.user import User
from app.services.trueconf_bot import trueconf_bot

router = APIRouter(prefix="/api/trueconf", tags=["trueconf"])


class WebhookPayload(BaseModel):
    event: Optional[str] = None
    chat_id: Optional[str] = None
    sender: Optional[str] = None
    text: Optional[str] = None
    message: Optional[str] = None
    is_group: Optional[bool] = False


class SendMessageRequest(BaseModel):
    chat_id: str
    text: str


@router.get("/status")
async def get_bot_status(
    current_user: User = Depends(get_current_admin),
):
    """Get TrueConf bot connection status."""
    return await trueconf_bot.get_status()


@router.post("/start")
async def start_bot(
    current_user: User = Depends(get_current_admin),
):
    """Start the TrueConf bot."""
    if trueconf_bot._running:
        return {"status": "already_running"}
    await trueconf_bot.start()
    return {"status": "started"}


@router.post("/stop")
async def stop_bot(
    current_user: User = Depends(get_current_admin),
):
    """Stop the TrueConf bot."""
    await trueconf_bot.stop()
    return {"status": "stopped"}


@router.post("/webhook")
async def trueconf_webhook(payload: WebhookPayload):
    """
    Webhook endpoint for TrueConf Server callbacks.
    Configure in TrueConf Server: Settings -> Web -> Webhooks
    URL: https://your-server/api/trueconf/webhook
    """
    chat_id = payload.chat_id or ""
    sender = payload.sender or ""
    text = payload.text or payload.message or ""

    if not chat_id or not text:
        return {"status": "ignored", "reason": "missing data"}

    response = await trueconf_bot.handle_incoming_message(
        chat_id=chat_id,
        sender_id=sender,
        message_text=text,
        is_group=payload.is_group or False,
    )

    if response:
        await trueconf_bot.send_message(chat_id, response)
        return {"status": "responded"}

    return {"status": "ignored"}


@router.post("/send")
async def send_message(
    request: SendMessageRequest,
    current_user: User = Depends(get_current_admin),
):
    """Send a message to a TrueConf chat (admin only)."""
    success = await trueconf_bot.send_message(request.chat_id, request.text)
    if success:
        return {"status": "sent"}
    raise HTTPException(status_code=502, detail="Failed to send message")


@router.get("/chats")
async def get_chats(
    current_user: User = Depends(get_current_admin),
):
    """List active TrueConf chats."""
    chats = await trueconf_bot.get_chats()
    return {"chats": chats}


@router.post("/test")
async def test_connection(
    current_user: User = Depends(get_current_admin),
):
    """Test connection to TrueConf Server."""
    token = await trueconf_bot.auth.get_token()
    if token:
        user_info = await trueconf_bot.get_bot_user_info()
        return {
            "status": "connected",
            "authenticated": True,
            "bot_user": user_info,
        }
    return {
        "status": "disconnected",
        "authenticated": False,
        "error": "Failed to obtain access token",
    }
