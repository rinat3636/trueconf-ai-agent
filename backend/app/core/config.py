from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "TrueConf AI Agent"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # Database (MySQL)
    DATABASE_URL: str = "mysql+aiomysql://trueconf:trueconf_db_pass@localhost:3306/trueconf_agent"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"

    # JWT
    SECRET_KEY: str = "change-me-in-production-use-strong-secret-key"  # overridden by .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM (aitunnel.ru — unified OpenAI-compatible API)
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.aitunnel.ru/v1"
    LLM_CHAT_MODEL: str = "claude-sonnet-4"  # main model for chat
    LLM_LIGHT_MODEL: str = "gpt-4.1-mini"  # lightweight model for extraction/classification

    # TrueConf Chatbot (via python-trueconf-bot / WebSocket API)
    TRUECONF_SERVER_ADDRESS: str = ""  # IP or FQDN, e.g. "192.168.1.158"
    TRUECONF_BOT_USERNAME: str = ""  # TrueConf Server user account for bot
    TRUECONF_BOT_PASSWORD: str = ""  # Password for the bot user account
    TRUECONF_BOT_USE_HTTPS: bool = False  # Use wss:// via Web Manager (port 443)
    TRUECONF_BOT_WEB_PORT: int = 0  # Custom web port (0 = default)

    # Legacy TrueConf REST API (kept for admin API access if needed)
    TRUECONF_API_URL: str = ""
    TRUECONF_CLIENT_ID: str = ""
    TRUECONF_CLIENT_SECRET: str = ""
    TRUECONF_OAUTH_REDIRECT_URI: str = "https://localhost/"
    TRUECONF_BOT_ID: str = ""

    # Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # RAG
    RAG_TOP_K: int = 10
    RAG_SCORE_THRESHOLD: float = 0.35
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    MAX_CONTEXT_TOKENS: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = Path(settings.UPLOAD_DIR) if Path(settings.UPLOAD_DIR).is_absolute() else BASE_DIR / settings.UPLOAD_DIR

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "documents").mkdir(exist_ok=True)
(UPLOAD_DIR / "reports").mkdir(exist_ok=True)
