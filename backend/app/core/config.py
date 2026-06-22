from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "TrueConf AI Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite+aiosqlite:///./data/app.db"

    SECRET_KEY: str = "change-me-in-production-use-strong-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    AITUNNEL_API_KEY: str = ""
    AITUNNEL_BASE_URL: str = "https://api.aitunnel.ru/v1"

    LLM_CHAT_MODEL: str = "gpt-4.1-mini"
    LLM_ANALYSIS_MODEL: str = "gpt-4.1-mini"
    LLM_EMBEDDING_MODEL: str = "text-embedding-3-small"

    CHROMA_PERSIST_DIR: str = "./data/chroma"

    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    TRUECONF_API_URL: str = ""
    TRUECONF_API_KEY: str = ""
    TRUECONF_BOT_ID: str = ""

    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "documents").mkdir(exist_ok=True)
(UPLOAD_DIR / "reports").mkdir(exist_ok=True)
