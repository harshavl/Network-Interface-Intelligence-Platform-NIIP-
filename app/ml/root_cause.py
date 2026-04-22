"""
Root Cause Suggestion Engine.

Uses a rule-based expert system that encodes well-known network
operations diagnostic patterns. Each rule has a confidence score and
specific remediation steps. When a future training dataset becomes
available, the same interface can be implemented by an ML classifier
without changing callers.

The rules are ordered by specificity. The first matching rule with the
highest score wins. Rules return None to indicate "no opinion".
"""

from __future__ import annotations

from typing import Optional

from app.core import MLEngineException, Settings, get_logger
from app.models import Anomaly, AnomalyType, InterfaceMetric, RootCauseSuggestion

logger = get_logger(__name__)


class RootCauseEngine:
    """Suggest probable root causes for problematic interfaces."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def suggest(
        self,
        metric: InterfaceMetric,
        anomalies: list[Anomaly],
    ) -> Optional[RootCauseSuggestion]:
        """Return a `RootCauseSuggestion` if a rule fires, else None."""
        if not anomalies:
            return None

        try:
            candidates: list[RootCauseSuggestion] = []
            for rule in self._rules:
                result = rule(metric, anomalies)
                if result is not None:
                    candidates.append(result)

            if not candidates:
                return None

            # Highest-confidence winner
            return max(candidates, key=lambda r: r.confidence)
        except Exception as exc:
            logger.exception("root_cause_failed", error=str(exc))
            raise MLEngineException(
                "Root cause analysis failed",
                details={"underlying": str(exc), "interface": metric.interface_id},
            ) from exc

    # ---------------- rules ----------------

    @property
    def _rules(self):
        return [
            self._rule_congestion_with_discards,
            self._rule_physical_layer_errors,
            self._rule_buffer_exhaustion,
            self._rule_capacity_warning,
            self._rule_asymmetric_routing,
            self._rule_combined_errors_and_congestion,
        ]

    def _rule_congestion_with_discards(
        self, m: InterfaceMetric, anomalies: list[Anomaly]
    ) -> Optional[RootCauseSuggestion]:
        """High utilization + high discards → classic congestion."""
        types = {a.type for a in anomalies}
        if (
            AnomalyType.UTILIZATION_HIGH in types
            and AnomalyType.DISCARD_SPIKE in types
            and m.max_utilization >= 80.0
        ):
            return RootCauseSuggestion(
                probable_cause="Interface congestion / link saturation",
                confidence=0.94,
                details=(
                    f"Utilization at {m.max_utilization:.1f}% combined with "
                    f"{m.total_discards} discards in the last hour strongly "
                    "suggests the link is saturated and dropping packets."
                ),
                recommended_actions=[
                    "Immediate: implement QoS policies to protect critical traffic",
                    "Short-term: investigate top talkers via NetFlow / sFlow",
                    "Long-term: upgrade link capacity or add a parallel link via LACP",
                ],
            )
        return None

    def _rule_physical_layer_errors(
        self, m: InterfaceMetric, anomalies: list[Anomaly]
    ) -> Optional[RootCauseSuggestion]:
        """High errors + low utilization → likely physical layer issue."""
        types = {a.type for a in anomalies}
        if (
            AnomalyType.ERROR_SPIKE in types
            and m.max_utilization < 30.0
            and m.total_errors > 50
        ):
            return RootCauseSuggestion(
                probable_cause="Physical layer issue",
                confidence=0.87,
                details=(
                    f"{m.total_errors} errors at low utilization "
                    f"({m.max_utilization:.1f}%) typically indicates cabling, "
                    "SFP/optic, or duplex-mismatch issues rather than congestion."
                ),
                recommended_actions=[
                    "Inspect the SFP/transceiver on local and remote ends",
                    "Verify cable integrity (light levels for fiber, continuity for copper)",
                    "Check for duplex mismatch with the neighbor",
                    "Review interface counters for CRC errors and runts",
                ],
            )
        return None

    def _rule_buffer_exhaustion(
        self, m: InterfaceMetric, anomalies: list[Anomaly]
    ) -> Optional[RootCauseSuggestion]:
        """High discards + moderate utilization → bursty traffic / micro-bursts."""
        types = {a.type for a in anomalies}
        if (
            AnomalyType.DISCARD_SPIKE in types
            and AnomalyType.UTILIZATION_HIGH not in types
            and m.total_discards > 100
        ):
            return RootCauseSuggestion(
                probable_cause="Buffer exhaustion from micro-bursts",
                confidence=0.78,
                details=(
                    f"{m.total_discards} discards without sustained high "
                    "utilization indicates short bursts overwhelming interface "
                    "buffers — common with elephant flows or backup windows."
                ),
                recommended_actions=[
                    "Enable per-queue statistics to confirm micro-bursts",
                    "Tune output queue depth on the device",
                    "Investigate scheduled jobs (backups, replication) on connected hosts",
                    "Consider WRED or shaped queues for affected traffic classes",
                ],
            )
        return None

    def _rule_capacity_warning(
        self, m: InterfaceMetric, anomalies: list[Anomaly]
    ) -> Optional[RootCauseSuggestion]:
        """High utilization with no other signals → capacity planning."""
        types = {a.type for a in anomalies}
        if (
            AnomalyType.UTILIZATION_HIGH in types
            and AnomalyType.DISCARD_SPIKE not in types
            and AnomalyType.ERROR_SPIKE not in types
            and m.max_utilization >= self.settings.util_warning_threshold
        ):
            severity_word = (
                "critically high"
                if m.max_utilization >= self.settings.util_critical_threshold
                else "elevated"
            )
            return RootCauseSuggestion(
                probable_cause="Capacity headroom approaching limit",
                confidence=0.82,
                details=(
                    f"Utilization is {severity_word} ({m.max_utilization:.1f}%) "
                    "but there are no errors or discards yet. This is a leading "
                    "indicator — plan capacity before quality degrades."
                ),
                recommended_actions=[
                    "Trend utilization over 30/60/90 days",
                    "Identify top talkers and consider traffic optimization",
                    "Plan upgrade if growth continues at current rate",
                ],
            )
        return None

    def _rule_asymmetric_routing(
        self, m: InterfaceMetric, anomalies: list[Anomaly]
    ) -> Optional[RootCauseSuggestion]:
        """Asymmetric utilization → possible asymmetric routing or single-flow dominance."""
        types = {a.type for a in anomalies}
        if AnomalyType.UTILIZATION_ASYMMETRIC in types:
            return RootCauseSuggestion(
                probable_cause="Asymmetric traffic distribution",
                confidence=0.65,
                details=(
                    f"Significant difference between in ({m.in_utilization_percent:.1f}%) "
                    f"and out ({m.out_utilization_percent:.1f}%) utilization. "
                    "Possible causes: asymmetric routing, content-heavy server "
                    "workload, or a dominant elephant flow."
                ),
                recommended_actions=[
                    "Verify routing symmetry with traceroute in both directions",
                    "Profile traffic with NetFlow to identify dominant flows",
                    "Check if this matches the expected role (e.g. download server)",
                ],
            )
        return None

    def _rule_combined_errors_and_congestion(
        self, m: InterfaceMetric, anomalies: list[Anomaly]
    ) -> Optional[RootCauseSuggestion]:
        """Errors + utilization + discards → degraded link under load."""
        types = {a.type for a in anomalies}
        if (
            AnomalyType.ERROR_SPIKE in types
            and AnomalyType.UTILIZATION_HIGH in types
            and AnomalyType.DISCARD_SPIKE in types
        ):
            return RootCauseSuggestion(
                probable_cause="Degraded link under load (compounded fault)",
                confidence=0.91,
                details=(
                    "Errors, high utilization, and discards together suggest a "
                    "physically degraded link that is also being pushed near "
                    "capacity — a high-risk combination likely to cause an "
                    "outage if not addressed promptly."
                ),
                recommended_actions=[
                    "Immediate: open a P1 ticket and notify NOC",
                    "Schedule replacement of the optic/cable in the next maintenance window",
                    "Reduce load via QoS or traffic engineering until repaired",
                    "Verify failover paths are healthy",
                ],
            )
        return None
