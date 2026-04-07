from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Float,
    ForeignKey,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class DashboardUser(Base):
    __tablename__ = "dashboard_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="viewer", index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PassportData(Base):
    __tablename__ = "passport_data"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(36), unique=True, index=True, nullable=False)

    # Личные данные
    first_name = Column(String(100))
    last_name = Column(String(100))
    middle_name = Column(String(100))
    birth_date = Column(String(20))
    gender = Column(String(10))
    nationality = Column(String(50))
    pinfl = Column(String(20))

    # Данные паспорта
    passport_number = Column(String(20))
    passport_series = Column(String(10))
    issue_date = Column(String(20))
    expiry_date = Column(String(20))
    issued_by = Column(String(200))

    # MRZ
    mrz_line1 = Column(Text)
    mrz_line2 = Column(Text)
    mrz_line3 = Column(Text)
    mrz_valid = Column(Boolean, default=False)

    # Метаданные
    confidence = Column(Float, default=0.0)
    raw_text = Column(Text)
    processing_time_ms = Column(Integer, default=0)

    # Файлы
    original_scan_path = Column(String(500))
    copy_scan_path = Column(String(500))

    # Аналитика
    citizenship = Column(String(50), server_default="UZ")
    age_group = Column(String(20))
    is_foreigner = Column(Boolean, server_default="false")
    ocr_confidence_avg = Column(Float, server_default="0.0")
    mrz_confidence = Column(Float, server_default="0.0")
    field_errors = Column(JSON, server_default="{}")
    field_confidence = Column(JSON, server_default="{}")
    recognition_status = Column(String(20), server_default="partial")
    uploaded_by = Column(Integer, ForeignKey("dashboard_users.id"))

    uploader = relationship("DashboardUser", backref="uploads")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AccessLog(Base):
    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    action = Column(String(50), nullable=False)
    ip_address = Column(String(45))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
