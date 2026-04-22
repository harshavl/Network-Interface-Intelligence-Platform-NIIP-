"""
RAG + LLM root cause engine — v2.

Drop-in replacement for the v1 rule-based engine, following the
RCACopilot architecture (EuroSys 2024) with SOP-constrained generation
(Flow-of-Action, Web Conf 2025).

Public surface:

    from app.ml.root_cause_v2 import RootCauseEngineV2, HistoricalIncident
    engine = RootCauseEngineV2(settings)
    suggestion = engine.suggest(metric, anomalies)
"""

from app.ml.root_cause_v2.engine import RootCauseEngineV2
from app.ml.root_cause_v2.types import (
    HistoricalIncident,
    IncidentFeatures,
    LLMRootCauseResponse,
    RetrievedIncident,
)

__all__ = [
    "RootCauseEngineV2",
    "HistoricalIncident",
    "IncidentFeatures",
    "LLMRootCauseResponse",
    "RetrievedIncident",
]
