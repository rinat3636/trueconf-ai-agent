"""
Bot & system settings API.

Provides endpoints for managing chatbot configuration:
- System instructions / custom prompt additions
- Restricted topics (things the bot should NOT discuss)
- Allowed knowledge categories for the bot
- TrueConf-specific restrictions
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_admin
from app.core.audit import log_action
from app.models.user import User
from app.models.system import SystemSetting
from app.schemas.settings import BotSettingsRequest, BotSettingsResponse

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_BOT_SETTINGS = {
    "system_instructions": "",
    "restricted_topics": [],
    "allowed_categories": [],
    "trueconf_restrictions": "",
    "greeting_message": "",
    "max_response_length": 2000,
    "enable_sales_data": True,
    "enable_knowledge_base": True,
    "enable_self_learning": True,
    "custom_prompt_suffix": "",
}


async def get_bot_settings(db: AsyncSession) -> dict:
    """Load bot settings from system_settings table."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "bot_settings")
    )
    row = result.scalar_one_or_none()
    if row and row.value:
        merged = {**DEFAULT_BOT_SETTINGS, **row.value}
        return merged
    return dict(DEFAULT_BOT_SETTINGS)


@router.get("/bot", response_model=BotSettingsResponse)
async def read_bot_settings(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_bot_settings(db)
    return BotSettingsResponse(**data)


@router.put("/bot", response_model=BotSettingsResponse)
async def update_bot_settings(
    payload: BotSettingsRequest,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "bot_settings")
    )
    row = result.scalar_one_or_none()

    new_value = payload.model_dump(exclude_unset=False)

    if row:
        old_value = dict(row.value) if row.value else {}
        row.value = new_value
        row.updated_by = current_user.id
    else:
        old_value = {}
        row = SystemSetting(
            key="bot_settings",
            value=new_value,
            updated_by=current_user.id,
        )
        db.add(row)

    await db.flush()

    await log_action(
        db, "update_bot_settings",
        user_id=current_user.id,
        entity_type="system_setting",
        entity_id=row.id,
        old_value=old_value,
        new_value=new_value,
    )

    # Invalidate chat cache so new settings take effect immediately
    try:
        from app.core.redis import delete_cached
        await delete_cached("chat:*")
    except Exception:
        pass

    return BotSettingsResponse(**new_value)
