"""Tests for all P0-P2 updates — no full app import, tests individual modules."""

import os
import sys
import json
import importlib.util

BASE = os.path.join(os.path.dirname(__file__), "..", "app")


def load_module(name, path):
    """Load a module directly without triggering app/__init__.py."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ============================================================
# P0-2: Re-export verification
# ============================================================
class TestReExports:
    def test_validator_reexport_content(self):
        path = os.path.join(BASE, "services", "validator.py")
        with open(path) as f:
            content = f.read()
        assert "from app.modules.validation import" in content
        assert "validation_engine" in content

    def test_mrz_parser_reexport_content(self):
        path = os.path.join(BASE, "services", "mrz_parser.py")
        with open(path) as f:
            content = f.read()
        assert "from app.modules.mrz import" in content
        assert "mrz_parser" in content

    def test_ocr_service_reexport_content(self):
        path = os.path.join(BASE, "services", "ocr_service.py")
        with open(path) as f:
            content = f.read()
        assert "from app.modules.ocr import" in content
        assert "ocr_engine" in content


# ============================================================
# P0-1: AntiFraudChecker integration
# ============================================================
class TestAntiFraudChecker:
    def test_pipeline_has_stage_0(self):
        path = os.path.join(BASE, "services", "pipeline.py")
        with open(path) as f:
            content = f.read()
        assert "Stage 0" in content
        assert "image_fraud" in content
        assert "anti_fraud_checker" in content
        assert "anti_fraud_checker.check" in content

    def test_anti_fraud_checker_file(self):
        path = os.path.join(BASE, "services", "anti_fraud.py")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "class AntiFraudChecker" in content
        assert "_detect_blur" in content
        assert "_detect_glare" in content
        assert "_detect_moire" in content


# ============================================================
# P1-5: Circuit Breaker
# ============================================================
class TestCircuitBreaker:
    def test_circuit_breaker_file(self):
        path = os.path.join(BASE, "services", "circuit_breaker.py")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "class CircuitBreaker" in content
        assert "class CircuitState" in content
        assert "CLOSED" in content
        assert "OPEN" in content
        assert "HALF_OPEN" in content
        assert "record_success" in content
        assert "record_failure" in content
        assert "allow_request" in content

    def test_circuit_breaker_in_fallback(self):
        path = os.path.join(BASE, "services", "ocr_fallback.py")
        with open(path) as f:
            content = f.read()
        assert "circuit_breakers" in content
        assert "cb.allow_request" in content
        assert "cb.record_success" in content
        assert "cb.record_failure" in content

    def test_circuit_breaker_config(self):
        path = os.path.join(BASE, "config.py")
        with open(path) as f:
            content = f.read()
        assert "CIRCUIT_FAILURE_THRESHOLD" in content
        assert "CIRCUIT_RECOVERY_TIMEOUT" in content
        assert "CIRCUIT_SUCCESS_THRESHOLD" in content


# ============================================================
# P1-6: API Key Auth
# ============================================================
class TestAPIKeyAuth:
    def test_api_key_auth_file(self):
        path = os.path.join(BASE, "api_key_auth.py")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "generate_api_key" in content
        assert "hash_api_key" in content
        assert "get_api_key" in content
        assert "check_rate_limit" in content
        assert "X-API-Key" in content

    def test_api_key_model(self):
        path = os.path.join(BASE, "models.py")
        with open(path) as f:
            content = f.read()
        assert "class APIKey" in content
        assert "key_hash" in content
        assert "key_prefix" in content
        assert "rate_limit_per_minute" in content
        assert "rate_limit_per_day" in content

    def test_admin_api_key_routes(self):
        path = os.path.join(BASE, "routers", "admin.py")
        with open(path) as f:
            content = f.read()
        assert '"/api-keys"' in content
        assert "create_api_key" in content
        assert "list_api_keys" in content
        assert "update_api_key" in content
        assert "revoke_api_key" in content


# ============================================================
# P1-7: Billing Model
# ============================================================
class TestBillingModel:
    def test_usage_record_model(self):
        path = os.path.join(BASE, "models.py")
        with open(path) as f:
            content = f.read()
        assert "class UsageRecord" in content
        assert "api_key_id" in content
        assert "document_id" in content
        assert "cost_cents" in content

    def test_subscription_plan_model(self):
        path = os.path.join(BASE, "models.py")
        with open(path) as f:
            content = f.read()
        assert "class SubscriptionPlan" in content
        assert "price_cents" in content
        assert "documents_per_month" in content

    def test_billing_routes(self):
        path = os.path.join(BASE, "routers", "analytics.py")
        with open(path) as f:
            content = f.read()
        assert "/billing/usage" in content
        assert "/billing/api-keys" in content

    def test_usage_in_celery_task(self):
        path = os.path.join(BASE, "tasks", "ocr_task.py")
        with open(path) as f:
            content = f.read()
        assert "UsageRecord" in content


# ============================================================
# P2-8: Ensemble OCR
# ============================================================
class TestEnsembleOCR:
    def test_ensemble_method(self):
        path = os.path.join(BASE, "services", "ocr_fallback.py")
        with open(path) as f:
            content = f.read()
        assert "def ensemble_merge" in content
        assert "weighted" in content.lower() or "weight" in content.lower()
        assert "line_votes" in content


# ============================================================
# P2-9: Multi-agent Pipeline
# ============================================================
class TestMultiAgentPipeline:
    def test_multi_agent_file(self):
        path = os.path.join(BASE, "tasks", "multi_agent.py")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "detect_document" in content
        assert "run_ocr" in content
        assert "extract_and_validate" in content
        assert "fraud_and_save" in content
        assert "build_ocr_chain" in content
        assert "chain(" in content


# ============================================================
# P2-10: Tracing
# ============================================================
class TestTracing:
    def test_tracing_file(self):
        path = os.path.join(BASE, "tracing.py")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "class TraceContext" in content
        assert "start_trace" in content
        assert "continue_trace" in content
        assert "inject_trace_headers" in content
        assert "extract_trace_id" in content
        assert "X-Trace-ID" in content

    def test_tracing_in_main(self):
        path = os.path.join(BASE, "main.py")
        with open(path) as f:
            content = f.read()
        assert "trace_context" in content
        assert "inject_trace_headers" in content
        assert "extract_trace_id" in content
        assert "X-Trace-ID" in content

    def test_circuit_breaker_endpoint(self):
        path = os.path.join(BASE, "main.py")
        with open(path) as f:
            content = f.read()
        assert "circuit-breakers" in content


# ============================================================
# P0-3: Prometheus Metrics
# ============================================================
class TestPrometheusMetrics:
    def test_celery_metrics(self):
        path = os.path.join(BASE, "utils", "metrics.py")
        with open(path) as f:
            content = f.read()
        assert "ocr_tasks_total" in content
        assert "ocr_task_duration" in content
        assert "ocr_confidence" in content
        assert "ocr_fraud_alerts_total" in content
        assert "ocr_documents_processed_total" in content
        assert "ocr_engine_fallback_total" in content
        assert "ocr_queue_size" in content


# ============================================================
# P0-4: Grafana Dashboards
# ============================================================
class TestGrafanaDashboards:
    def test_dashboard_files_exist(self):
        base = os.path.join(os.path.dirname(__file__), "..", "grafana", "dashboards")
        assert os.path.exists(os.path.join(base, "ocr-performance.json"))
        assert os.path.exists(os.path.join(base, "ocr-errors-fraud.json"))
        assert os.path.exists(os.path.join(base, "ocr-business-metrics.json"))

    def test_dashboard_valid_json(self):
        base = os.path.join(os.path.dirname(__file__), "..", "grafana", "dashboards")
        for fname in [
            "ocr-performance.json",
            "ocr-errors-fraud.json",
            "ocr-business-metrics.json",
        ]:
            with open(os.path.join(base, fname)) as f:
                data = json.load(f)
            assert "panels" in data
            assert "title" in data

    def test_datasource_exists(self):
        base = os.path.join(os.path.dirname(__file__), "..", "grafana", "datasources")
        assert os.path.exists(os.path.join(base, "prometheus.yml"))

    def test_docker_compose_has_grafana(self):
        compose_path = os.path.join(
            os.path.dirname(__file__), "..", "docker-compose.yml"
        )
        with open(compose_path) as f:
            content = f.read()
        assert "grafana" in content
        assert "prometheus" in content


# ============================================================
# Alembic Migrations
# ============================================================
class TestMigrations:
    def test_migration_files_exist(self):
        base = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions")
        assert os.path.exists(os.path.join(base, "002_api_keys.py"))
        assert os.path.exists(os.path.join(base, "003_billing.py"))

    def test_migration_content(self):
        base = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions")
        with open(os.path.join(base, "002_api_keys.py")) as f:
            content = f.read()
        assert "def upgrade" in content
        assert "def downgrade" in content
        assert "api_keys" in content

        with open(os.path.join(base, "003_billing.py")) as f:
            content = f.read()
        assert "def upgrade" in content
        assert "def downgrade" in content
        assert "usage_records" in content
        assert "subscription_plans" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
