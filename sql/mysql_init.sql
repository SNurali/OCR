-- MySQL Schema for OCR Service
-- Uzbekistan Compliance

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    refresh_token_hash VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dashboard Users Table (for admin/airport staff)
CREATE TABLE IF NOT EXISTS dashboard_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- OCR Results Table
CREATE TABLE IF NOT EXISTS ocr_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    task_id VARCHAR(36) UNIQUE,
    document_type VARCHAR(50) NOT NULL,
    first_name_enc TEXT,
    last_name_enc TEXT,
    middle_name VARCHAR(100),
    birth_date_enc TEXT,
    gender VARCHAR(10),
    nationality VARCHAR(50),
    passport_number_enc TEXT,
    passport_series VARCHAR(20),
    issue_date VARCHAR(20),
    expiry_date VARCHAR(20),
    issued_by VARCHAR(200),
    pinfl_enc TEXT,
    mrz_line1 TEXT,
    mrz_line2 TEXT,
    mrz_line3 TEXT,
    photo_base64 LONGTEXT,
    confidence FLOAT,
    raw_text LONGTEXT,
    mrz_valid BOOLEAN DEFAULT FALSE,
    all_checks_valid BOOLEAN DEFAULT FALSE,
    fraud_score FLOAT DEFAULT 0.0,
    fraud_blocked BOOLEAN DEFAULT FALSE,
    field_confidence_json JSON,
    processing_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_task_id (task_id),
    INDEX idx_created_at (created_at),
    INDEX idx_document_type (document_type),
    INDEX idx_nationality (nationality)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Passport Scans Table (for airport system)
