"""
Bootstrap the in-memory incident store from a JSON seed file.

Usage:
    python -m app.ml.root_cause_v2.bootstrap \
        --input data/incidents/seed_incidents.json \
        --output data/incidents/incident_store.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from app.core import configure_logging, get_logger, get_settings
from app.ml.root_cause_v2.embedder import get_embedder
from app.ml.root_cause_v2.incident_store import InMemoryIncidentStore
from app.ml.root_cause_v2.types import HistoricalIncident

logger = get_logger(__name__)


def bootstrap(input_path: Path, output_path: Path) -> int:
    embedder = get_embedder()
    store = InMemoryIncidentStore(embedder)

    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print(f"ERROR: expected JSON array at top level of {input_path}", file=sys.stderr)
        return 2

    added = 0
    for r in raw:
        try:
            inc = HistoricalIncident(
                incident_id=r["incident_id"],
                timestamp=datetime.fromisoformat(r["timestamp"]),
                device_class=r["device_class"],
                text=r["text"],
                root_cause=r["root_cause"],
                root_cause_detail=r["root_cause_detail"],
                actions_taken=r["actions_taken"],
                resolution_minutes=r.get("resolution_minutes"),
                confidence_label=r.get("confidence_label", 1.0),
                metadata=r.get("metadata", {}),
            )
        except KeyError as exc:
            logger.error("seed_incident_missing_field", incident=r.get("incident_id"), field=str(exc))
            continue
        embedding = embedder.embed(inc.text)
        store.add(inc, embedding)
        added += 1

    store.save(output_path)
    print(f"Bootstrapped {added} incidents → {output_path}")
    return 0


def main() -> int:
    settings = get_settings() if False else None  # avoid load if env not set
    if settings:
        configure_logging(settings)
    parser = argparse.ArgumentParser(description="Bootstrap the incident knowledge base")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/incidents/seed_incidents.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/incidents/incident_store.json"),
    )
    args = parser.parse_args()
    return bootstrap(args.input, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
