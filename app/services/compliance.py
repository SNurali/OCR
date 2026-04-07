from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import (
    UserConsent,
    DataRetentionPolicy,
    DataDeletionRequest,
    ComplianceAuditLog,
    DataAccessLog,
    OCRResult,
    FaceVerification,
    FraudEvent,
    AccessLog,
    EmbeddingCache,
)
import logging

logger = logging.getLogger(__name__)


class ComplianceService:
    """Handle GDPR and Uzbek compliance requirements"""

    @staticmethod
    def record_consent(
        db: Session,
        user_id: int,
        consent_type: str,
        given: bool,
        ip_address: str = None,
        user_agent: str = None,
        expires_days: int = 365,
    ) -> UserConsent:
        """Record user consent (GDPR Article 7)"""

        # Check if consent already exists
        existing = (
            db.query(UserConsent)
            .filter(
                UserConsent.user_id == user_id, UserConsent.consent_type == consent_type
            )
            .first()
        )

        expires_at = datetime.utcnow() + timedelta(days=expires_days)

        if existing:
            existing.given = given
            existing.consent_date = datetime.utcnow()
            existing.expires_at = expires_at
            existing.ip_address = ip_address
            existing.user_agent = user_agent
            db.commit()
            db.refresh(existing)
            return existing

        consent = UserConsent(
            user_id=user_id,
            consent_type=consent_type,
            consent_version="1.0",
            given=given,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
        )
        db.add(consent)
        db.commit()
        db.refresh(consent)

        logger.info(
            f"Consent recorded for user {user_id}: {consent_type}={given}",
            extra={"user_id": user_id, "consent_type": consent_type},
        )

        return consent

    @staticmethod
    def get_user_consents(db: Session, user_id: int) -> dict:
        """Get all consents for a user"""
        consents = db.query(UserConsent).filter(UserConsent.user_id == user_id).all()

        return {
            c.consent_type: {
                "given": c.given,
                "date": c.consent_date.isoformat(),
                "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            }
            for c in consents
        }

    @staticmethod
    def is_consent_given(db: Session, user_id: int, consent_type: str) -> bool:
        """Check if user has given specific consent"""
        consent = (
            db.query(UserConsent)
            .filter(
                UserConsent.user_id == user_id,
                UserConsent.consent_type == consent_type,
                UserConsent.given == True,
            )
            .first()
        )

        if not consent:
            return False

        # Check if expired
        if consent.expires_at and consent.expires_at < datetime.utcnow():
            return False

        return True

    @staticmethod
    def get_retention_policy(
        db: Session, data_type: str, jurisdiction: str = "GDPR"
    ) -> DataRetentionPolicy:
        """Get data retention policy"""
        policy = (
            db.query(DataRetentionPolicy)
            .filter(
                DataRetentionPolicy.data_type == data_type,
                DataRetentionPolicy.jurisdiction == jurisdiction,
            )
            .first()
        )

        return policy

    @staticmethod
    def request_data_deletion(
        db: Session, user_id: int, request_type: str = "full", reason: str = None
    ) -> DataDeletionRequest:
        """Request data deletion (GDPR Right to be Forgotten)"""

        deletion_request = DataDeletionRequest(
            user_id=user_id, request_type=request_type, status="pending", reason=reason
        )
        db.add(deletion_request)
        db.commit()
        db.refresh(deletion_request)

        logger.warning(
            f"Data deletion request created for user {user_id}",
            extra={"user_id": user_id, "request_id": deletion_request.id},
        )

        return deletion_request

    @staticmethod
    def execute_data_deletion(db: Session, deletion_request_id: int) -> int:
        """Execute data deletion for a user"""

        deletion_request = (
            db.query(DataDeletionRequest)
            .filter(DataDeletionRequest.id == deletion_request_id)
            .first()
        )

        if not deletion_request:
            return 0

        user_id = deletion_request.user_id
        deleted_count = 0

        try:
            # Delete OCR results
            ocr_count = (
                db.query(OCRResult).filter(OCRResult.user_id == user_id).delete()
            )
            deleted_count += ocr_count

            # Delete face verifications
            face_count = (
                db.query(FaceVerification)
                .filter(FaceVerification.user_id == user_id)
                .delete()
            )
            deleted_count += face_count

            # Delete fraud events
            fraud_count = (
                db.query(FraudEvent).filter(FraudEvent.user_id == user_id).delete()
            )
            deleted_count += fraud_count

            # Delete access logs
            access_count = (
                db.query(AccessLog).filter(AccessLog.user_id == user_id).delete()
            )
            deleted_count += access_count

            # Delete data access logs
            data_access_count = (
                db.query(DataAccessLog)
                .filter(DataAccessLog.user_id == user_id)
                .delete()
            )
            deleted_count += data_access_count

            # Update deletion request
            deletion_request.status = "completed"
            deletion_request.completed_at = datetime.utcnow()
            deletion_request.deleted_records = deleted_count

            db.commit()

            logger.warning(
                f"Data deletion completed for user {user_id}: {deleted_count} records",
                extra={"user_id": user_id, "deleted_count": deleted_count},
            )

            return deleted_count

        except Exception as e:
            deletion_request.status = "failed"
            db.commit()
            logger.error(
                f"Data deletion failed for user {user_id}: {str(e)}",
                extra={"user_id": user_id},
            )
            raise

    @staticmethod
    def log_audit_event(
        db: Session,
        user_id: int,
        action: str,
        resource_type: str = None,
        resource_id: int = None,
        old_value: str = None,
        new_value: str = None,
        ip_address: str = None,
        user_agent: str = None,
        reason: str = None,
    ):
        """Log compliance audit event"""

        audit_log = ComplianceAuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
            reason=reason,
        )
        db.add(audit_log)
        db.commit()

    @staticmethod
    def log_data_access(
        db: Session,
        user_id: int,
        accessed_by_user_id: int,
        data_type: str,
        record_id: int = None,
        access_type: str = "read",
        purpose: str = None,
        ip_address: str = None,
        user_agent: str = None,
    ):
        """Log data access for audit trail"""

        access_log = DataAccessLog(
            user_id=user_id,
            accessed_by_user_id=accessed_by_user_id,
            data_type=data_type,
            record_id=record_id,
            access_type=access_type,
            purpose=purpose,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(access_log)
        db.commit()

    @staticmethod
    def get_audit_trail(db: Session, user_id: int, days: int = 90) -> list:
        """Get audit trail for a user"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        logs = (
            db.query(ComplianceAuditLog)
            .filter(
                ComplianceAuditLog.user_id == user_id,
                ComplianceAuditLog.created_at >= cutoff_date,
            )
            .order_by(ComplianceAuditLog.created_at.desc())
            .all()
        )

        return logs

    @staticmethod
    def get_data_access_history(db: Session, user_id: int, days: int = 90) -> list:
        """Get data access history for a user"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        logs = (
            db.query(DataAccessLog)
            .filter(
                DataAccessLog.user_id == user_id,
                DataAccessLog.accessed_at >= cutoff_date,
            )
            .order_by(DataAccessLog.accessed_at.desc())
            .all()
        )

        return logs

    @staticmethod
    def cleanup_expired_data(db: Session) -> dict:
        """Cleanup expired data based on retention policies"""

        stats = {
            "ocr_results_deleted": 0,
            "face_verifications_deleted": 0,
            "embeddings_deleted": 0,
            "access_logs_deleted": 0,
        }

        try:
            # Get all retention policies
            policies = (
                db.query(DataRetentionPolicy)
                .filter(DataRetentionPolicy.auto_delete == True)
                .all()
            )

            for policy in policies:
                cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_days)

                if policy.data_type == "ocr_results":
                    count = (
                        db.query(OCRResult)
                        .filter(OCRResult.created_at < cutoff_date)
                        .delete()
                    )
                    stats["ocr_results_deleted"] += count

                elif policy.data_type == "face_verifications":
                    count = (
                        db.query(FaceVerification)
                        .filter(FaceVerification.created_at < cutoff_date)
                        .delete()
                    )
                    stats["face_verifications_deleted"] += count

                elif policy.data_type == "embeddings":
                    count = (
                        db.query(EmbeddingCache)
                        .filter(EmbeddingCache.created_at < cutoff_date)
                        .delete()
                    )
                    stats["embeddings_deleted"] += count

                elif policy.data_type == "access_logs":
                    count = (
                        db.query(AccessLog)
                        .filter(AccessLog.created_at < cutoff_date)
                        .delete()
                    )
                    stats["access_logs_deleted"] += count

            db.commit()

            logger.info(f"Data cleanup completed: {stats}", extra=stats)

            return stats

        except Exception as e:
            logger.error(f"Data cleanup failed: {str(e)}")
            raise

    @staticmethod
    def export_user_data(db: Session, user_id: int) -> dict:
        """Export all user data (GDPR Data Portability)"""

        data = {
            "user_id": user_id,
            "exported_at": datetime.utcnow().isoformat(),
            "ocr_results": [],
            "face_verifications": [],
            "consents": {},
            "audit_trail": [],
        }

        # Export OCR results
        ocr_results = db.query(OCRResult).filter(OCRResult.user_id == user_id).all()

        data["ocr_results"] = [
            {
                "task_id": r.task_id,
                "document_type": r.document_type,
                "confidence": r.confidence,
                "created_at": r.created_at.isoformat(),
            }
            for r in ocr_results
        ]

        # Export face verifications
        face_verifications = (
            db.query(FaceVerification).filter(FaceVerification.user_id == user_id).all()
        )

        data["face_verifications"] = [
            {
                "task_id": f.task_id,
                "match": f.match,
                "similarity": f.similarity,
                "confidence": f.confidence,
                "created_at": f.created_at.isoformat(),
            }
            for f in face_verifications
        ]

        # Export consents
        data["consents"] = ComplianceService.get_user_consents(db, user_id)

        # Export audit trail
        audit_logs = ComplianceService.get_audit_trail(db, user_id, days=365)
        data["audit_trail"] = [
            {
                "action": log.action,
                "resource_type": log.resource_type,
                "created_at": log.created_at.isoformat(),
            }
            for log in audit_logs
        ]

        return data
