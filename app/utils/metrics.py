from prometheus_client import (
    Counter,
    Histogram,
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


def metrics_endpoint():
    return generate_latest(REGISTRY), 200, {"Content-Type": CONTENT_TYPE_LATEST}
