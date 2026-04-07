import pytest
from app.utils.feature_flags import FeatureFlags
from app.utils.model_registry import ModelRegistry


class TestFeatureFlags:
    @pytest.fixture
    def flags(self):
        ff = FeatureFlags()
        ff._overrides = {}
        return ff

    def test_default_values(self, flags):
        assert flags.is_enabled("FEATURE_LIVENESS") is True
        assert flags.is_enabled("FEATURE_FACE_MATCH") is True
        assert flags.is_enabled("FEATURE_ANTI_SPOOF") is True
        assert flags.is_enabled("FEATURE_SHADOW_MODE") is False

    def test_set_override(self, flags):
        flags.set_override("FEATURE_LIVENESS", False)
        assert flags.is_enabled("FEATURE_LIVENESS") is False

    def test_clear_override(self, flags):
        flags.set_override("FEATURE_LIVENESS", False)
        flags.clear_override("FEATURE_LIVENESS")
        assert flags.is_enabled("FEATURE_LIVENESS") is True

    def test_get_value(self, flags):
        assert flags.get_value("FEATURE_LIVENESS") is True

    def test_get_all(self, flags):
        all_flags = flags.get_all()
        assert "FEATURE_LIVENESS" in all_flags
        assert "FEATURE_FACE_MATCH" in all_flags

    def test_to_json_from_json(self, flags):
        json_str = flags.to_json()
        assert "FEATURE_LIVENESS" in json_str

    def test_unknown_flag_default(self, flags):
        assert flags.is_enabled("UNKNOWN_FLAG", default=True) is True
        assert flags.is_enabled("UNKNOWN_FLAG", default=False) is False


class TestModelRegistry:
    @pytest.fixture
    def registry(self):
        return ModelRegistry()

    def test_get_model(self, registry):
        model = registry.get_model("face_recognition")
        assert model is not None
        assert model["name"] == "buffalo_l"

    def test_get_unknown_model(self, registry):
        assert registry.get_model("nonexistent") is None

    def test_set_loaded(self, registry):
        registry.set_loaded("face_recognition")
        model = registry.get_model("face_recognition")
        assert model["status"] == "active"
        assert model["loaded_at"] is not None

    def test_set_fallback(self, registry):
        registry.set_fallback("yolo_detection")
        model = registry.get_model("yolo_detection")
        assert model["status"] == "fallback"

    def test_get_active_versions(self, registry):
        versions = registry.get_active_versions()
        assert "face_recognition" in versions
        assert "buffalo_l" in versions["face_recognition"]

    def test_get_audit_info(self, registry):
        audit = registry.get_audit_info()
        assert "face_recognition" in audit
        info = audit["face_recognition"]
        assert "name" in info
        assert "version" in info
        assert "framework" in info
        assert "status" in info

    def test_register_model(self, registry):
        registry.register_model(
            "custom_model",
            name="custom",
            version="2.0.0",
            framework="pytorch",
        )
        model = registry.get_model("custom_model")
        assert model["name"] == "custom"
        assert model["version"] == "2.0.0"
        assert model["framework"] == "pytorch"
