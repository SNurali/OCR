-- PostgreSQL initialization script for OCR Service

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create indexes will be handled by SQLAlchemy models
-- This file is just for extensions and initial setup

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE ocr_service TO ocr_user;
