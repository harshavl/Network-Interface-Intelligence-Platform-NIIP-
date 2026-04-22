"""
Health Scoring Engine.

Produces a single 0–100 score per interface, derived from four
weighted sub-scores. Higher is healthier.

  - Utilization sub-score: 100 at 0% util, 0 at 100% util, with a steeper
    drop above the warning threshold.
  - Error sub-score: log-decay so small error counts are tolerated but
    big spikes are penalized hard.
  - Discard sub-score: same shape as errors.
  - Anomaly sub-score: deduction per anomaly weighted by severity.

Final score is a weighted sum, then mapped to a health status enum.
"""

from __future__ import annotations

import math

from app.core import Settings, get_logger
from app.models import Anomaly, HealthStatus, InterfaceMetric, Severity

logger = get_logger(__name__)


_SEVERITY_PENALTY = {
    Severity.LOW: 5,
    Severity.MEDIUM: 15,
    Severity.HIGH: 30,
    Severity.CRITICAL: 50,
}


class HealthScoringEngine:
    """Compute composite health scores for interfaces."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def score(
        self,
        metric: InterfaceMetric,
        anomalies: list[Anomaly],
    ) -> tuple[int, HealthStatus]:
        """Return (score 0-100, status enum)."""
        util_score = self._utilization_subscore(metric.max_utilization)
        error_score = self._counter_subscore(
            metric.total_errors,
            warning=self.settings.error_warning_threshold,
            critical=self.settings.error_critical_threshold,
        )
        discard_score = self._counter_subscore(
            metric.total_discards,
            warning=self.settings.discard_warning_threshold,
            critical=self.settings.discard_critical_threshold,
        )
        anomaly_score = self._anomaly_subscore(anomalies)

        weighted = (
            util_score * self.settings.health_score_weights_util
            + error_score * self.settings.health_score_weights_errors
            + discard_score * self.settings.health_score_weights_discards
            + anomaly_score * self.settings.health_score_weights_anomaly
        )

        final_score = int(round(max(0.0, min(100.0, weighted))))
        status = self._status_from_score(final_score)

        logger.debug(
            "health_score_computed",
            interface=metric.interface_id,
            util_score=util_score,
            error_score=error_score,
            discard_score=discard_score,
            anomaly_score=anomaly_score,
            final=final_score,
            status=status.value,
        )
        return final_score, status

    # ---------------- sub-scores ----------------

    def _utilization_subscore(self, util_pct: float) -> float:
        """Linear above warning threshold, gentle below."""
        if util_pct <= 0:
            return 100.0
        warn = self.settings.util_warning_threshold
        crit = self.settings.util_critical_threshold

        if util_pct < warn:
            # 100 → 80 across [0, warn]
            return 100.0 - (util_pct / warn) * 20.0
        if util_pct < crit:
            # 80 → 30 across [warn, crit]
            ratio = (util_pct - warn) / (crit - warn)
            return 80.0 - ratio * 50.0
        # 30 → 0 across [crit, 100]
        ratio = min(1.0, (util_pct - crit) / max(1e-6, 100.0 - crit))
        return max(0.0, 30.0 - ratio * 30.0)

    def _counter_subscore(self, value: int, warning: int, critical: int) -> float:
        """Logarithmic decay with thresholds for errors and discards."""
        if value <= 0:
            return 100.0
        if value < warning:
            ratio = value / max(1, warning)
            return 100.0 - ratio * 15.0  # 100 → 85
        if value < critical:
            ratio = (value - warning) / max(1, critical - warning)
            return 85.0 - ratio * 45.0  # 85 → 40
        # Above critical, log decay from 40 → 0
        excess = value - critical
        decay = min(40.0, 10.0 * math.log10(1.0 + excess / max(1, critical)))
        return max(0.0, 40.0 - decay)

    def _anomaly_subscore(self, anomalies: list[Anomaly]) -> float:
        """Start at 100, deduct per-anomaly penalty by severity."""
        if not anomalies:
            return 100.0
        penalty = sum(_SEVERITY_PENALTY.get(a.severity, 10) for a in anomalies)
        return max(0.0, 100.0 - penalty)

    @staticmethod
    def _status_from_score(score: int) -> HealthStatus:
        if score >= 80:
            return HealthStatus.HEALTHY
        if score > 55:
            return HealthStatus.WARNING
        return HealthStatus.CRITICAL
