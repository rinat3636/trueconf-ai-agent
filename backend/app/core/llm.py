import asyncio
import logging
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_groq_client: Optional[AsyncOpenAI] = None
_openai_client: Optional[AsyncOpenAI] = None
_google_client: Optional[AsyncOpenAI] = None


def get_groq_client() -> Optional[AsyncOpenAI]:
    global _groq_client
    if _groq_client is None and settings.GROQ_API_KEY:
        _groq_client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
    return _groq_client


def get_openai_client() -> Optional[AsyncOpenAI]:
    global _openai_client
    if _openai_client is None and settings.OPENAI_API_KEY:
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def get_google_client() -> Optional[AsyncOpenAI]:
    global _google_client
    if _google_client is None and settings.GOOGLE_API_KEY:
        _google_client = AsyncOpenAI(
            api_key=settings.GOOGLE_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    return _google_client


async def chat_completion(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2000,
) -> str:
    model = model or settings.LLM_CHAT_MODEL
    max_retries = 3
    last_error = None

    # Primary: Google Gemini
    google_client = get_google_client()
    if google_client:
        for attempt in range(max_retries):
            try:
                response = await google_client.chat.completions.create(
                    model="gemini-2.0-flash",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                if "429" in error_str or "rate" in error_str or "quota" in error_str:
                    wait_time = 15 * (attempt + 1)
                    logger.warning(
                        "Google Gemini rate limit (attempt %d/%d), waiting %ds",
                        attempt + 1, max_retries, wait_time,
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.warning("Google Gemini failed, trying fallback: %s", e)
                    break

    # Fallback 1: Groq
    groq_client = get_groq_client()
    if groq_client:
        try:
            response = await groq_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning("Groq failed: %s", e)

    # Fallback 2: OpenAI
    client = get_openai_client()
    if client:
        try:
            response = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning("OpenAI failed: %s", e)

    if last_error and ("rate_limit" in str(last_error).lower() or "429" in str(last_error).lower()):
        raise RuntimeError(
            "Превышен лимит запросов к ИИ (Groq rate limit). "
            "Попробуйте через несколько минут."
        )
    raise RuntimeError("No LLM provider configured. Set GROQ_API_KEY, GOOGLE_API_KEY or OPENAI_API_KEY.")


async def get_embedding(text: str) -> list[float]:
    client = get_openai_client()
    if not client:
        raise RuntimeError("OpenAI API key required for embeddings. Set OPENAI_API_KEY.")

    text = text.replace("\n", " ").strip()
    if len(text) > 8000:
        text = text[:8000]

    response = await client.embeddings.create(
        model=settings.LLM_EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding
