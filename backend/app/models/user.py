from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Index

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="employee")  # super_admin, admin, manager, employee
    trueconf_id = Column(String(255), unique=True, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    last_login = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_users_trueconf", "trueconf_id"),
        Index("idx_users_role", "role"),
    )
