"""
Redis-based rate limiter (ARCHITECTURE.md 9.5).

Per-endpoint rate limits:
  - chat endpoints: 100 req/min
  - upload endpoints: 10 req/min
  - default: 200 req/min
"""

import time
import logging

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

RATE_LIMITS = {
    "/api/chat/ask": (100, 60),
    "/api/knowledge/documents/upload": (10, 60),
    "/api/analytics/reports/upload": (10, 60),
    "/api/analytics/ask": (50, 60),
    "/api/knowledge/reindex": (5, 60),
}

DEFAULT_LIMIT = (200, 60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        limit, window = DEFAULT_LIMIT
        for prefix, (l, w) in RATE_LIMITS.items():
            if path.startswith(prefix):
                limit, window = l, w
                break

        try:
            redis = await get_redis()
            key = f"rate:{client_ip}:{path}"

            current = await redis.get(key)
            if current and int(current) >= limit:
                logger.warning(f"Rate limit exceeded: {client_ip} on {path}")
                raise HTTPException(
                    status_code=429,
                    detail="Слишком много запросов. Подождите и попробуйте снова.",
                )

            pipe = redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            await pipe.execute()
        except HTTPException:
            raise
        except Exception:
            pass

        return await call_next(request)
