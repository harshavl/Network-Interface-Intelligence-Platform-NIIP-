"""
Pydantic schemas for API input validation and output serialization.

These are the contract at the API boundary. Internal code uses the
dataclass models in `app.models`; these schemas exist purely to
validate incoming JSON and serialize outgoing JSON.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InterfaceMetricSchema(BaseModel):
    """Schema for a single interface metric row submitted via JSON."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    device_name: str = Field(..., min_length=1, max_length=255)
    interface_name: str = Field(..., min_length=1, max_length=255)
    interface_description: str = Field(default="", max_length=1024)
    in_utilization_percent: float = Field(..., ge=0.0, le=100.0)
    out_utilization_percent: float = Field(..., ge=0.0, le=100.0)
    in_errors_1h: int = Field(..., ge=0)
    out_errors_1h: int = Field(..., ge=0)
    in_discards_1h: int = Field(..., ge=0)
    out_discards_1h: int = Field(..., ge=0)

    @field_validator("interface_description", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        return v if v is not None else ""


class AnalysisRequestSchema(BaseModel):
    """Schema for direct JSON analysis requests."""

    interfaces: list[InterfaceMetricSchema] = Field(..., min_length=1, max_length=100_000)


class AnomalySchema(BaseModel):
    type: str
    severity: str
    description: str
    metric_value: float | int
    baseline_value: Optional[float] = None


class ForecastSchema(BaseModel):
    predicted_80pct_breach: Optional[str]
    days_until_capacity: Optional[int]
    trend: str
    confidence: float
    method: str


class RootCauseSchema(BaseModel):
    probable_cause: str
    confidence: float
    details: str
    recommended_actions: list[str]


class InterfaceAnalysisSchema(BaseModel):
    device: str
    interface: str
    description: str
    health_score: int
    status: str
    anomalies: list[AnomalySchema] = Field(default_factory=list)
    forecast: Optional[ForecastSchema] = None
    root_cause_suggestion: Optional[RootCauseSchema] = None
    recommended_actions: list[str] = Field(default_factory=list)


class AnalysisSummarySchema(BaseModel):
    total_interfaces: int
    healthy_count: int
    warning_count: int
    critical_count: int
    anomalies_detected: int
    forecasts_generated: int
    root_causes_identified: int
    avg_health_score: float


class AnalysisReportSchema(BaseModel):
    analysis_timestamp: str
    summary: AnalysisSummarySchema
    interfaces: list[InterfaceAnalysisSchema]


class ErrorResponseSchema(BaseModel):
    error: str
    message: str
    details: dict = Field(default_factory=dict)
