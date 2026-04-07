from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "OCR Passport Service"
    VERSION: str = "2.2.0"

    # PostgreSQL
    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_USER: str = "ocr_user"
    DB_PASSWORD: str = "ocr_secure_password"
    DB_NAME: str = "ocr_service"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40

    # Redis (для Celery)
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # JWT
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"

    # Encryption
    ENCRYPTION_KEY: str = "your-32-byte-encryption-key-here!"

    # File Settings
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: list = ["jpg", "jpeg", "png", "tiff", "bmp", "webp"]
    UPLOAD_DIR: str = "/app/uploads/passports"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Qwen VLM (Alibaba Cloud — DashScope)
    # Единственный провайдер OCR/Vision
    QWEN_API_KEY: str = ""
    QWEN_MODEL: str = "qwen3.5-plus"
    QWEN_BASE_URL: str = "https://coding-intl.dashscope.aliyuncs.com/v1"
    VLM_TIMEOUT: int = 60

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
