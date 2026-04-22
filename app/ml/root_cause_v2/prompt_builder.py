"""
Prompt assembly for the LLM root cause call.

Builds two-part input:

  - **System prompt**: the SOP (Standard Operating Procedure), loaded
    once at startup and cached.
  - **User prompt**: featurized current incident + retrieved historical
    examples in a structured format the LLM can reliably parse.

Design principle: the prompt is the contract. Changes here are
behavior-changing and must be versioned.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.ml.root_cause_v2.types import IncidentFeatures, RetrievedIncident

PROMPT_VERSION = "v2.0.0"


def load_sop(sop_path: Optional[Path] = None) -> str:
    """Load the SOP markdown document."""
    if sop_path is None:
        sop_path = Path(__file__).parent / "sop" / "network_interface_rca.md"
    return Path(sop_path).read_text(encoding="utf-8")


def build_user_prompt(
    features: IncidentFeatures,
    retrieved: list[RetrievedIncident],
) -> str:
    """Assemble the user-side prompt with telemetry + retrieved cases."""

    metrics_json = json.dumps(features.structured_metrics, indent=2)

    retrieved_section = _format_retrieved(retrieved)

    return (
        "## Current incident\n\n"
        f"### Device class: {features.device_class}\n\n"
        f"### Natural-language summary\n{features.summary_text}\n\n"
        f"### Raw metrics\n```json\n{metrics_json}\n```\n\n"
        f"### Anomaly signatures\n"
        f"{', '.join(features.anomaly_signatures) if features.anomaly_signatures else 'none'}\n\n"
        "## Retrieved historical incidents\n\n"
        f"{retrieved_section}\n\n"
        "## Your task\n\n"
        "Apply the SOP and emit a single JSON object as your entire response. "
        "No markdown fences, no commentary outside the JSON.\n"
    )


def _format_retrieved(retrieved: list[RetrievedIncident]) -> str:
    if not retrieved:
        return "(no similar historical incidents found in the knowledge base)"

    chunks: list[str] = []
    for i, hit in enumerate(retrieved, start=1):
        inc = hit.incident
        actions = "\n".join(f"  - {a}" for a in inc.actions_taken)
        chunks.append(
            f"### Historical incident #{i}\n"
            f"- **incident_id**: `{inc.incident_id}`\n"
            f"- **similarity**: {hit.similarity:.3f}\n"
            f"- **device_class**: {inc.device_class}\n"
            f"- **confidence_label**: {inc.confidence_label}\n"
            f"- **resolution_minutes**: {inc.resolution_minutes}\n"
            f"- **summary**: {inc.text}\n"
            f"- **confirmed_root_cause**: `{inc.root_cause}` — {inc.root_cause_detail}\n"
            f"- **actions_that_worked**:\n{actions}\n"
        )
    return "\n".join(chunks)
