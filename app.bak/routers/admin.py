from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
import secrets

from app.database import get_db
from app.models import DashboardUser, AccessLog, APIKey
from app.auth import get_password_hash, verify_dashboard_token
from app.api_key_auth import generate_api_key, hash_api_key
from app.schemas import (
    CreateUserRequest,
    CurrentUserInfoResponse,
    MessageResponse,
    PasswordResetResponse,
    RolesResponse,
    UpdateUserRequest,
    UserListResponse,
    UserResponse,
)

router = APIRouter()

# Роли
ROLES = {
    "admin": {
        "level": 3,
        "description": "Полный доступ: управление пользователями, настройками, просмотр всех отчетов",
        "permissions": ["create", "read", "update", "delete", "manage_users"],
    },
    "observer": {
        "level": 1,
        "description": "Только просмотр: видит отчеты и статистику, не может вносить изменения",
        "permissions": ["read"],
    },
}


def require_admin(
    payload: dict = Depends(verify_dashboard_token),
    db: Session = Depends(get_db),
):
    """Проверка прав администратора"""
    user = (
        db.query(DashboardUser).filter(DashboardUser.id == int(payload["sub"])).first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required",
        )

    # Логирование
    log = AccessLog(
        user_id=user.id,
        action="admin_access",
        ip_address=payload.get("ip"),
    )
    db.add(log)
    db.commit()

    return {"user": user, "payload": payload}


def require_observer_or_higher(
    payload: dict = Depends(verify_dashboard_token),
    db: Session = Depends(get_db),
):
    """Проверка прав наблюдателя или выше"""
    user = (
        db.query(DashboardUser).filter(DashboardUser.id == int(payload["sub"])).first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role not in ["admin", "observer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Observer or administrator role required",
        )
    return {"user": user, "payload": payload}


@router.get(
    "/roles",
    response_model=RolesResponse,
    summary="Получить доступные роли",
)
def get_available_roles(token_data: dict = Depends(require_admin)):
    """Получить список доступных ролей (только админ)"""
    return {
        "roles": [
            {
                "name": role,
                "level": data["level"],
                "description": data["description"],
                "permissions": data["permissions"],
            }
            for role, data in ROLES.items()
        ]
    }


@router.post(
    "/users",
    response_model=UserResponse,
    summary="Создать пользователя",
)
def create_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin),
):
    """
    Создать нового пользователя (ТОЛЬКО АДМИНИСТРАТОР)

    Роли:
    - admin: полный доступ
    - observer: только просмотр отчетов
    """
    if request.role not in ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Available: {', '.join(ROLES.keys())}",
        )

    existing = (
        db.query(DashboardUser)
        .filter(DashboardUser.username == request.username)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user = DashboardUser(
        username=request.username,
        hashed_password=get_password_hash(request.password),
        role=request.role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Логирование
    log = AccessLog(
        user_id=token_data["user"].id,
        action=f"create_user:{request.role}",
        ip_address=token_data["payload"].get("ip"),
    )
    db.add(log)
    db.commit()

    return user


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="Список пользователей",
)
def list_users(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin),
):
    """Список всех пользователей (ТОЛЬКО АДМИНИСТРАТОР)"""
    users = db.query(DashboardUser).order_by(DashboardUser.created_at.desc()).all()
    return UserListResponse(users=users)


@router.get(
    "/users/me",
    response_model=CurrentUserInfoResponse,
    summary="Текущий пользователь",
)
def get_current_user_info(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    """Получить информацию о текущем пользователе"""
    user = (
        db.query(DashboardUser)
        .filter(DashboardUser.id == int(token_data["payload"]["sub"]))
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role_info = ROLES.get(user.role, {})

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "role_description": role_info.get("description", ""),
        "permissions": role_info.get("permissions", []),
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Обновить пользователя",
)
def update_user(
    user_id: int,
    request: UpdateUserRequest,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin),
):
    """
    Обновить пользователя (ТОЛЬКО АДМИНИСТРАТОР)

    Можно изменить:
    - Роль (admin/observer)
    - Статус (active/inactive)
    - Пароль
    """
    user = db.query(DashboardUser).filter(DashboardUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Cannot delete last admin
    if user.role == "admin":
        admin_count = (
            db.query(DashboardUser)
            .filter(DashboardUser.role == "admin", DashboardUser.is_active == True)
            .count()
        )
        if admin_count <= 1 and request.role != "admin":
            raise HTTPException(
                status_code=400,
                detail="Cannot downgrade the last active administrator",
            )

    if request.role is not None:
        if request.role not in ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role. Available: {', '.join(ROLES.keys())}",
            )
        user.role = request.role

    if request.is_active is not None:
        user.is_active = request.is_active

    if request.password is not None:
        user.hashed_password = get_password_hash(request.password)

    db.commit()
    db.refresh(user)

    # Логирование
    log = AccessLog(
        user_id=token_data["user"].id,
        action=f"update_user:{user_id}",
        ip_address=token_data["payload"].get("ip"),
    )
    db.add(log)
    db.commit()

    return user


