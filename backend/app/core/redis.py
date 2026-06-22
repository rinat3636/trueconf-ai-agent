import json
import hashlib
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return redis_client


async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


def cache_key(prefix: str, data: str) -> str:
    h = hashlib.sha256(data.encode()).hexdigest()[:16]
    return f"{prefix}:{h}"


async def get_cached(key: str) -> Optional[dict]:
    r = await get_redis()
    val = await r.get(key)
    if val:
        return json.loads(val)
    return None


async def set_cached(key: str, value: dict, ttl: int = 3600):
    r = await get_redis()
    await r.set(key, json.dumps(value, ensure_ascii=False, default=str), ex=ttl)


async def delete_cached(pattern: str):
    r = await get_redis()
    keys = []
    async for key in r.scan_iter(match=pattern):
        keys.append(key)
    if keys:
        await r.delete(*keys)
