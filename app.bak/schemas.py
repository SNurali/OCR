from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, RootModel


class FieldWithConfidence(BaseModel):
    value: str = ""
    confidence: float = 0.0


class PassportDataResponse(BaseModel):
    id: int
    task_id: str
    first_name: str = ""
    last_name: str = ""
    middle_name: str = ""
    birth_date: str = ""
    gender: str = ""
    nationality: str = ""
    passport_number: str = ""
    passport_series: str = ""
    issue_date: str = ""
    expiry_date: str = ""
    issued_by: str = ""
    pinfl: str = ""
    mrz_line1: Optional[str] = None
    mrz_line2: Optional[str] = None
    mrz_line3: Optional[str] = None
    mrz_valid: bool = False
    confidence: float = 0.0
    validation_status: str = "pending"
    field_confidence: Optional[Dict[str, float]] = None
    low_confidence_fields: Optional[List[str]] = None
    engine_used: Optional[str] = None
    raw_text: Optional[str] = None
    fraud_risk_score: Optional[float] = None
    fraud_alerts: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[str] = None


class DashboardLoginRequest(BaseModel):
    username: str
    password: str


class DashboardTokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token lifetime in seconds")


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    role: str


class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[UserResponse]


class SummaryResponse(BaseModel):
    total_passports: int
    total_uploads: int
    unrecognized_uploads: int
    male_count: int
    female_count: int
    male_percent: float
    female_percent: float
    average_age: float


class RoleDetailsResponse(BaseModel):
    name: str
    level: int
    description: str
    permissions: List[str]


class RolesResponse(BaseModel):
    roles: List[RoleDetailsResponse]


class CurrentUserInfoResponse(BaseModel):
    id: int
    username: str
    role: str
    role_description: str
    permissions: List[str]
    is_active: bool
    created_at: Optional[str] = None


class MessageResponse(BaseModel):
    message: str


class PasswordResetResponse(BaseModel):
    message: str
    temporary_password: str
    warning: str


class CountPercentResponse(BaseModel):
    count: int
    percent: float


class GenderReportResponse(BaseModel):
    total: int
    male: CountPercentResponse
    female: CountPercentResponse
    unknown: CountPercentResponse
    more: str
    difference: int


class AgeGroupReportResponse(BaseModel):
    total: int
    groups: Dict[str, int]
    percentages: Dict[str, float]
    average_age: float


class NationalityReportResponse(BaseModel):
    total: int
    nationalities: List[Dict[str, Any]]


class TimeReportResponse(BaseModel):
    period: str
    start_date: str
    end_date: str
    count: int
    average_per_day: float


class MonthlyStatsResponse(BaseModel):
    year: int
    total: int
    months: List[Dict[str, Any]]
    average_per_month: float


class YearlyStatsResponse(BaseModel):
    years: List[Dict[str, Any]]
    total: int


class GenderByAgeResponse(RootModel[Dict[str, Dict[str, int]]]):
    pass


class DailyBreakdownResponse(BaseModel):
    days: int
    data: List[Dict[str, Any]]
    total: int
    average_per_day: float


class AccessLogItemResponse(BaseModel):
    id: int
    user_id: int
    action: str
    ip_address: Optional[str] = None
    created_at: Optional[str] = None


class AccessLogsResponse(BaseModel):
    logs: List[AccessLogItemResponse]


class PassportScanResponse(BaseModel):
    task_id: str
    status: str
    message: str


class PassportStatusResponse(BaseModel):
    task_id: str
    status: str
    confidence: float
    created_at: Optional[str] = None


class PassportListItemResponse(BaseModel):
    id: int
    task_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    birth_date: Optional[str] = None
    passport_series: Optional[str] = None
    passport_number: Optional[str] = None
    confidence: Optional[float] = None
    duplicate_count: Optional[int] = 1
    created_at: Optional[str] = None


class PassportListResponse(BaseModel):
    total: int
    page: int
    limit: int
    data: List[PassportListItemResponse]


class PassportOcrTestResponse(BaseModel):
    filename: str
    image: Dict[str, int]
    doc_detected: bool
    ocr_confidence: float
    overall_confidence: float
    mrz_valid: bool
    mrz_lines: List[str]
    mrz_data: Dict[str, Any]
    extracted_fields: Dict[str, Any]
    validation: Dict[str, Any]
    raw_text: str


class HealthResponse(BaseModel):
    status: str
    version: str
