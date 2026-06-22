"""
Background task scheduler (ARCHITECTURE.md 8.1).

Periodic tasks:
  - analyze_chat_messages: every 6 hours (self-learning)
  - cleanup_expired_cache: daily
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_running = False


async def run_message_analysis():
    """Periodic: analyze chat messages for self-learning."""
    from app.core.database import async_session
    from app.services.self_learning import analyze_messages_task

    async with async_session() as db:
        try:
            await analyze_messages_task(db, hours=6)
            logger.info("Periodic message analysis completed")
        except Exception as e:
            logger.error(f"Message analysis failed: {e}")


async def run_cache_cleanup():
    """Periodic: clean up expired cache entries."""
    from app.core.redis import get_redis

    try:
        redis = await get_redis()
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = await redis.scan(cursor, match="chat:*", count=100)
            for key in keys:
                ttl = await redis.ttl(key)
                if ttl == -1:
                    await redis.expire(key, 3600)
                    deleted += 1
            if cursor == 0:
                break
        if deleted:
            logger.info(f"Cache cleanup: set TTL on {deleted} orphaned keys")
    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}")


async def scheduler_loop():
    """Main scheduler loop. Runs periodic tasks at intervals."""
    global _running
    _running = True
    logger.info("Background scheduler started")

    message_analysis_interval = 6 * 3600  # 6 hours
    cache_cleanup_interval = 24 * 3600    # 24 hours

    last_message_analysis = 0.0
    last_cache_cleanup = 0.0

    while _running:
        now = asyncio.get_event_loop().time()

        if now - last_message_analysis >= message_analysis_interval:
            asyncio.create_task(run_message_analysis())
            last_message_analysis = now

        if now - last_cache_cleanup >= cache_cleanup_interval:
            asyncio.create_task(run_cache_cleanup())
            last_cache_cleanup = now

        await asyncio.sleep(60)

    logger.info("Background scheduler stopped")


def stop_scheduler():
    global _running
    _running = False
