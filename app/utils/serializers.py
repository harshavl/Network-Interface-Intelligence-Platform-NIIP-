"""Serialization helpers — convert dataclass models to JSON-friendly dicts."""

from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from typing import Any

from app.models import AnalysisReport, InterfaceAnalysis


def _coerce(obj: Any) -> Any:
    """Recursively convert enums and exclude None-only artifacts cleanly."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _coerce(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce(i) for i in obj]
    return obj


def serialize_interface_analysis(analysis: InterfaceAnalysis) -> dict:
    """Convert one InterfaceAnalysis to a clean dict for JSON output."""
    raw = asdict(analysis)
    # Drop heavy raw_metrics from default output
    #raw.pop("raw_metrics", None)
    return _coerce(raw)


def serialize_report(report: AnalysisReport) -> dict:
    """Convert a full AnalysisReport to a clean dict."""
    return {
        "analysis_timestamp": report.analysis_timestamp,
        "summary": _coerce(asdict(report.summary)),
        "interfaces": [serialize_interface_analysis(i) for i in report.interfaces],
    }
