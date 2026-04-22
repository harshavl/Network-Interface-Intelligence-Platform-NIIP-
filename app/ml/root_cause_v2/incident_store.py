"""
Incident store — vector index of historical incidents.

Two backends:

  - `InMemoryIncidentStore`: numpy-based, suitable for dev, tests, and
    small deployments (<10K incidents). Loads from JSON on disk.

  - `PgVectorIncidentStore`: PostgreSQL with the `pgvector` extension,
    for production. Schema in `schema.sql`.

Both implement the `IncidentStore` Protocol so the engine treats them
identically.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol

import numpy as np

from app.core import get_logger
from app.ml.root_cause_v2.embedder import Embedder, cosine_similarity
from app.ml.root_cause_v2.types import HistoricalIncident, RetrievedIncident

logger = get_logger(__name__)


class IncidentStore(Protocol):
    """Vector-indexed store of historical incidents."""

    def add(self, incident: HistoricalIncident, embedding: np.ndarray) -> None: ...

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        device_class_filter: Optional[str] = None,
    ) -> list[RetrievedIncident]: ...

    def count(self) -> int: ...


class InMemoryIncidentStore:
    """Numpy-based in-memory store. Persists to JSON on `save()`."""

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._incidents: list[HistoricalIncident] = []
        self._embeddings: list[np.ndarray] = []

    def add(self, incident: HistoricalIncident, embedding: np.ndarray) -> None:
        if embedding.shape != (self._embedder.dim,):
            raise ValueError(
                f"Embedding dim mismatch: got {embedding.shape}, "
                f"expected ({self._embedder.dim},)"
            )
        self._incidents.append(incident)
        self._embeddings.append(embedding.astype(np.float32))

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        device_class_filter: Optional[str] = None,
    ) -> list[RetrievedIncident]:
        if not self._incidents:
            return []

        # Optional pre-filter on device class for tighter retrieval
        candidate_indices = list(range(len(self._incidents)))
        if device_class_filter:
            candidate_indices = [
                i for i in candidate_indices
                if self._incidents[i].device_class == device_class_filter
            ]
            if not candidate_indices:
                # Filter eliminated everything — fall back to no filter
                logger.debug(
                    "device_class_filter_empty_fallback",
                    filter=device_class_filter,
                )
                candidate_indices = list(range(len(self._incidents)))

        # Score
        scored: list[tuple[int, float]] = []
        for idx in candidate_indices:
            sim = cosine_similarity(query_embedding, self._embeddings[idx])
            scored.append((idx, sim))

        scored.sort(key=lambda t: t[1], reverse=True)
        top = scored[:k]
        return [
            RetrievedIncident(incident=self._incidents[i], similarity=sim)
            for i, sim in top
        ]

    def count(self) -> int:
        return len(self._incidents)

    # ---- persistence ----

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "embedding_dim": self._embedder.dim,
            "incidents": [
                {
                    "incident_id": inc.incident_id,
                    "timestamp": inc.timestamp.isoformat(),
                    "device_class": inc.device_class,
                    "text": inc.text,
                    "root_cause": inc.root_cause,
                    "root_cause_detail": inc.root_cause_detail,
                    "actions_taken": inc.actions_taken,
                    "resolution_minutes": inc.resolution_minutes,
                    "confidence_label": inc.confidence_label,
                    "metadata": inc.metadata,
                    "embedding": emb.tolist(),
                }
                for inc, emb in zip(self._incidents, self._embeddings)
            ],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        logger.info("incident_store_saved", path=str(path), count=len(self._incidents))

    @classmethod
    def load(cls, path: Path, embedder: Embedder) -> "InMemoryIncidentStore":
        path = Path(path)
        store = cls(embedder)
        if not path.exists():
            logger.info("incident_store_load_skip_missing", path=str(path))
            return store

        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("embedding_dim") != embedder.dim:
            logger.warning(
                "incident_store_dim_mismatch_reembedding",
                file_dim=data.get("embedding_dim"),
                embedder_dim=embedder.dim,
            )
            # Re-embed all incidents from text (different model in use)
            for raw in data["incidents"]:
                inc = cls._incident_from_dict(raw)
                emb = embedder.embed(inc.text)
                store.add(inc, emb)
        else:
            for raw in data["incidents"]:
                inc = cls._incident_from_dict(raw)
                emb = np.asarray(raw["embedding"], dtype=np.float32)
                store.add(inc, emb)
        logger.info("incident_store_loaded", path=str(path), count=store.count())
        return store

    @staticmethod
    def _incident_from_dict(raw: dict) -> HistoricalIncident:
        return HistoricalIncident(
            incident_id=raw["incident_id"],
            timestamp=datetime.fromisoformat(raw["timestamp"]),
            device_class=raw["device_class"],
            text=raw["text"],
            root_cause=raw["root_cause"],
            root_cause_detail=raw["root_cause_detail"],
            actions_taken=raw["actions_taken"],
            resolution_minutes=raw.get("resolution_minutes"),
            confidence_label=raw.get("confidence_label", 1.0),
            metadata=raw.get("metadata", {}),
        )


class PgVectorIncidentStore:
    """PostgreSQL + pgvector backend for production deployments.

    Skeleton implementation — wires the SQL but expects the caller to
    provide a connection pool. Schema is in `schema.sql`.
    """

    def __init__(self, embedder: Embedder, conn_pool) -> None:
        self._embedder = embedder
        self._pool = conn_pool

    def add(self, incident: HistoricalIncident, embedding: np.ndarray) -> None:
        sql = """
            INSERT INTO incidents
              (incident_id, ts, device_class, text, root_cause,
               root_cause_detail, actions_taken, resolution_minutes,
               confidence_label, metadata, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (incident_id) DO UPDATE
              SET text = EXCLUDED.text,
                  embedding = EXCLUDED.embedding;
        """
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (
                incident.incident_id,
                incident.timestamp,
                incident.device_class,
                incident.text,
                incident.root_cause,
                incident.root_cause_detail,
                json.dumps(incident.actions_taken),
                incident.resolution_minutes,
                incident.confidence_label,
                json.dumps(incident.metadata),
                embedding.tolist(),
            ))

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        device_class_filter: Optional[str] = None,
    ) -> list[RetrievedIncident]:
        # pgvector cosine distance operator: <=>
        # similarity = 1 - distance for normalized vectors
        if device_class_filter:
            sql = """
                SELECT incident_id, ts, device_class, text, root_cause,
                       root_cause_detail, actions_taken, resolution_minutes,
                       confidence_label, metadata,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM incidents
                WHERE device_class = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
            """
            params = (query_embedding.tolist(), device_class_filter,
                      query_embedding.tolist(), k)
        else:
            sql = """
                SELECT incident_id, ts, device_class, text, root_cause,
                       root_cause_detail, actions_taken, resolution_minutes,
                       confidence_label, metadata,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM incidents
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
            """
            params = (query_embedding.tolist(), query_embedding.tolist(), k)

        results: list[RetrievedIncident] = []
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            for row in cur.fetchall():
                inc = HistoricalIncident(
                    incident_id=row[0],
                    timestamp=row[1],
                    device_class=row[2],
                    text=row[3],
                    root_cause=row[4],
                    root_cause_detail=row[5],
                    actions_taken=json.loads(row[6]) if row[6] else [],
                    resolution_minutes=row[7],
                    confidence_label=row[8],
                    metadata=json.loads(row[9]) if row[9] else {},
                )
                results.append(RetrievedIncident(incident=inc, similarity=float(row[10])))
        return results

    def count(self) -> int:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM incidents;")
            return int(cur.fetchone()[0])
