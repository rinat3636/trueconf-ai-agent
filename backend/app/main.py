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


async def _load_company_reference():
    """Load company reference document into knowledge base once."""
    import os
    from app.models.knowledge import Document
    async with async_session() as db:
        result = await db.execute(
            select(Document).where(Document.original_filename == "company_reference.txt")
        )
        if result.scalar_one_or_none():
            return

        ref_path = os.path.join(os.path.dirname(__file__), "reference", "company_reference.txt")
        if not os.path.exists(ref_path):
            logger.warning("Company reference file not found: %s", ref_path)
            return

        with open(ref_path, "r", encoding="utf-8") as f:
            content = f.read()

        from app.services.document_processor import chunk_text
        from app.services.knowledge_service import add_knowledge_item_to_vector_db

        chunks = chunk_text(content)

        doc = Document(
            original_filename="company_reference.txt",
            file_type="txt",
            file_size=len(content),
            status="processed",
            chunk_count=len(chunks),
            uploaded_by=1,
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)

        from app.models.knowledge import KnowledgeItem
        for i, chunk in enumerate(chunks):
            item = KnowledgeItem(
                document_id=doc.id,
                content=chunk,
                status="approved",
                source_type="auto_reference",
                priority=90,
            )
            db.add(item)
            await db.flush()
            await db.refresh(item)
            try:
                await add_knowledge_item_to_vector_db(
                    item.id, chunk, title="Справочник компании",
                    category="company_reference", priority=90,
                )
            except Exception as e:
                logger.warning("Failed to index reference chunk %d: %s", i, e)

        await db.commit()
        logger.info("Loaded company reference: %d chunks indexed", len(chunks))


async def _index_existing_reports():
    """Index sales profiles for any processed reports not yet indexed in Qdrant."""
    from app.models.analytics import SalesReport
    from app.services.sales_indexer import index_sales_profiles

    async with async_session() as db:
        result = await db.execute(
            select(SalesReport).where(SalesReport.status == "processed")
        )
        reports = result.scalars().all()
        for report in reports:
            try:
                indexed = await index_sales_profiles(db, report.id)
                logger.info("Indexed %d profiles for report %d", indexed, report.id)
            except Exception as e:
                logger.warning("Failed to index report %d: %s", report.id, e)


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

    # Load company reference document into knowledge base (once)
    try:
        await _load_company_reference()
    except Exception as e:
        logger.warning("Failed to load company reference: %s", e)

    # Index existing sales reports if not yet indexed in Qdrant
    try:
        await _index_existing_reports()
    except Exception as e:
        logger.warning("Failed to index existing reports: %s", e)

    # Start background scheduler
    from app.services.scheduler import scheduler_loop
    scheduler_task = asyncio.create_task(scheduler_loop())
    _background_tasks.append(scheduler_task)

    # Start TrueConf bot (WebSocket via python-trueconf-bot)
    from app.services.trueconf_bot import BOT_ENABLED, start_bot
    if BOT_ENABLED:
        bot_task = asyncio.create_task(start_bot())
        _background_tasks.append(bot_task)
        logger.info("TrueConf bot task started")

    yield

    # Shutdown
    from app.services.scheduler import stop_scheduler
    from app.services.trueconf_bot import stop_bot
    stop_scheduler()
    stop_bot()

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
