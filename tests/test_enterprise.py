import pytest
from sqlalchemy.orm import Session
from app.models import FeatureFlag, ModelVersion, ShadowModeResult
from app.services.feature_flags import FeatureFlagService
from app.services.model_versioning import ModelVersioningService
from app.services.shadow_mode import ShadowModeService
from app.database import SessionLocal


@pytest.fixture
def db():
    """Create test database session"""
    db = SessionLocal()
    yield db
    db.close()


class TestFeatureFlagService:
    def test_set_and_get_flag(self, db: Session):
        """Test setting and getting feature flag"""
        flag = FeatureFlagService.set_flag(db, "TEST_FLAG", True, 100, updated_by=1)

        assert flag.flag_name == "TEST_FLAG"
        assert flag.enabled == True
        assert flag.rollout_percentage == 100

    def test_get_flag_disabled(self, db: Session):
        """Test getting disabled flag"""
        FeatureFlagService.set_flag(db, "DISABLED_FLAG", False, 0)

        is_enabled = FeatureFlagService.get_flag(db, "DISABLED_FLAG")
        assert is_enabled == False

    def test_rollout_percentage(self, db: Session):
        """Test rollout percentage logic"""
        FeatureFlagService.set_flag(db, "ROLLOUT_FLAG", True, 50)

        # Test multiple times to verify rollout works
        results = [FeatureFlagService.get_flag(db, "ROLLOUT_FLAG") for _ in range(100)]

        # Should have mix of True/False (approximately 50%)
        true_count = sum(results)
        assert 20 < true_count < 80  # Allow some variance

    def test_get_all_flags(self, db: Session):
        """Test getting all flags"""
        FeatureFlagService.set_flag(db, "FLAG1", True)
        FeatureFlagService.set_flag(db, "FLAG2", False)

        flags = FeatureFlagService.get_all_flags(db)
        flag_names = [f.flag_name for f in flags]

        assert "FLAG1" in flag_names
        assert "FLAG2" in flag_names

    def test_invalidate_cache(self, db: Session):
        """Test cache invalidation"""
        FeatureFlagService.set_flag(db, "CACHE_FLAG", True)
        FeatureFlagService.invalidate_cache("CACHE_FLAG")

        # Should still work after cache invalidation
        is_enabled = FeatureFlagService.get_flag(db, "CACHE_FLAG")
        assert is_enabled == True


class TestModelVersioningService:
    def test_register_model(self, db: Session):
        """Test registering a model version"""
        model = ModelVersioningService.register_model(
            db, "face_recognition", "v1.0.0", "face", {"threshold": 0.6}, deployed_by=1
        )

        assert model.model_name == "face_recognition"
        assert model.version == "v1.0.0"
        assert model.status == "active"

    def test_get_active_model(self, db: Session):
        """Test getting active model"""
        ModelVersioningService.register_model(
            db, "ocr_paddle", "v2.0.0", "ocr", deployed_by=1
        )

        active = ModelVersioningService.get_active_model(db, "ocr_paddle")

        assert active is not None
        assert active.version == "v2.0.0"
        assert active.status == "active"

    def test_list_model_versions(self, db: Session):
        """Test listing model versions"""
        ModelVersioningService.register_model(
            db, "yolo", "v1.0.0", "detection", deployed_by=1
        )
        ModelVersioningService.register_model(
            db, "yolo", "v1.1.0", "detection", deployed_by=1
        )

        versions = ModelVersioningService.list_model_versions(db, "yolo")

        assert len(versions) >= 2
        version_nums = [v.version for v in versions]
        assert "v1.0.0" in version_nums
        assert "v1.1.0" in version_nums

    def test_set_model_status(self, db: Session):
        """Test updating model status"""
        ModelVersioningService.register_model(
            db, "test_model", "v1.0.0", "test", deployed_by=1
        )

        updated = ModelVersioningService.set_model_status(
            db, "test_model", "v1.0.0", "deprecated"
        )

        assert updated.status == "deprecated"

    def test_update_model_metrics(self, db: Session):
        """Test updating model metrics"""
        ModelVersioningService.register_model(
            db, "metrics_model", "v1.0.0", "test", deployed_by=1
        )

        metrics = {"accuracy": 0.95, "f1_score": 0.92}
        updated = ModelVersioningService.update_model_metrics(
            db, "metrics_model", "v1.0.0", metrics
        )

        assert updated.metrics["accuracy"] == 0.95


class TestShadowModeService:
    def test_record_comparison(self, db: Session):
        """Test recording shadow mode comparison"""
        prod_result = {"confidence": 0.95, "decision": "approve"}
        shadow_result = {"confidence": 0.94, "decision": "approve"}

        result = ShadowModeService.record_comparison(
            db,
            "task_123",
            user_id=1,
            pipeline_stage="ocr",
            production_result=prod_result,
            shadow_result=shadow_result,
        )

        assert result.task_id == "task_123"
        assert result.pipeline_stage == "ocr"
        assert result.divergence_detected == False

    def test_divergence_detection(self, db: Session):
        """Test divergence detection"""
        prod_result = {"confidence": 0.95, "decision": "approve"}
        shadow_result = {"confidence": 0.80, "decision": "review"}

        result = ShadowModeService.record_comparison(
            db,
            "task_456",
            user_id=1,
            pipeline_stage="face_verification",
            production_result=prod_result,
            shadow_result=shadow_result,
        )

        assert result.divergence_detected == True
        assert len(result.comparison_metrics["differences"]) > 0

    def test_get_divergence_report(self, db: Session):
        """Test getting divergence report"""
        # Create divergent result
        ShadowModeService.record_comparison(
            db,
            "task_div",
            user_id=1,
            pipeline_stage="ocr",
            production_result={"confidence": 0.9},
            shadow_result={"confidence": 0.7},
        )

        report = ShadowModeService.get_divergence_report(db, "ocr")

        assert len(report) > 0
        assert any(r.task_id == "task_div" for r in report)

    def test_get_stage_statistics(self, db: Session):
        """Test getting stage statistics"""
        # Create multiple comparisons
        for i in range(5):
            ShadowModeService.record_comparison(
                db,
                f"task_{i}",
                user_id=1,
                pipeline_stage="risk_engine",
                production_result={"confidence": 0.9},
                shadow_result={"confidence": 0.89},
            )

        stats = ShadowModeService.get_stage_statistics(db, "risk_engine")

        assert stats["pipeline_stage"] == "risk_engine"
        assert stats["total_comparisons"] >= 5
        assert stats["divergence_rate"] >= 0

    def test_similarity_score_calculation(self, db: Session):
        """Test similarity score calculation"""
        prod_result = {"confidence": 0.95, "similarity": 0.92, "decision": "approve"}
        shadow_result = {"confidence": 0.94, "similarity": 0.91, "decision": "approve"}

        result = ShadowModeService.record_comparison(
            db,
            "task_sim",
            user_id=1,
            pipeline_stage="face_verification",
            production_result=prod_result,
            shadow_result=shadow_result,
        )

        similarity = result.comparison_metrics["similarity_score"]
        assert 0 <= similarity <= 1