@router.delete(
    "/users/{user_id}",
    response_model=MessageResponse,
    summary="Удалить пользователя",
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin),
):
    """Удалить пользователя (ТОЛЬКО АДМИНИСТРАТОР)"""
    user = db.query(DashboardUser).filter(DashboardUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.username == "admin":
        raise HTTPException(
            status_code=400, detail="Cannot delete the main administrator"
        )

    db.delete(user)
    db.commit()

    # Логирование
    log = AccessLog(
        user_id=token_data["user"].id,
        action=f"delete_user:{user_id}",
        ip_address=token_data["payload"].get("ip"),
    )
    db.add(log)
    db.commit()

    return {"message": "User deleted successfully"}


@router.post(
    "/users/{user_id}/reset-password",
    response_model=PasswordResetResponse,
    summary="Сбросить пароль пользователя",
)
def reset_user_password(
    user_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin),
):
    """Сбросить пароль пользователя (ТОЛЬКО АДМИНИСТРАТОР)"""
    user = db.query(DashboardUser).filter(DashboardUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate temporary password
    temp_password = secrets.token_urlsafe(12)
    user.hashed_password = get_password_hash(temp_password)
    db.commit()

    return {
        "message": "Password reset successfully",
        "temporary_password": temp_password,
        "warning": "User must change password on next login",
    }


@router.post("/api-keys")
def create_api_key(
    name: str,
    rate_limit_per_minute: int = 60,
    rate_limit_per_day: int = 10000,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin),
):
    raw_key, prefix = generate_api_key()
    key_hash = hash_api_key(raw_key)

    api_key = APIKey(
        key_hash=key_hash,
        key_prefix=prefix,
        name=name,
        owner_id=token_data.get("sub"),
        rate_limit_per_minute=rate_limit_per_minute,
        rate_limit_per_day=rate_limit_per_day,
        is_active=True,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return {
        "id": api_key.id,
        "key": raw_key,
        "prefix": prefix,
        "name": name,
        "rate_limit_per_minute": rate_limit_per_minute,
        "rate_limit_per_day": rate_limit_per_day,
        "warning": "Store this key securely. It will not be shown again.",
    }


@router.get("/api-keys")
def list_api_keys(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin),
):
    keys = db.query(APIKey).all()
    return [
        {
            "id": k.id,
            "key_prefix": k.key_prefix,
            "name": k.name,
            "is_active": k.is_active,
            "rate_limit_per_minute": k.rate_limit_per_minute,
            "rate_limit_per_day": k.rate_limit_per_day,
            "daily_usage": k.daily_usage,
            "created_at": str(k.created_at),
            "last_used_at": str(k.last_used_at) if k.last_used_at else None,
        }
        for k in keys
    ]


@router.put("/api-keys/{key_id}")
def update_api_key(
    key_id: int,
    is_active: bool = None,
    rate_limit_per_minute: int = None,
    rate_limit_per_day: int = None,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin),
):
    key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    if is_active is not None:
        key.is_active = is_active
    if rate_limit_per_minute is not None:
        key.rate_limit_per_minute = rate_limit_per_minute
    if rate_limit_per_day is not None:
        key.rate_limit_per_day = rate_limit_per_day

    db.commit()
    db.refresh(key)
    return {"message": "API key updated", "id": key.id}


@router.delete("/api-keys/{key_id}")
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin),
):
    key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    db.delete(key)
    db.commit()
    return {"message": "API key revoked"}
