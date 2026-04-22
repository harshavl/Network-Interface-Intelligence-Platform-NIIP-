"""
Analysis orchestration service.

Wires the four ML engines into a single end-to-end pipeline. This is
the single entry point used by the API layer and the CLI — all higher
layers depend on this service rather than on the individual engines.
"""

from __future__ import annotations

from app.core import Settings, get_logger
from app.ml import (
    AnomalyDetectionEngine,
    ForecastingEngine,
    HealthScoringEngine,
    RootCauseEngine,
)
from app.models import (
    AnalysisReport,
    AnalysisSummary,
    HealthStatus,
    InterfaceAnalysis,
    InterfaceMetric,
    Severity,
)

logger = get_logger(__name__)


class AnalysisService:
    """Orchestrate the four ML engines to produce an AnalysisReport."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.anomaly_engine = AnomalyDetectionEngine(settings)
        self.forecast_engine = ForecastingEngine(settings)
        self.root_cause_engine = RootCauseEngine(settings)
        self.health_engine = HealthScoringEngine(settings)

    def analyze(self, metrics: list[InterfaceMetric]) -> AnalysisReport:
        """Run the full analysis pipeline."""
        logger.info("analysis_started", interface_count=len(metrics))

        if not metrics:
            return AnalysisReport.new(
                summary=AnalysisSummary(
                    total_interfaces=0,
                    healthy_count=0,
                    warning_count=0,
                    critical_count=0,
                    anomalies_detected=0,
                    forecasts_generated=0,
                    root_causes_identified=0,
                    avg_health_score=0.0,
                ),
                interfaces=[],
            )

        # Step 1: Anomaly detection — works on the full batch
        anomalies_by_iface = self.anomaly_engine.detect(metrics)

        analyses: list[InterfaceAnalysis] = []
        anomalies_total = 0
        forecasts_total = 0
        root_causes_total = 0

        for metric in metrics:
            iface_anomalies = anomalies_by_iface.get(metric.interface_id, [])
            anomalies_total += len(iface_anomalies)

            # Step 2: Forecast (snapshot mode)
            forecast = self.forecast_engine.forecast_snapshot(metric)
            if forecast is not None:
                forecasts_total += 1

            # Step 3: Root cause
            root_cause = self.root_cause_engine.suggest(metric, iface_anomalies)
            if root_cause is not None:
                root_causes_total += 1

            # Step 4: Health score
            score, status = self.health_engine.score(metric, iface_anomalies)

            # Escalation rule: 2+ high/critical-severity anomalies override
            # the weighted score and force CRITICAL status. This catches
            # genuinely degraded interfaces whose composite score sits in
            # the warning band but whose individual signals are alarming.
            severe_count = sum(
                1 for a in iface_anomalies
                if a.severity in (Severity.HIGH, Severity.CRITICAL)
            )
            if severe_count >= 2 and status != HealthStatus.CRITICAL:
                status = HealthStatus.CRITICAL
                score = min(score, 49)

            recommended_actions = self._build_recommendations(
                status, iface_anomalies, root_cause, forecast
            )

            analyses.append(
                InterfaceAnalysis(
                    device=metric.device_name,
                    interface=metric.interface_name,
                    description=metric.interface_description,
                    health_score=score,
                    status=status,
                    anomalies=iface_anomalies,
                    forecast=forecast,
                    root_cause_suggestion=root_cause,
                    recommended_actions=recommended_actions,
                    raw_metrics=metric,
                )
            )

        summary = self._build_summary(
            analyses,
            anomalies_total=anomalies_total,
            forecasts_total=forecasts_total,
            root_causes_total=root_causes_total,
        )

        # Sort: critical first, then warning, then healthy; lower scores first within tier
        analyses.sort(key=lambda a: (self._status_order(a.status), a.health_score))

        report = AnalysisReport.new(summary=summary, interfaces=analyses)
        logger.info(
            "analysis_completed",
            total=summary.total_interfaces,
            healthy=summary.healthy_count,
            warning=summary.warning_count,
            critical=summary.critical_count,
            anomalies=summary.anomalies_detected,
            avg_score=summary.avg_health_score,
        )
        return report

    # ---------------- helpers ----------------

    @staticmethod
    def _status_order(status: HealthStatus) -> int:
        return {
            HealthStatus.CRITICAL: 0,
            HealthStatus.WARNING: 1,
            HealthStatus.HEALTHY: 2,
            HealthStatus.UNKNOWN: 3,
        }[status]

    @staticmethod
    def _build_summary(
        analyses: list[InterfaceAnalysis],
        anomalies_total: int,
        forecasts_total: int,
        root_causes_total: int,
    ) -> AnalysisSummary:
        healthy = sum(1 for a in analyses if a.status == HealthStatus.HEALTHY)
        warning = sum(1 for a in analyses if a.status == HealthStatus.WARNING)
        critical = sum(1 for a in analyses if a.status == HealthStatus.CRITICAL)
        avg_score = (
            sum(a.health_score for a in analyses) / len(analyses)
            if analyses
            else 0.0
        )
        return AnalysisSummary(
            total_interfaces=len(analyses),
            healthy_count=healthy,
            warning_count=warning,
            critical_count=critical,
            anomalies_detected=anomalies_total,
            forecasts_generated=forecasts_total,
            root_causes_identified=root_causes_total,
            avg_health_score=round(avg_score, 2),
        )

    @staticmethod
    def _build_recommendations(
        status: HealthStatus,
        anomalies: list,
        root_cause,
        forecast,
    ) -> list[str]:
        """Compose top-level recommendations independent of root cause."""
        recs: list[str] = []
        if root_cause:
            recs.extend(root_cause.recommended_actions)
        if forecast and forecast.predicted_80pct_breach == "ALREADY_BREACHED":
            recs.append("Capacity already breached — investigate immediately")
        elif forecast and forecast.days_until_capacity is not None:
            if forecast.days_until_capacity <= 30:
                recs.append(
                    f"Plan capacity upgrade within {forecast.days_until_capacity} days"
                )
        if status == HealthStatus.HEALTHY and not recs:
            recs.append("No action required — interface is healthy")
        elif status == HealthStatus.WARNING and not recs:
            recs.append("Monitor closely; no immediate action required")
        elif status == HealthStatus.CRITICAL and not recs:
            severities = {a.severity for a in anomalies}
            if Severity.CRITICAL in severities or Severity.HIGH in severities:
                recs.append("High-severity anomalies present — escalate to NOC")
            else:
                recs.append("Critical health score — investigate root cause")
        # De-duplicate while preserving order
        seen = set()
        return [r for r in recs if not (r in seen or seen.add(r))]
