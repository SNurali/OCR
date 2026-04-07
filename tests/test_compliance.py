import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import UserConsent, DataDeletionRequest, ComplianceAuditLog
from app.services.compliance import ComplianceService
from app.database import SessionLocal


@pytest.fixture
def db():
    """Create test database session"""
    db = SessionLocal()
    yield db
    db.close()


class TestComplianceService:
    def test_record_consent(self, db: Session):
        """Test recording user consent"""
        consent = ComplianceService.record_consent(
            db,
            user_id=1,
            consent_type="data_processing",
            given=True,
            ip_address="192.168.1.1",
        )

        assert consent.user_id == 1
        assert consent.consent_type == "data_processing"
        assert consent.given == True
        assert consent.ip_address == "192.168.1.1"

    def test_consent_expiration(self, db: Session):
        """Test consent expiration"""
        consent = ComplianceService.record_consent(
            db, user_id=1, consent_type="marketing", given=True, expires_days=1
        )

        # Consent should be valid
        is_valid = ComplianceService.is_consent_given(db, 1, "marketing")
        assert is_valid == True

    def test_get_user_consents(self, db: Session):
        """Test getting all user consents"""
        ComplianceService.record_consent(db, 1, "data_processing", True)
        ComplianceService.record_consent(db, 1, "marketing", False)

        consents = ComplianceService.get_user_consents(db, 1)

        assert "data_processing" in consents
        assert "marketing" in consents
        assert consents["data_processing"]["given"] == True
        assert consents["marketing"]["given"] == False

    def test_is_consent_given(self, db: Session):
        """Test checking if consent is given"""
        ComplianceService.record_consent(db, 1, "analytics", True)

        is_given = ComplianceService.is_consent_given(db, 1, "analytics")
        assert is_given == True

        is_given = ComplianceService.is_consent_given(db, 1, "nonexistent")
        assert is_given == False

    def test_request_data_deletion(self, db: Session):
        """Test requesting data deletion"""
        deletion_request = ComplianceService.request_data_deletion(
            db, user_id=1, request_type="full", reason="User requested deletion"
        )

        assert deletion_request.user_id == 1
        assert deletion_request.request_type == "full"
        assert deletion_request.status == "pending"

    def test_get_retention_policy(self, db: Session):
        """Test getting retention policy"""
        policy = ComplianceService.get_retention_policy(db, "ocr_results", "GDPR")

        assert policy is not None
        assert policy.data_type == "ocr_results"
        assert policy.jurisdiction == "GDPR"
        assert policy.retention_days == 2555  # 7 years

    def test_log_audit_event(self, db: Session):
        """Test logging audit event"""
        ComplianceService.log_audit_event(
            db,
            user_id=1,
            action="data_access",
            resource_type="ocr_result",
            resource_id=123,
            ip_address="192.168.1.1",
        )

        logs = ComplianceService.get_audit_trail(db, 1, days=1)

        assert len(logs) > 0
        assert logs[0].action == "data_access"
        assert logs[0].resource_type == "ocr_result"

    def test_log_data_access(self, db: Session):
        """Test logging data access"""
        ComplianceService.log_data_access(
            db,
            user_id=1,
            accessed_by_user_id=2,
            data_type="ocr_result",
            record_id=123,
            access_type="read",
            purpose="verification",
        )

        logs = ComplianceService.get_data_access_history(db, 1, days=1)

        assert len(logs) > 0
        assert logs[0].data_type == "ocr_result"
        assert logs[0].accessed_by_user_id == 2

    def test_get_audit_trail(self, db: Session):
        """Test getting audit trail"""
        # Log multiple events
        for i in range(3):
            ComplianceService.log_audit_event(db, user_id=1, action=f"action_{i}")

        logs = ComplianceService.get_audit_trail(db, 1, days=1)

        assert len(logs) >= 3

    def test_get_data_access_history(self, db: Session):
        """Test getting data access history"""
        # Log multiple accesses
        for i in range(3):
            ComplianceService.log_data_access(
                db, user_id=1, accessed_by_user_id=2, data_type=f"type_{i}"
            )

        logs = ComplianceService.get_data_access_history(db, 1, days=1)

        assert len(logs) >= 3

    def test_export_user_data(self, db: Session):
        """Test exporting user data"""
        # Record some data
        ComplianceService.record_consent(db, 1, "data_processing", True)
        ComplianceService.log_audit_event(db, 1, "test_action")

        exported_data = ComplianceService.export_user_data(db, 1)

        assert exported_data["user_id"] == 1
        assert "exported_at" in exported_data
        assert "ocr_results" in exported_data
        assert "face_verifications" in exported_data
        assert "consents" in exported_data
        assert "audit_trail" in exported_data

    def test_cleanup_expired_data(self, db: Session):
        """Test cleanup of expired data"""
        stats = ComplianceService.cleanup_expired_data(db)

        assert "ocr_results_deleted" in stats
        assert "face_verifications_deleted" in stats
        assert "embeddings_deleted" in stats
        assert "access_logs_deleted" in stats

    def test_consent_update(self, db: Session):
        """Test updating existing consent"""
        # Record initial consent
        consent1 = ComplianceService.record_consent(db, 1, "test_consent", True)

        # Update consent
        consent2 = ComplianceService.record_consent(db, 1, "test_consent", False)

        # Should be same record, updated
        assert consent1.id == consent2.id
        assert consent2.given == False

    def test_retention_policy_ruz(self, db: Session):
        """Test Uzbek retention policy"""
        policy = ComplianceService.get_retention_policy(db, "ocr_results", "RUZ")

        assert policy is not None
        assert policy.jurisdiction == "RUZ"
        assert policy.retention_days == 1825  # 5 years

    def test_multiple_jurisdictions(self, db: Session):
        """Test policies for multiple jurisdictions"""
        gdpr_policy = ComplianceService.get_retention_policy(
            db, "face_verifications", "GDPR"
        )
        ruz_policy = ComplianceService.get_retention_policy(
            db, "face_verifications", "RUZ"
        )

        assert gdpr_policy.retention_days == 2555
        assert ruz_policy.retention_days == 1825