CREATE TABLE IF NOT EXISTS passport_scans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ocr_result_id INT,
    scan_filename VARCHAR(255) NOT NULL,
    scan_path VARCHAR(500) NOT NULL,
    scan_type VARCHAR(20) NOT NULL,
    file_size INT,
    mime_type VARCHAR(50),
    uploaded_by INT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ocr_result_id) REFERENCES ocr_results(id),
    FOREIGN KEY (uploaded_by) REFERENCES dashboard_users(id),
    INDEX idx_ocr_result_id (ocr_result_id),
    INDEX idx_uploaded_at (uploaded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Task Status Table
CREATE TABLE IF NOT EXISTS task_statuses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(36) UNIQUE NOT NULL,
    user_id INT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error TEXT,
    result_id INT,
    result_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_status (status),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Access Logs Table
CREATE TABLE IF NOT EXISTS access_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(50) NOT NULL,
    resource_id INT,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    INDEX idx_action (action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Face Verifications Table
CREATE TABLE IF NOT EXISTS face_verifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    task_id VARCHAR(36) UNIQUE,
    idempotency_key VARCHAR(64) UNIQUE,
    match BOOLEAN DEFAULT FALSE,
    similarity FLOAT,
    liveness_score FLOAT,
    anti_spoof_score FLOAT,
    doc_quality_score FLOAT,
    selfie_quality_score FLOAT,
    confidence FLOAT,
    fraud_risk VARCHAR(20) DEFAULT 'high',
    risk_factors TEXT,
    doc_face_detected BOOLEAN DEFAULT FALSE,
    self_face_detected BOOLEAN DEFAULT FALSE,
    threshold_used FLOAT,
    doc_embedding_enc TEXT,
    self_embedding_enc TEXT,
    liveness_details TEXT,
    anti_spoof_details TEXT,
    doc_quality_details TEXT,
    self_quality_details TEXT,
    processing_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_task_id (task_id),
    INDEX idx_idempotency (idempotency_key),
    INDEX idx_match (match),
    INDEX idx_fraud_risk (fraud_risk)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Fraud Events Table
CREATE TABLE IF NOT EXISTS fraud_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    task_id VARCHAR(36),
    event_type VARCHAR(50) NOT NULL,
    face_hash VARCHAR(64),
    document_hash VARCHAR(64),
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    risk_score FLOAT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_event_type (event_type),
    INDEX idx_face_hash (face_hash),
    INDEX idx_doc_hash (document_hash),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Attempt History Table
CREATE TABLE IF NOT EXISTS attempt_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    task_id VARCHAR(36),
    idempotency_key VARCHAR(64),
    attempt_type VARCHAR(20) NOT NULL,
    result VARCHAR(20),
    similarity FLOAT,
    fraud_risk VARCHAR(20),
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_task_id (task_id),
    INDEX idx_created_at (created_at),
    INDEX idx_attempt_type (attempt_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Embedding Cache Table
CREATE TABLE IF NOT EXISTS embedding_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    image_hash VARCHAR(64) UNIQUE NOT NULL,
    embedding_enc LONGTEXT NOT NULL,
    face_quality FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    INDEX idx_image_hash (image_hash),
    INDEX idx_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Feature Flags Table
CREATE TABLE IF NOT EXISTS feature_flags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    flag_name VARCHAR(100) UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    description TEXT,
    rollout_percentage INT DEFAULT 100,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by INT,
    INDEX idx_flag_name (flag_name),
    INDEX idx_enabled (enabled),
    FOREIGN KEY (updated_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Model Versions Table
CREATE TABLE IF NOT EXISTS model_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    config JSON,
    metrics JSON,
    deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deployed_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_model_version (model_name, version),
    INDEX idx_model_name (model_name),
    INDEX idx_status (status),
    INDEX idx_deployed_at (deployed_at),
    FOREIGN KEY (deployed_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Shadow Mode Results Table
CREATE TABLE IF NOT EXISTS shadow_mode_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL,
    user_id INT,
    pipeline_stage VARCHAR(50) NOT NULL,
    production_result JSON NOT NULL,
    shadow_result JSON NOT NULL,
    comparison_metrics JSON,
    divergence_detected BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_user_id (user_id),
    INDEX idx_pipeline_stage (pipeline_stage),
    INDEX idx_divergence (divergence_detected),
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- User Consents Table
CREATE TABLE IF NOT EXISTS user_consents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    consent_type VARCHAR(50) NOT NULL,
    consent_version VARCHAR(20) NOT NULL,
    given BOOLEAN DEFAULT FALSE,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    consent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_consent_type (consent_type),
    INDEX idx_given (given),
    UNIQUE KEY unique_user_consent (user_id, consent_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Data Retention Policies Table
CREATE TABLE IF NOT EXISTS data_retention_policies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    data_type VARCHAR(100) NOT NULL,
    retention_days INT NOT NULL,
    jurisdiction VARCHAR(50) NOT NULL,
    description TEXT,
    auto_delete BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_data_policy (data_type, jurisdiction),
    INDEX idx_data_type (data_type),
    INDEX idx_jurisdiction (jurisdiction)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Data Deletion Requests Table
CREATE TABLE IF NOT EXISTS data_deletion_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    request_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    reason TEXT,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    deleted_records INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_requested_at (requested_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Compliance Audit Log Table
CREATE TABLE IF NOT EXISTS compliance_audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id INT,
    old_value TEXT,
    new_value TEXT,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_resource_type (resource_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Data Access Log Table
CREATE TABLE IF NOT EXISTS data_access_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    accessed_by_user_id INT,
    data_type VARCHAR(50) NOT NULL,
    record_id INT,
    access_type VARCHAR(20),
    purpose VARCHAR(100),
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (accessed_by_user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_accessed_by (accessed_by_user_id),
    INDEX idx_data_type (data_type),
    INDEX idx_accessed_at (accessed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default admin user
INSERT INTO users (username, hashed_password) VALUES
('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYILp92S.0i')
ON DUPLICATE KEY UPDATE username=username;

-- Insert default dashboard admin
INSERT INTO dashboard_users (username, hashed_password, role) VALUES
('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYILp92S.0i', 'admin')
ON DUPLICATE KEY UPDATE username=username;

-- Insert feature flags
INSERT INTO feature_flags (flag_name, enabled, description, rollout_percentage) VALUES
('FEATURE_LIVENESS', TRUE, 'Enable liveness detection in face verification', 100),
('FEATURE_FACE_MATCH', TRUE, 'Enable face matching against document', 100),
('FEATURE_ANTI_SPOOF', TRUE, 'Enable anti-spoofing detection', 100),
('FEATURE_SHADOW_MODE', FALSE, 'Enable shadow mode for model comparison', 0),
('FEATURE_HYBRID_OCR', TRUE, 'Enable hybrid OCR fallback chain', 100),
('FEATURE_FRAUD_DETECTION', TRUE, 'Enable fraud detection engine', 100)
ON DUPLICATE KEY UPDATE flag_name=flag_name;

-- Insert retention policies
INSERT INTO data_retention_policies (data_type, retention_days, jurisdiction, description, auto_delete) VALUES
('ocr_results', 2555, 'GDPR', 'OCR results retention (7 years for financial records)', TRUE),
('ocr_results', 1825, 'RUZ', 'OCR results retention (5 years per Uzbek law)', TRUE),
('face_verifications', 2555, 'GDPR', 'Face verification data (7 years)', TRUE),
('face_verifications', 1825, 'RUZ', 'Face verification data (5 years)', TRUE),
('fraud_events', 2555, 'GDPR', 'Fraud event logs (7 years)', TRUE),
('fraud_events', 1825, 'RUZ', 'Fraud event logs (5 years)', TRUE),
('access_logs', 365, 'GDPR', 'Access logs (1 year)', TRUE),
('access_logs', 365, 'RUZ', 'Access logs (1 year)', TRUE),
('embeddings', 90, 'GDPR', 'Face embeddings (90 days)', TRUE),
('embeddings', 90, 'RUZ', 'Face embeddings (90 days)', TRUE)
ON DUPLICATE KEY UPDATE data_type=data_type;
