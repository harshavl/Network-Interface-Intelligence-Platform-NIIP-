"""
Telemetry featurizer.

Converts the structured `InterfaceMetric + list[Anomaly]` into a
natural-language description suitable for embedding and LLM input.

This step matters more than people realize. The RCACopilot paper found
that summarized diagnostic information improved Micro-F1 by 0.077 over
raw diagnostic information — language quality directly affects retrieval
quality and LLM reasoning quality.

Design principle: every featurized description should be self-contained.
A retrieved historical incident should be understandable without reading
its raw telemetry — just the text.
"""

from __future__ import annotations

from app.models import Anomaly, AnomalyType, InterfaceMetric, Severity
from app.ml.root_cause_v2.types import IncidentFeatures


def _classify_device(device_name: str, interface_name: str) -> str:
    """Heuristic device-class inference from naming conventions.

    Real deployments would override this with a CMDB lookup. The
    heuristic is good enough to bootstrap and to exercise the pipeline.
    """
    name = device_name.lower()
    if "core" in name or "spine" in name:
        return "core_router"
    if "edge" in name or "fw" in name or "firewall" in name:
        return "edge_firewall"
    if "dist" in name or "leaf" in name:
        return "distribution_switch"
    if "access" in name:
        return "access_switch"
    if "dc-" in name or "datacenter" in name:
        return "datacenter_switch"
    return "unknown"


def _bucket_utilization(pct: float) -> str:
    if pct >= 90:
        return "saturated"
    if pct >= 70:
        return "high"
    if pct >= 40:
        return "moderate"
    if pct >= 10:
        return "light"
    return "idle"


def _bucket_count(value: int) -> str:
    if value == 0:
        return "none"
    if value < 10:
        return "few"
    if value < 100:
        return "moderate"
    if value < 500:
        return "many"
    return "extreme"


def featurize(
    metric: InterfaceMetric,
    anomalies: list[Anomaly],
) -> IncidentFeatures:
    """Build a featurized description of the current incident."""

    device_class = _classify_device(metric.device_name, metric.interface_name)

    # Build the natural-language summary
    util_in_bucket = _bucket_utilization(metric.in_utilization_percent)
    util_out_bucket = _bucket_utilization(metric.out_utilization_percent)
    err_bucket = _bucket_count(metric.total_errors)
    disc_bucket = _bucket_count(metric.total_discards)

    parts = [
        f"On a {device_class.replace('_', ' ')} ({metric.device_name}), "
        f"interface {metric.interface_name} "
        f"({metric.interface_description or 'no description'}) "
        f"is showing {util_in_bucket} inbound utilization "
        f"({metric.in_utilization_percent:.1f}%) "
        f"and {util_out_bucket} outbound utilization "
        f"({metric.out_utilization_percent:.1f}%)."
    ]

    if metric.total_errors > 0:
        parts.append(
            f"There are {err_bucket} errors in the last hour "
            f"({metric.in_errors_1h} inbound, {metric.out_errors_1h} outbound)."
        )

    if metric.total_discards > 0:
        parts.append(
            f"There are {disc_bucket} discards in the last hour "
            f"({metric.in_discards_1h} inbound, {metric.out_discards_1h} outbound)."
        )

    # Anomaly signatures — short tags useful for retrieval boosting
    anomaly_signatures: list[str] = []
    for a in anomalies:
        sig = f"{a.type.value}_{a.severity.value}"
        anomaly_signatures.append(sig)
        parts.append(f"Anomaly: {a.description}")

    summary_text = " ".join(parts)

    structured_metrics = {
        "device_name": metric.device_name,
        "interface_name": metric.interface_name,
        "interface_description": metric.interface_description,
        "in_utilization_percent": metric.in_utilization_percent,
        "out_utilization_percent": metric.out_utilization_percent,
        "in_errors_1h": metric.in_errors_1h,
        "out_errors_1h": metric.out_errors_1h,
        "in_discards_1h": metric.in_discards_1h,
        "out_discards_1h": metric.out_discards_1h,
        "max_utilization": metric.max_utilization,
        "total_errors": metric.total_errors,
        "total_discards": metric.total_discards,
    }

    return IncidentFeatures(
        device_class=device_class,
        summary_text=summary_text,
        structured_metrics=structured_metrics,
        anomaly_signatures=anomaly_signatures,
    )
