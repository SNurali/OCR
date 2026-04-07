import json
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Float,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator
from app.database import Base


class JSONEncodedDict(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


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
    passport_number = Column(String(20), index=True)
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

    # Pipeline metadata
    validation_status = Column(
        String(20), default="pending"
    )  # pending, valid, low_confidence, invalid, high_risk_fraud
    field_confidence = Column(JSONEncodedDict)
    engine_used = Column(String(20))
    document_type = Column(String(30))
    pipeline_stages = Column(JSONEncodedDict)
    fraud_risk_score = Column(Float, default=0.0)
    fraud_alerts = Column(JSONEncodedDict)

    # Файлы
    original_scan_path = Column(String(500))
    copy_scan_path = Column(String(500))
    image_hash = Column(String(64), index=True)
    perceptual_hash = Column(String(64), index=True)

    # Дедупликация
    duplicate_count = Column(Integer, default=1)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index(
            "idx_passport_number",
            "passport_number",
            postgresql_where="passport_number IS NOT NULL AND passport_number != ''",
        ),
        Index(
            "idx_image_hash", "image_hash", postgresql_where="image_hash IS NOT NULL"
        ),
        Index("idx_recognition_status", "mrz_valid", "passport_number", "birth_date"),
    )


class AccessLog(Base):
    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    action = Column(String(50), nullable=False)
    ip_address = Column(String(45))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_hash = Column(String(64), unique=True, index=True, nullable=False)
    key_prefix = Column(String(8), index=True, nullable=False)
    name = Column(String(100), nullable=False)
    owner_id = Column(Integer, ForeignKey("dashboard_users.id"), index=True)
    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_day = Column(Integer, default=10000)
    daily_usage = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True))


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    price_cents = Column(Integer, default=0)
    documents_per_month = Column(Integer, default=1000)
    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_day = Column(Integer, default=10000)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), index=True, nullable=False)
    document_id = Column(Integer, ForeignKey("passport_data.id"), index=True)
    action = Column(String(30), nullable=False)  # ocr_scan, face_verify, kyc_full
    processing_time_ms = Column(Integer, default=0)
    confidence = Column(Float, default=0.0)
    engine_used = Column(String(30))
    cost_cents = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (Index("idx_usage_api_key_date", "api_key_id", "created_at"),)
