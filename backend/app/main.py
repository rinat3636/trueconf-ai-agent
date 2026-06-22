import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.core.config import settings
from app.core.database import init_db, async_session
from app.core.security import get_password_hash
from app.core.redis import close_redis
from app.core.qdrant import init_collections
from app.core.rate_limiter import RateLimitMiddleware
from app.models.user import User

logger = logging.getLogger(__name__)

_background_tasks = []


async def create_default_admin():
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            admin = User(
                username="admin",
                email="admin@trueconf-agent.local",
                full_name="System Administrator",
                hashed_password=get_password_hash("admin123"),
                role="super_admin",
            )
            db.add(admin)
            await db.commit()
            logger.info("Default admin user created (admin/admin123)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)
    logger.info("Starting TrueConf AI Agent v%s", settings.APP_VERSION)

    await init_db()
    logger.info("Database tables created")

    await create_default_admin()

    try:
        init_collections()
        logger.info("Qdrant collections initialized")
    except Exception as e:
        logger.warning("Qdrant not available: %s", e)

    # Start background scheduler
    from app.services.scheduler import scheduler_loop
    scheduler_task = asyncio.create_task(scheduler_loop())
    _background_tasks.append(scheduler_task)

    # Start TrueConf bot polling (if configured)
    from app.services.trueconf_bot import trueconf_bot
    if trueconf_bot.enabled:
        bot_task = asyncio.create_task(trueconf_bot.start_polling())
        _background_tasks.append(bot_task)
        logger.info("TrueConf bot polling started")

    yield

    # Shutdown
    from app.services.scheduler import stop_scheduler
    from app.services.trueconf_bot import trueconf_bot as bot
    stop_scheduler()
    bot.stop_polling()

    for task in _background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await close_redis()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.knowledge import router as knowledge_router
from app.api.analytics import router as analytics_router
from app.api.monitoring import router as monitoring_router

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(knowledge_router)
app.include_router(analytics_router)
app.include_router(monitoring_router)


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
    }
