#!/usr/bin/env python3
"""
Скрипт для сброса пароля администратора в OCRUZ Passport API.
Устанавливает пароль: admin123 (или любой другой по желанию)
"""

import sys
import os
from pathlib import Path

# Добавляем путь к приложению
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
from app.models import DashboardUser
from app.config import settings


def reset_admin_password(new_password="admin123"):
    """Сбрасывает пароль администратора"""

    # Создаем engine и session
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Находим пользователя admin
        admin_user = (
            db.query(DashboardUser).filter(DashboardUser.username == "admin").first()
        )

        if not admin_user:
            print("❌ Пользователь 'admin' не найден в базе данных!")
            print("Создаем нового администратора...")
            # Создаем нового администратора
            pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
            hashed_password = pwd_context.hash(new_password)

            new_admin = DashboardUser(
                username="admin",
                hashed_password=hashed_password,
                role="admin",
                is_active=True,
            )
            db.add(new_admin)
            db.commit()
            print(f"✅ Создан новый администратор с паролем: {new_password}")
        else:
            # Обновляем пароль существующего администратора
            pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
            admin_user.hashed_password = pwd_context.hash(new_password)
            admin_user.is_active = True
            admin_user.role = "admin"
            db.commit()
            print(f"✅ Пароль администратора успешно сброшен на: {new_password}")

    except Exception as e:
        print(f"❌ Ошибка при сбросе пароля: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    # Можно передать свой пароль как аргумент
    if len(sys.argv) > 1:
        password = sys.argv[1]
        reset_admin_password(password)
    else:
        reset_admin_password()
