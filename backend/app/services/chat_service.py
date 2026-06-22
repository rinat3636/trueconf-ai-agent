import uuid
from typing import List, Optional, Tuple

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.knowledge import CorporateRule, AnswerCorrection
from app.services.knowledge_service import search_knowledge

client = AsyncOpenAI(
    api_key=settings.AITUNNEL_API_KEY,
    base_url=settings.AITUNNEL_BASE_URL,
)


async def get_corporate_rules(db: AsyncSession) -> List[str]:
    result = await db.execute(
        select(CorporateRule).where(CorporateRule.is_active == True)
    )
    rules = result.scalars().all()
    return [f"[{r.rule_type}] {r.title}: {r.content}" for r in rules]


async def find_correction(db: AsyncSession, question: str) -> Optional[str]:
    result = await db.execute(
        select(AnswerCorrection).where(AnswerCorrection.is_active == True)
    )
    corrections = result.scalars().all()

    question_lower = question.lower()
    for correction in corrections:
        if correction.original_question.lower() in question_lower or question_lower in correction.original_question.lower():
            return correction.corrected_answer

    return None


async def generate_answer(
    question: str,
    db: AsyncSession,
    session_id: Optional[str] = None,
) -> Tuple[str, List[str], str]:
    if not session_id:
        session_id = str(uuid.uuid4())

    correction = await find_correction(db, question)
    if correction:
        return correction, ["correction"], session_id

    context_items = await search_knowledge(question, n_results=5)
    rules = await get_corporate_rules(db)

    context_text = ""
    sources = []
    for item in context_items:
        if item["relevance"] > 0.3:
            context_text += f"\n---\n{item['content']}\n"
            source = item["metadata"].get("source", "base")
            if source not in sources:
                sources.append(source)

    system_prompt = (
        "Ты - корпоративный ИИ-ассистент компании. "
        "Ты отвечаешь ТОЛЬКО на основании предоставленной базы знаний. "
        "Если информация отсутствует в базе знаний, ответь: "
        '"Информация отсутствует в базе знаний."\n'
        "Отвечай на русском языке. Будь точен и конкретен.\n"
        "Указывай источник информации, если он известен.\n"
    )

    if rules:
        system_prompt += "\nКорпоративные правила:\n"
        for rule in rules:
            system_prompt += f"- {rule}\n"

    messages = [{"role": "system", "content": system_prompt}]

    if context_text:
        messages.append({
            "role": "user",
            "content": f"Контекст из базы знаний:\n{context_text}\n\nВопрос: {question}",
        })
    else:
        messages.append({
            "role": "user",
            "content": question,
        })

    response = await client.chat.completions.create(
        model=settings.LLM_CHAT_MODEL,
        messages=messages,
        max_tokens=2000,
        temperature=0.3,
    )

    answer = response.choices[0].message.content
    return answer, sources, session_id


async def analyze_document_with_ai(text: str) -> dict:
    if len(text) > 12000:
        text = text[:12000]

    response = await client.chat.completions.create(
        model=settings.LLM_ANALYSIS_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты - ИИ-аналитик. Проанализируй документ и верни:\n"
                    "1. Краткое содержание\n"
                    "2. Основные выводы\n"
                    "3. Риски\n"
                    "4. Рекомендации\n"
                    "5. Проблемные зоны\n"
                    "Отвечай на русском языке. Будь конкретен."
                ),
            },
            {
                "role": "user",
                "content": f"Проанализируй этот документ:\n\n{text}",
            },
        ],
        max_tokens=3000,
        temperature=0.3,
    )

    return {
        "analysis": response.choices[0].message.content,
    }
