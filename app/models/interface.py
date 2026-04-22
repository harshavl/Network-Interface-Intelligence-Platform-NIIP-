"""
Domain models — the canonical in-memory representation of network
interface telemetry and analysis results.

Implemented as `dataclasses` (rather than Pydantic models) because they
flow through the ML pipeline where mutation is common and validation is
performed once at the ingestion boundary.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class HealthStatus(str, Enum):
    """Categorical health status derived from numeric score."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AnomalyType(str, Enum):
    """Types of anomalies the system can flag."""

    UTILIZATION_HIGH = "utilization_high"
    UTILIZATION_ASYMMETRIC = "utilization_asymmetric"
    ERROR_SPIKE = "error_spike"
    DISCARD_SPIKE = "discard_spike"
    MULTIVARIATE_OUTLIER = "multivariate_outlier"


class Severity(str, Enum):
    """Severity levels applied to anomalies and recommendations."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class InterfaceMetric:
    """Single row of interface telemetry — one observation."""

    device_name: str
    interface_name: str
    interface_description: str
    in_utilization_percent: float
    out_utilization_percent: float
    in_errors_1h: int
    out_errors_1h: int
    in_discards_1h: int
    out_discards_1h: int

    @property
    def interface_id(self) -> str:
        """Stable identifier across devices."""
        return f"{self.device_name}::{self.interface_name}"

    @property
    def max_utilization(self) -> float:
        return max(self.in_utilization_percent, self.out_utilization_percent)

    @property
    def total_errors(self) -> int:
        return self.in_errors_1h + self.out_errors_1h

    @property
    def total_discards(self) -> int:
        return self.in_discards_1h + self.out_discards_1h


@dataclass
class Anomaly:
    """A single detected anomaly."""

    type: AnomalyType
    severity: Severity
    description: str
    metric_value: float | int
    baseline_value: Optional[float] = None


@dataclass
class Forecast:
    """Forecast result for an interface."""

    predicted_80pct_breach: Optional[str]   # ISO date or "ALREADY_BREACHED" or None
    days_until_capacity: Optional[int]
    trend: str                              # "increasing" | "decreasing" | "stable" | "critical"
    confidence: float                       # 0.0 – 1.0
    method: str                             # algorithm used


@dataclass
class RootCauseSuggestion:
    """Probable root cause and recommended remediation."""

    probable_cause: str
    confidence: float
    details: str
    recommended_actions: list[str]


@dataclass
class InterfaceAnalysis:
    """Complete analysis result for a single interface."""

    device: str
    interface: str
    description: str
    health_score: int
    status: HealthStatus
    anomalies: list[Anomaly] = field(default_factory=list)
    forecast: Optional[Forecast] = None
    root_cause_suggestion: Optional[RootCauseSuggestion] = None
    recommended_actions: list[str] = field(default_factory=list)
    raw_metrics: Optional[InterfaceMetric] = None


@dataclass
class AnalysisSummary:
    """Aggregate counts over a full analysis run."""

    total_interfaces: int
    healthy_count: int
    warning_count: int
    critical_count: int
    anomalies_detected: int
    forecasts_generated: int
    root_causes_identified: int
    avg_health_score: float


@dataclass
class AnalysisReport:
    """Top-level report containing summary and per-interface results."""

    analysis_timestamp: str
    summary: AnalysisSummary
    interfaces: list[InterfaceAnalysis]

    @classmethod
    def new(
        cls,
        summary: AnalysisSummary,
        interfaces: list[InterfaceAnalysis],
    ) -> "AnalysisReport":
        return cls(
            analysis_timestamp=datetime.now(timezone.utc).isoformat(),
            summary=summary,
            interfaces=interfaces,
        )
