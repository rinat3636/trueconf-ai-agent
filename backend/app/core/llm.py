import logging
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_groq_client: Optional[AsyncOpenAI] = None
_openai_client: Optional[AsyncOpenAI] = None


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


async def chat_completion(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2000,
) -> str:
    model = model or settings.LLM_CHAT_MODEL

    if settings.LLM_PROVIDER == "groq":
        client = get_groq_client()
        if client:
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"Groq failed, falling back to OpenAI: {e}")

    client = get_openai_client()
    if client:
        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    raise RuntimeError("No LLM provider configured. Set GROQ_API_KEY or OPENAI_API_KEY.")


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
