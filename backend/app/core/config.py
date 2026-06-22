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
    SECRET_KEY: str = "change-me-in-production-use-strong-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    LLM_PROVIDER: str = "groq"  # "groq" or "openai"
    LLM_CHAT_MODEL: str = "llama-3.3-70b-versatile"
    LLM_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # TrueConf
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
