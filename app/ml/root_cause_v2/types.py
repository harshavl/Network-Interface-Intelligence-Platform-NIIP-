"""
Internal types for the RAG-based root cause engine.

These are dataclasses used inside the pipeline. They are deliberately
distinct from `app.models.RootCauseSuggestion` (the public output type)
so that pipeline-internal restructuring does not break the API contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class HistoricalIncident:
    """One historical incident stored in the vector index.

    The `text` field is what gets embedded — a natural-language
    description that combines telemetry features and human notes. The
    structured fields (`root_cause`, `actions_taken`) are what the LLM
    sees as ground-truth examples in the RAG prompt.
    """

    incident_id: str
    timestamp: datetime
    device_class: str           # "core_router", "access_switch", etc.
    text: str                   # the embedded description
    root_cause: str             # canonical category (e.g. "physical_layer")
    root_cause_detail: str      # free-form explanation
    actions_taken: list[str]    # remediation steps that worked
    resolution_minutes: Optional[int] = None
    confidence_label: float = 1.0   # 1.0 = engineer-confirmed; <1.0 = inferred
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievedIncident:
    """A historical incident returned by the retriever, with similarity score."""

    incident: HistoricalIncident
    similarity: float           # cosine similarity, 0.0 – 1.0


@dataclass
class IncidentFeatures:
    """Featurized representation of the current telemetry being analyzed."""

    device_class: str
    summary_text: str           # natural-language summary used for embedding
    structured_metrics: dict    # raw numbers for the prompt
    anomaly_signatures: list[str]   # short tags per anomaly


@dataclass
class LLMRootCauseResponse:
    """Raw structured output parsed from the LLM call.

    Kept separate from `RootCauseSuggestion` so the parser can validate
    fields before the orchestrator constructs the public type.
    """

    probable_cause: str
    confidence: float           # raw LLM-reported confidence, 0.0–1.0
    details: str
    recommended_actions: list[str]
    referenced_incident_ids: list[str] = field(default_factory=list)
    reasoning: str = ""
