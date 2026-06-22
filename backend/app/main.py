from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.core.security import get_password_hash
from app.api import auth, knowledge, chat, analytics, monitoring, trueconf


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await create_default_admin()
    from app.services.trueconf_bot import trueconf_bot
    await trueconf_bot.start()
    yield
    await trueconf_bot.stop()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(knowledge.router)
app.include_router(chat.router)
app.include_router(analytics.router)
app.include_router(monitoring.router)
app.include_router(trueconf.router)


async def create_default_admin():
    from app.core.database import async_session
    from app.models.user import User
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            admin = User(
                username="admin",
                email="admin@company.local",
                full_name="Administrator",
                hashed_password=get_password_hash("admin123"),
                role="admin",
            )
            db.add(admin)
            await db.commit()


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
