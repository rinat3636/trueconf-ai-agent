from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, JSON

from app.core.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel = Column(String(50), nullable=False, default="trueconf")  # trueconf, web, api
    trueconf_chat_id = Column(String(255), nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_activity_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_sessions_user", "user_id"),
        Index("idx_sessions_trueconf", "trueconf_chat_id"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    trace = Column(JSON, default=dict)
    feedback = Column(String(20), nullable=True)  # useful, not_useful
    feedback_comment = Column(Text, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_messages_session", "session_id", "created_at"),
    )
