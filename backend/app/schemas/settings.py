from pydantic import BaseModel, Field
from typing import List, Optional


class BotSettingsRequest(BaseModel):
    system_instructions: str = Field(
        default="",
        description="Custom system instructions appended to the bot prompt",
    )
    restricted_topics: List[str] = Field(
        default_factory=list,
        description="Topics the bot must NOT discuss (e.g. 'финансовые показатели акционеров')",
    )
    allowed_categories: List[str] = Field(
        default_factory=list,
        description="If non-empty, bot only uses knowledge from these categories",
    )
    trueconf_restrictions: str = Field(
        default="",
        description="Special restrictions for TrueConf channel (e.g. 'не разглашать данные о продажах')",
    )
    greeting_message: str = Field(
        default="",
        description="Custom greeting when user starts a new chat",
    )
    max_response_length: int = Field(
        default=2000,
        ge=100,
        le=10000,
        description="Maximum response length in characters",
    )
    enable_sales_data: bool = Field(
        default=True,
        description="Allow the bot to access and discuss sales analytics",
    )
    enable_knowledge_base: bool = Field(
        default=True,
        description="Allow the bot to search the knowledge base",
    )
    enable_self_learning: bool = Field(
        default=True,
        description="Allow automatic knowledge extraction from uploaded documents",
    )
    custom_prompt_suffix: str = Field(
        default="",
        description="Raw text appended to the end of the system prompt",
    )


class BotSettingsResponse(BotSettingsRequest):
    pass
