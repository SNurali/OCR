from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

ocr_requests_total = Counter(
    "ocr_requests_total",
    "Total OCR requests",
    ["endpoint", "status"],
)

ocr_success_total = Counter(
    "ocr_success_total",
    "Total successful OCR operations",
)

ocr_errors_total = Counter(
    "ocr_errors_total",
    "Total OCR errors",
    ["reason"],
)

ocr_processing_time = Histogram(
    "ocr_processing_time_seconds",
    "OCR processing time in seconds",
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

ocr_mrz_valid_total = Counter(
    "ocr_mrz_valid_total",
    "Total MRZ validations",
    ["valid"],
)

ocr_tasks_total = Counter(
    "ocr_celery_tasks_total",
    "Total Celery OCR tasks",
    ["status", "engine_used"],
)

ocr_task_duration = Histogram(
    "ocr_celery_task_duration_seconds",
    "Celery OCR task duration in seconds",
    buckets=(1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

ocr_confidence = Histogram(
    "ocr_confidence_score",
    "OCR confidence score distribution",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0),
)

ocr_fraud_alerts_total = Counter(
    "ocr_fraud_alerts_total",
    "Total fraud alerts triggered",
    ["alert_type", "severity"],
)

ocr_documents_processed_total = Counter(
    "ocr_documents_processed_total",
    "Total documents processed",
    ["document_type", "final_status"],
)

ocr_queue_size = Gauge(
    "ocr_celery_queue_size",
    "Current Celery queue depth",
    ["queue_name"],
)

ocr_engine_fallback_total = Counter(
    "ocr_engine_fallback_total",
    "Total engine fallbacks",
    ["from_engine", "to_engine"],
)


def metrics_endpoint():
    return generate_latest(REGISTRY), 200, {"Content-Type": CONTENT_TYPE_LATEST}
