from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "OCR Passport Service"
    VERSION: str = "2.1.0"

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

    # OCR Settings
    OCR_LANGUAGES: str = "uzb+rus+eng"
    OCR_CONFIDENCE_THRESHOLD: float = 0.4

    # File Settings
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: list = ["jpg", "jpeg", "png", "tiff", "bmp", "webp"]
    UPLOAD_DIR: str = "/app/uploads/passports"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # VLM (Vision-Language Model)
    VLM_ENABLED: bool = True
    VLM_PROVIDER: str = "ollama"  # 'groq', 'qwen', 'gemini', or 'ollama'

    # Groq (Free & Fast - Llama 3.2 Vision)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.2-11b-vision-preview"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # Google Gemini (резерв)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Alibaba Qwen-VL (Cloud Plan)
    QWEN_API_KEY: str = ""
    QWEN_MODEL: str = "qwen3.5-plus"
    QWEN_BASE_URL: str = "https://coding-intl.dashscope.aliyuncs.com/v1"

    # Ollama (локально или Cloud - Nemotron)
    OLLAMA_API_KEY: str = ""
    OLLAMA_MODEL: str = "nemotron-3-super:cloud"
    OLLAMA_BASE_URL: str = "https://ollama.com/v1"  # Cloud API

    VLM_TIMEOUT: int = 60

    # Anti-Fraud (image quality checks)
    ANTI_FRAUD_BLUR_THRESHOLD: int = 100
    ANTI_FRAUD_GLARE_THRESHOLD: float = 0.8
    ANTI_FRAUD_MOIRE_THRESHOLD: int = 50

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
