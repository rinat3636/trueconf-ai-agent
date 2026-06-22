from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "employee"


class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    role: str
    trueconf_id: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str
