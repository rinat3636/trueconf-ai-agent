import asyncio
import logging
from typing import Optional

import httpx
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_groq_client: Optional[AsyncOpenAI] = None
_openai_client: Optional[AsyncOpenAI] = None
_google_client: Optional[AsyncOpenAI] = None
_embedding_client: Optional[AsyncOpenAI] = None
_httpx_client: Optional[httpx.AsyncClient] = None


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


def get_embedding_client() -> Optional[AsyncOpenAI]:
    """Get client for embeddings. Uses OPENAI_API_KEY if set, otherwise falls back to ANTHROPIC proxy."""
    global _embedding_client
    if _embedding_client is None:
        if settings.OPENAI_API_KEY:
            _embedding_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        elif settings.ANTHROPIC_API_KEY and settings.ANTHROPIC_BASE_URL:
            _embedding_client = AsyncOpenAI(
                api_key=settings.ANTHROPIC_API_KEY,
                base_url=settings.ANTHROPIC_BASE_URL,
            )
    return _embedding_client


def get_google_client() -> Optional[AsyncOpenAI]:
    global _google_client
    if _google_client is None and settings.GOOGLE_API_KEY:
        _google_client = AsyncOpenAI(
            api_key=settings.GOOGLE_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    return _google_client


def get_httpx_client() -> httpx.AsyncClient:
    global _httpx_client
    if _httpx_client is None:
        _httpx_client = httpx.AsyncClient(timeout=60)
    return _httpx_client


async def _anthropic_chat(
    messages: list[dict],
    model: str,
    temperature: float,
    max_tokens: int,
) -> Optional[str]:
    if not settings.ANTHROPIC_API_KEY:
        return None
    client = get_httpx_client()
    url = f"{settings.ANTHROPIC_BASE_URL}/chat/completions"
    try:
        resp = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.ANTHROPIC_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning("Anthropic httpx failed: %s", e)
        raise


async def chat_completion(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2000,
) -> str:
    model = model or settings.LLM_CHAT_MODEL
    max_retries = 3
    last_error = None

    # Primary: Anthropic (Claude via Tessera proxy, httpx)
    if settings.ANTHROPIC_API_KEY:
        try:
            claude_model = settings.LLM_CHAT_MODEL if "claude" in settings.LLM_CHAT_MODEL else "claude-sonnet-4-20250514"
            result = await _anthropic_chat(messages, claude_model, temperature, max_tokens)
            if result:
                return result
        except Exception as e:
            last_error = e
            logger.warning("Anthropic failed, trying fallback: %s", e)

    # Fallback 1: Google Gemini
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
                    logger.warning("Google Gemini failed: %s", e)
                    break

    # Fallback 2: Groq
    groq_client = get_groq_client()
    if groq_client:
        try:
            groq_model = model if "llama" in (model or "") else "llama-3.3-70b-versatile"
            response = await groq_client.chat.completions.create(
                model=groq_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning("Groq failed: %s", e)

    # Fallback 3: OpenAI
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
    raise RuntimeError("No LLM provider configured. Set ANTHROPIC_API_KEY, GROQ_API_KEY, GOOGLE_API_KEY or OPENAI_API_KEY.")


_fastembed_model = None


def _get_fastembed_model():
    global _fastembed_model
    if _fastembed_model is None:
        from fastembed import TextEmbedding
        _fastembed_model = TextEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    return _fastembed_model


async def get_embedding(text: str) -> list[float]:
    """Generate embedding using local fastembed model (no external API needed)."""
    import asyncio

    text = text.replace("\n", " ").strip()
    if len(text) > 8000:
        text = text[:8000]

    try:
        model = _get_fastembed_model()
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, lambda: list(model.embed([text]))
        )
        return embeddings[0].tolist()
    except Exception as e:
        logger.warning("Local embedding generation failed: %s", e)
        raise RuntimeError(f"Embedding generation failed: {e}")
