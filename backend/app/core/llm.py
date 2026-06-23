import asyncio
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_httpx_client: Optional[httpx.AsyncClient] = None


def get_httpx_client() -> httpx.AsyncClient:
    global _httpx_client
    if _httpx_client is None:
        _httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=30))
    return _httpx_client


async def _anthropic_chat(
    messages: list[dict],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY не настроен. Укажите ключ в .env")
    client = get_httpx_client()
    url = f"{settings.ANTHROPIC_BASE_URL}/chat/completions"
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
    if resp.status_code != 200:
        logger.error("Claude API HTTP %d: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        logger.error("Claude API empty choices: %s", str(data)[:500])
        raise RuntimeError(f"Claude API вернул пустой ответ (нет choices)")
    message = choices[0].get("message", {})
    content = message.get("content")
    if content is None:
        # Try alternative response formats
        refusal = message.get("refusal", "")
        if refusal:
            return f"[Отказ]: {refusal}"
        text = choices[0].get("text", "")
        if text:
            return text
        logger.error("Claude API no content in message: %s", str(message)[:500])
        raise RuntimeError(f"Claude API: нет content в ответе")
    return content


async def chat_completion(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2000,
) -> str:
    claude_model = model or settings.LLM_CHAT_MODEL
    if "claude" not in claude_model:
        claude_model = "claude-sonnet-4-20250514"

    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            result = await _anthropic_chat(messages, claude_model, temperature, max_tokens)
            if not result or not result.strip():
                logger.warning("Claude returned empty response, retry %d/%d", attempt + 1, max_retries)
                await asyncio.sleep(3 * (attempt + 1))
                continue
            return result
        except Exception as e:
            last_error = e
            error_type = type(e).__name__
            error_str = str(e).lower()
            is_retryable = (
                "429" in error_str or "rate" in error_str
                or "empty" in error_str or "timeout" in error_type.lower()
                or isinstance(e, (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException))
            )
            if is_retryable:
                wait_time = 5 * (attempt + 1)
                logger.warning(
                    "Anthropic retryable error (attempt %d/%d), waiting %ds: %s: %s",
                    attempt + 1, max_retries, wait_time, error_type, e,
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error("Anthropic (Claude) error [%s]: %s", error_type, e)
                break

    raise RuntimeError(
        f"Ошибка Claude API ({type(last_error).__name__}): {last_error}. "
        f"Проверьте ANTHROPIC_API_KEY и доступность сервера."
    )


_fastembed_model = None


def _get_fastembed():
    global _fastembed_model
    if _fastembed_model is None:
        from fastembed import TextEmbedding
        _fastembed_model = TextEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    return _fastembed_model


async def get_embedding(text: str) -> list[float]:
    text = text.replace("\n", " ").strip()
    if len(text) > 8000:
        text = text[:8000]

    # Use local fastembed (no API key needed)
    import asyncio
    model = _get_fastembed()
    embeddings = await asyncio.to_thread(
        lambda: list(model.embed([text]))[0].tolist()
    )
    return embeddings
