"""Anti-fraud rules engine for OCR passport service."""

import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

import redis
from sqlalchemy.orm import Session

from app.models import PassportData
from app.config import settings
from app.logging_config import log_security_event


class FraudRuleType(Enum):
    """Types of fraud detection rules."""

    SUSPICIOUS_PATTERN = "suspicious_pattern"
    FREQUENCY_ABUSE = "frequency_abuse"
    DATA_INCONSISTENCY = "data_inconsistency"
    BLACKLISTED_CONTENT = "blacklisted_content"
    SIMILARITY_DETECTION = "similarity_detection"


@dataclass
class FraudAlert:
    """Fraud alert structure."""

    rule_type: FraudRuleType
    rule_name: str
    severity: str  # low, medium, high, critical
    score: float
    details: Dict[str, Any]
    timestamp: datetime


class AntiFraudEngine:
    """Main anti-fraud engine class."""

    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.rules = [
            self._check_suspicious_names,
            self._check_frequency_abuse,
            self._check_document_patterns,
            self._check_date_anomalies,
            self._check_blacklisted_content,
            self._check_duplicate_patterns,
        ]

    def _check_suspicious_names(
        self, passport_data: Dict[str, Any]
    ) -> Optional[FraudAlert]:
        """Check for suspicious name patterns."""
        name = passport_data.get("full_name", "").upper()

        # Known test/fake names
        fake_names = [
            "TEST",
            "SAMPLE",
            "DEMO",
            "FAKE",
            "EXAMPLE",
            "JOHN DOE",
            "JANE DOE",
            "TESTER",
            "ADMIN",
        ]

        # Suspicious patterns
        suspicious_patterns = [
            r"DUMMY\s*\d+",  # DUMMY123
            r"TEST\s*[A-Z]\d+",  # TESTA1234567
            r"[A-Z]{3,}\d{6,}",  # AAA123456 (too many consecutive letters)
            r"\d{3,}[A-Z]{3,}",  # 123AAA (too many consecutive digits)
        ]

        for fake_name in fake_names:
            if fake_name in name:
                return FraudAlert(
                    rule_type=FraudRuleType.BLACKLISTED_CONTENT,
                    rule_name="blacklisted_name",
                    severity="high",
                    score=0.8,
                    details={"found_name": fake_name, "field": "full_name"},
                    timestamp=datetime.utcnow(),
                )

        for pattern in suspicious_patterns:
            if re.search(pattern, name):
                return FraudAlert(
                    rule_type=FraudRuleType.SUSPICIOUS_PATTERN,
                    rule_name="suspicious_name_pattern",
                    severity="medium",
                    score=0.6,
                    details={
                        "pattern": pattern,
                        "matched_text": re.search(pattern, name).group(),
                        "field": "full_name",
                    },
                    timestamp=datetime.utcnow(),
                )

        return None

    def _check_frequency_abuse(
        self, passport_data: Dict[str, Any], ip_address: str
    ) -> Optional[FraudAlert]:
        """Check for frequency-based abuse patterns."""
        key = f"fraud:freq:{ip_address}"
        current_time = datetime.utcnow().timestamp()

        # Track requests in last 5 minutes
        pipeline = self.redis_client.pipeline()
        pipeline.zremrangebyscore(key, 0, current_time - 300)  # Remove old entries
        pipeline.zcard(key)  # Count current entries
        pipeline.zadd(key, {str(current_time): current_time})  # Add current request
        pipeline.expire(key, 300)  # Expire after 5 minutes
        results = pipeline.execute()

        request_count = results[1]

        if request_count > 10:  # More than 10 requests in 5 minutes
            return FraudAlert(
                rule_type=FraudRuleType.FREQUENCY_ABUSE,
                rule_name="high_frequency_requests",
                severity="medium",
                score=0.7,
                details={
                    "request_count": request_count,
                    "ip_address": ip_address,
                    "threshold": 10,
                },
                timestamp=datetime.utcnow(),
            )

        # Also check passport number frequency
        passport_num = passport_data.get("passport_number", "")
        if passport_num:
            passport_key = f"fraud:freq:passport:{passport_num}"
            pipeline = self.redis_client.pipeline()
            pipeline.zremrangebyscore(passport_key, 0, current_time - 3600)  # Last hour
            pipeline.zcard()
            pipeline.zadd(passport_key, {str(current_time): current_time})
            pipeline.expire(passport_key, 3600)
            results = pipeline.execute()

            passport_freq = results[1]

            if passport_freq > 5:  # Same passport scanned more than 5 times per hour
                return FraudAlert(
                    rule_type=FraudRuleType.FREQUENCY_ABUSE,
                    rule_name="high_passport_frequency",
                    severity="high",
                    score=0.85,
                    details={
                        "passport_number": passport_num,
                        "frequency": passport_freq,
                        "threshold": 5,
                    },
                    timestamp=datetime.utcnow(),
                )

        return None

    def _check_document_patterns(
        self, passport_data: Dict[str, Any]
    ) -> Optional[FraudAlert]:
        """Check for suspicious document patterns."""
        passport_num = passport_data.get("passport_number", "").upper()

        if not passport_num:
            return None

        # Check for sequential patterns
        if re.match(r"^[A-Z]\d{7}$", passport_num):  # A1234567 format
            # Check for common test series
            if passport_num.startswith(("A00", "TEST", "TEMP")):
                return FraudAlert(
                    rule_type=FraudRuleType.SUSPICIOUS_PATTERN,
                    rule_name="test_passport_series",
                    severity="high",
                    score=0.9,
                    details={"passport_number": passport_num, "pattern": "test_series"},
                    timestamp=datetime.utcnow(),
                )

        # Check for repetitive patterns
        if (
            len(set(passport_num)) < len(passport_num) // 2
        ):  # Too many repeated characters
            return FraudAlert(
                rule_type=FraudRuleType.SUSPICIOUS_PATTERN,
                rule_name="repetitive_characters",
                severity="medium",
                score=0.5,
                details={
                    "passport_number": passport_num,
                    "unique_chars": len(set(passport_num)),
                    "total_chars": len(passport_num),
                },
                timestamp=datetime.utcnow(),
            )

        return None

    def _check_date_anomalies(
        self, passport_data: Dict[str, Any]
    ) -> Optional[FraudAlert]:
        """Check for suspicious date patterns."""
        dob_str = passport_data.get("date_of_birth")
        exp_str = passport_data.get("expiry_date")

        if not dob_str and not exp_str:
            return None

        try:
            # Parse dates
            dob = datetime.strptime(dob_str, "%Y-%m-%d") if dob_str else None
            exp = datetime.strptime(exp_str, "%Y-%m-%d") if exp_str else None

            if dob:
                # Check for future birth dates
                if dob > datetime.now():
                    return FraudAlert(
                        rule_type=FraudRuleType.DATA_INCONSISTENCY,
                        rule_name="future_birth_date",
                        severity="critical",
                        score=0.95,
                        details={
                            "birth_date": dob_str,
                            "current_date": datetime.now().strftime("%Y-%m-%d"),
                        },
                        timestamp=datetime.utcnow(),
                    )

                # Check for unrealistic ages
                if (datetime.now() - dob).days > 365 * 120:  # Older than 120 years
                    return FraudAlert(
                        rule_type=FraudRuleType.DATA_INCONSISTENCY,
                        rule_name="unrealistic_age",
                        severity="high",
                        score=0.8,
                        details={
                            "birth_date": dob_str,
                            "calculated_age": (datetime.now() - dob).days // 365,
                        },
                        timestamp=datetime.utcnow(),
                    )

            if exp:
                # Check for past expiry dates (unless checking expired documents is intentional)
                if exp < datetime.now():
                    return FraudAlert(
                        rule_type=FraudRuleType.DATA_INCONSISTENCY,
                        rule_name="expired_document",
                        severity="low",
                        score=0.3,
                        details={
                            "expiry_date": exp_str,
                            "days_expired": (datetime.now() - exp).days,
                        },
                        timestamp=datetime.utcnow(),
                    )

            if dob and exp:
                # Check if expiry date is before birth date
                if exp < dob:
                    return FraudAlert(
                        rule_type=FraudRuleType.DATA_INCONSISTENCY,
                        rule_name="expiry_before_birth",
                        severity="critical",
                        score=0.9,
                        details={"birth_date": dob_str, "expiry_date": exp_str},
                        timestamp=datetime.utcnow(),
                    )

        except ValueError:
            # Invalid date format
            return FraudAlert(
                rule_type=FraudRuleType.DATA_INCONSISTENCY,
                rule_name="invalid_date_format",
                severity="high",
                score=0.7,
                details={"birth_date": dob_str, "expiry_date": exp_str},
                timestamp=datetime.utcnow(),
            )

        return None

    def _check_blacklisted_content(
        self, passport_data: Dict[str, Any]
    ) -> Optional[FraudAlert]:
        """Check for blacklisted content."""
        from app.validators import BLACKLISTED_TERMS

        for field_name, field_value in passport_data.items():
            if isinstance(field_value, str):
                field_lower = field_value.lower()
                for blacklist_item in BLACKLISTED_TERMS:
                    if blacklist_item.lower() in field_lower:
                        return FraudAlert(
                            rule_type=FraudRuleType.BLACKLISTED_CONTENT,
                            rule_name="blacklisted_term",
                            severity="high",
                            score=0.85,
                            details={
                                "field": field_name,
                                "found_term": blacklist_item,
                                "field_value": field_value,
                            },
                            timestamp=datetime.utcnow(),
                        )

        return None

    def _check_duplicate_patterns(
        self, db: Session, passport_data: Dict[str, Any]
    ) -> Optional[FraudAlert]:
        """Check for duplicate patterns in recent submissions."""
        passport_number = passport_data.get("passport_number", "")

        if not passport_number:
            return None

        # Find similar passports in last 24 hours
        recent_time = datetime.utcnow() - timedelta(hours=24)

        similar_passports = (
            db.query(PassportData)
            .filter(
                PassportData.passport_number == passport_number,
                PassportData.created_at >= recent_time,
            )
            .all()
        )

        if len(similar_passports) > 3:  # Multiple scans of same passport
            return FraudAlert(
                rule_type=FraudRuleType.SIMILARITY_DETECTION,
                rule_name="multiple_scans_same_passport",
                severity="medium",
                score=0.6,
                details={
                    "passport_number": passport_number,
                    "scan_count": len(similar_passports),
                    "time_window_hours": 24,
                },
                timestamp=datetime.utcnow(),
            )

        return None

    def analyze(
        self, db: Session, passport_data: Dict[str, Any], ip_address: str = None
    ) -> List[FraudAlert]:
        """Analyze passport data for fraud indicators."""
        alerts = []

        for rule_func in self.rules:
            try:
                if "ip_address" in rule_func.__code__.co_varnames:
                    alert = rule_func(passport_data, ip_address)
                else:
                    alert = rule_func(passport_data)

                if alert:
                    alerts.append(alert)

                    # Log security event
                    log_security_event(
                        event_type=f"fraud_alert_{alert.severity}",
                        severity=alert.severity,
                        ip_address=ip_address or "unknown",
                        user_agent="OCR_Service",
                        details={
                            "rule_name": alert.rule_name,
                            "score": alert.score,
                            "details": alert.details,
                        },
                    )
            except Exception as e:
                # Log rule execution errors but don't break the process
                log_security_event(
                    event_type="fraud_rule_error",
                    severity="low",
                    ip_address=ip_address or "unknown",
                    user_agent="OCR_Service",
                    details={"rule_function": rule_func.__name__, "error": str(e)},
                )

        return alerts

    def get_risk_score(self, alerts: List[FraudAlert]) -> float:
        """Calculate overall risk score from alerts."""
        if not alerts:
            return 0.0

        # Weighted scoring based on severity
        severity_weights = {"low": 0.1, "medium": 0.3, "high": 0.7, "critical": 1.0}

        total_score = sum(
            alert.score * severity_weights.get(alert.severity, 0.5) for alert in alerts
        )
        max_possible = len(alerts)  # Maximum possible score

        return min(
            total_score / max_possible if max_possible > 0 else 0, 1.0
        )  # Normalize to 0-1 range

    def is_high_risk(self, risk_score: float) -> bool:
        """Determine if risk score indicates high risk."""
        return risk_score >= 0.7


# Global instance
antifraud_engine = AntiFraudEngine()
