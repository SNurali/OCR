-- ClickHouse Schema for OCR Service Analytics
-- Real-time analytics and metrics storage

CREATE DATABASE IF NOT EXISTS ocr_service;

-- OCR Metrics Table (for analytics)
CREATE TABLE IF NOT EXISTS ocr_service.ocr_metrics (
    timestamp DateTime DEFAULT now(),
    task_id String,
    user_id UInt32,
    document_type String,
    confidence Float32,
    fraud_score Float32,
    processing_time_ms UInt32,
    mrz_valid UInt8,
    ocr_engine String,
    language String,
    status String
) ENGINE = MergeTree()
ORDER BY (timestamp, user_id)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 7 YEAR;

-- Face Verification Metrics Table
CREATE TABLE IF NOT EXISTS ocr_service.face_metrics (
    timestamp DateTime DEFAULT now(),
    task_id String,
    user_id UInt32,
    match UInt8,
    similarity Float32,
    liveness_score Float32,
    anti_spoof_score Float32,
    doc_quality_score Float32,
    selfie_quality_score Float32,
    confidence Float32,
    fraud_risk String,
    processing_time_ms UInt32,
    status String
) ENGINE = MergeTree()
ORDER BY (timestamp, user_id)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 7 YEAR;

-- Risk Engine Decisions Table
CREATE TABLE IF NOT EXISTS ocr_service.risk_decisions (
    timestamp DateTime DEFAULT now(),
    task_id String,
    user_id UInt32,
    decision String,
    risk_score Float32,
    confidence Float32,
    face_similarity Float32,
    liveness_score Float32,
    anti_spoof_score Float32,
    ocr_confidence Float32,
    penalties Array(String),
    processing_time_ms UInt32
) ENGINE = MergeTree()
ORDER BY (timestamp, user_id)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 7 YEAR;

-- Fraud Events Table
CREATE TABLE IF NOT EXISTS ocr_service.fraud_events (
    timestamp DateTime DEFAULT now(),
    task_id String,
    user_id UInt32,
    event_type String,
    face_hash String,
    document_hash String,
    ip_address String,
    risk_score Float32,
    details String
) ENGINE = MergeTree()
ORDER BY (timestamp, user_id)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 7 YEAR;

-- API Request Metrics Table
CREATE TABLE IF NOT EXISTS ocr_service.api_metrics (
    timestamp DateTime DEFAULT now(),
    endpoint String,
    method String,
    status_code UInt16,
    response_time_ms UInt32,
    user_id UInt32,
    ip_address String,
    error_message String
) ENGINE = MergeTree()
ORDER BY (timestamp, endpoint)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 1 YEAR;

-- System Performance Metrics Table
CREATE TABLE IF NOT EXISTS ocr_service.system_metrics (
    timestamp DateTime DEFAULT now(),
    metric_name String,
    metric_value Float32,
    labels Map(String, String)
) ENGINE = MergeTree()
ORDER BY (timestamp, metric_name)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 1 YEAR;

-- Audit Trail Table
CREATE TABLE IF NOT EXISTS ocr_service.audit_trail (
    timestamp DateTime DEFAULT now(),
    user_id UInt32,
    action String,
    resource_type String,
    resource_id UInt32,
    old_value String,
    new_value String,
    ip_address String,
    reason String
) ENGINE = MergeTree()
ORDER BY (timestamp, user_id)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 7 YEAR;

-- Data Access Log Table
CREATE TABLE IF NOT EXISTS ocr_service.data_access_log (
    timestamp DateTime DEFAULT now(),
    user_id UInt32,
    accessed_by_user_id UInt32,
    data_type String,
    record_id UInt32,
    access_type String,
    purpose String,
    ip_address String
) ENGINE = MergeTree()
ORDER BY (timestamp, user_id)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 7 YEAR;

-- Compliance Events Table
CREATE TABLE IF NOT EXISTS ocr_service.compliance_events (
    timestamp DateTime DEFAULT now(),
    event_type String,
    user_id UInt32,
    jurisdiction String,
    description String,
    status String
) ENGINE = MergeTree()
ORDER BY (timestamp, event_type)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 7 YEAR;

-- Model Performance Table
CREATE TABLE IF NOT EXISTS ocr_service.model_performance (
    timestamp DateTime DEFAULT now(),
    model_name String,
    model_version String,
    metric_name String,
    metric_value Float32,
    sample_size UInt32
) ENGINE = MergeTree()
ORDER BY (timestamp, model_name)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 2 YEAR;

-- Create materialized views for common queries

-- Daily OCR Summary
CREATE MATERIALIZED VIEW IF NOT EXISTS ocr_service.ocr_daily_summary
ENGINE = SummingMergeTree()
ORDER BY (date, document_type)
PARTITION BY toYYYYMM(date)
AS SELECT
    toDate(timestamp) as date,
    document_type,
    count() as total_requests,
    sum(if(status = 'completed', 1, 0)) as successful,
    sum(if(status = 'failed', 1, 0)) as failed,
    avg(confidence) as avg_confidence,
    avg(processing_time_ms) as avg_processing_time,
    sum(if(fraud_score > 0.5, 1, 0)) as fraud_detected
FROM ocr_service.ocr_metrics
GROUP BY date, document_type;

-- Daily Face Verification Summary
CREATE MATERIALIZED VIEW IF NOT EXISTS ocr_service.face_daily_summary
ENGINE = SummingMergeTree()
ORDER BY (date, status)
PARTITION BY toYYYYMM(date)
AS SELECT
    toDate(timestamp) as date,
    status,
    count() as total_requests,
    sum(match) as matches,
    sum(if(match = 0, 1, 0)) as mismatches,
    avg(similarity) as avg_similarity,
    avg(liveness_score) as avg_liveness,
    avg(anti_spoof_score) as avg_anti_spoof,
    avg(processing_time_ms) as avg_processing_time
FROM ocr_service.face_metrics
GROUP BY date, status;

-- Daily Risk Decisions Summary
CREATE MATERIALIZED VIEW IF NOT EXISTS ocr_service.risk_daily_summary
ENGINE = SummingMergeTree()
ORDER BY (date, decision)
PARTITION BY toYYYYMM(date)
AS SELECT
    toDate(timestamp) as date,
    decision,
    count() as total_decisions,
    avg(risk_score) as avg_risk_score,
    avg(confidence) as avg_confidence,
    avg(processing_time_ms) as avg_processing_time
FROM ocr_service.risk_decisions
GROUP BY date, decision;

-- Hourly API Performance
CREATE MATERIALIZED VIEW IF NOT EXISTS ocr_service.api_hourly_performance
ENGINE = SummingMergeTree()
ORDER BY (hour, endpoint)
PARTITION BY toYYYYMM(toDate(timestamp))
AS SELECT
    toStartOfHour(timestamp) as hour,
    endpoint,
    method,
    count() as total_requests,
    sum(if(status_code >= 200 AND status_code < 300, 1, 0)) as successful,
    sum(if(status_code >= 400, 1, 0)) as errors,
    avg(response_time_ms) as avg_response_time,
    max(response_time_ms) as max_response_time
FROM ocr_service.api_metrics
GROUP BY hour, endpoint, method;
