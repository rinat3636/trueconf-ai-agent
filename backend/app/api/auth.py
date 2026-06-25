from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token,
    get_current_user, get_current_admin,
)
from app.core.audit import log_action
from app.models.user import User
from app.schemas.auth import (
    UserCreate, UserLogin, UserUpdate, UserResponse,
    Token, RefreshRequest, ChangePassword,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(user_data.password, user.hashed_password):
        await log_action(db, "login_failed", ip_address=request.client.host)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    user.last_login = datetime.now(timezone.utc)
    await log_action(db, "login", user_id=user.id, ip_address=request.client.host)

    token_data = {"sub": str(user.id)}
    return Token(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(data.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if user_id is None or token_type != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    token_data = {"sub": str(user.id)}
    return Token(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.post("/change-password")
async def change_password(
    data: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect old password")

    current_user.hashed_password = get_password_hash(data.new_password)

    # Blacklist all existing tokens for this user
    from app.core.redis import get_redis
    redis = await get_redis()
    await redis.set(
        f"token_blacklist:user:{current_user.id}",
        datetime.now(timezone.utc).isoformat(),
        ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    await log_action(db, "change_password", user_id=current_user.id)
    return {"status": "ok"}


# --- User Management (admin only) ---

@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        role=user_data.role,
        permissions=user_data.permissions or {},
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    await log_action(
        db, "create_user", user_id=current_user.id,
        entity_type="user", entity_id=user.id,
        new_value={"username": user.username, "role": user.role},
    )
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_value = {"role": user.role, "is_active": user.is_active}

    if data.username is not None and data.username != user.username:
        exists = await db.execute(
            select(User).where(User.username == data.username, User.id != user_id)
        )
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already exists")
        user.username = data.username
    if data.password:
        user.hashed_password = get_password_hash(data.password)
    if data.email is not None:
        user.email = data.email
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.permissions is not None:
        user.permissions = data.permissions

    await log_action(
        db, "update_user", user_id=current_user.id,
        entity_type="user", entity_id=user.id,
        old_value=old_value,
        new_value={"role": user.role, "is_active": user.is_active},
    )
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить собственную учётную запись")

    if user.role == "super_admin":
        from sqlalchemy import func
        count = await db.execute(
            select(func.count()).select_from(User).where(User.role == "super_admin")
        )
        if (count.scalar() or 0) <= 1:
            raise HTTPException(status_code=400, detail="Нельзя удалить последнего суперадмина")

    await log_action(
        db, "delete_user", user_id=current_user.id,
        entity_type="user", entity_id=user.id,
        old_value={"username": user.username, "role": user.role},
    )

    from sqlalchemy import text
    # Reassign content ownership to the acting admin so non-nullable FKs stay valid
    reassign = [
        ("documents", "uploaded_by"),
        ("sales_reports", "uploaded_by"),
        ("knowledge_items", "approved_by"),
        ("knowledge_item_versions", "changed_by"),
        ("corporate_rules", "created_by"),
        ("answer_corrections", "created_by"),
        ("knowledge_conflicts", "resolved_by"),
        ("moderation_queue", "created_by"),
        ("moderation_queue", "reviewed_by"),
        ("system_settings", "updated_by"),
    ]
    for table, col in reassign:
        await db.execute(
            text(f"UPDATE {table} SET {col} = :new_id WHERE {col} = :old_id"),
            {"new_id": current_user.id, "old_id": user.id},
        )
    # Detach audit history (nullable) and remove the user's own chat sessions
    await db.execute(
        text("UPDATE audit_log SET user_id = NULL WHERE user_id = :old_id"),
        {"old_id": user.id},
    )
    await db.execute(
        text("DELETE FROM chat_messages WHERE session_id IN "
             "(SELECT id FROM chat_sessions WHERE user_id = :old_id)"),
        {"old_id": user.id},
    )
    await db.execute(
        text("DELETE FROM chat_sessions WHERE user_id = :old_id"),
        {"old_id": user.id},
    )

    await db.delete(user)
    return {"status": "ok"}
