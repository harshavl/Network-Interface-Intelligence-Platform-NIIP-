"""
Root cause engine — public interface, RAG + LLM orchestration.

Pipeline:

  featurize → embed → retrieve → build prompt → LLM → parse → validate
                                                                  │
                                                                  ├─ ok? → emit
                                                                  └─ fail/low-conf → fall back to v1 rule engine

The fallback is the safety net that makes this safe to deploy. The
Flow-of-Action (Web Conf 2025) paper found that pure LLM RCA hallucinates
under load; constraining with SOPs + having a deterministic fallback
keeps reliability acceptable for production NOC use.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

from app.core import Settings, get_logger
from app.ml.root_cause import RootCauseEngine as V1RuleEngine  # fallback
from app.ml.root_cause_v2.embedder import Embedder, get_embedder
from app.ml.root_cause_v2.featurizer import featurize
from app.ml.root_cause_v2.incident_store import (
    IncidentStore,
    InMemoryIncidentStore,
)
from app.ml.root_cause_v2.llm_client import LLMClient, StubLLMClient, get_llm_client
from app.ml.root_cause_v2.parser import ParseError, parse_llm_response
from app.ml.root_cause_v2.prompt_builder import (
    PROMPT_VERSION,
    build_user_prompt,
    load_sop,
)
from app.models import Anomaly, InterfaceMetric, RootCauseSuggestion

logger = get_logger(__name__)

# Defaults — overridable via constructor args
DEFAULT_TOP_K = 5
DEFAULT_MIN_CONFIDENCE = 0.5     # below this, fall back to rules
DEFAULT_MIN_SIMILARITY = 0.45    # below this, treat as cold-start


class RootCauseEngineV2:
    """RAG + LLM root cause engine. Drop-in replacement for v1.

    Public method `suggest(metric, anomalies)` matches the v1 signature
    exactly so the orchestrator only needs an import swap.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        embedder: Optional[Embedder] = None,
        store: Optional[IncidentStore] = None,
        llm_client: Optional[LLMClient] = None,
        sop_path: Optional[Path] = None,
        top_k: int = DEFAULT_TOP_K,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
    ) -> None:
        self.settings = settings
        self._embedder = embedder or get_embedder()
        self._store = store or InMemoryIncidentStore(self._embedder)
        self._llm = llm_client or get_llm_client()
        self._sop = load_sop(sop_path)
        self._top_k = top_k
        self._min_confidence = min_confidence
        self._min_similarity = min_similarity
        self._fallback = V1RuleEngine(settings)

        logger.info(
            "root_cause_engine_v2_initialized",
            embedder=type(self._embedder).__name__,
            store=type(self._store).__name__,
            llm=type(self._llm).__name__,
            store_size=self._store.count(),
            prompt_version=PROMPT_VERSION,
            top_k=top_k,
            min_confidence=min_confidence,
            min_similarity=min_similarity,
        )

    # ---------------- public ----------------

    def suggest(
        self,
        metric: InterfaceMetric,
        anomalies: list[Anomaly],
    ) -> Optional[RootCauseSuggestion]:
        """Return a `RootCauseSuggestion` or `None` if nothing is wrong."""
        if not anomalies:
            return None

        request_id = str(uuid.uuid4())
        t0 = time.monotonic()

        # 1. Featurize
        features = featurize(metric, anomalies)

        # 2. Embed
        try:
            query_embedding = self._embedder.embed(features.summary_text)
        except Exception as exc:  # noqa: BLE001
            logger.exception("embedding_failed", request_id=request_id, error=str(exc))
            return self._use_fallback(metric, anomalies, reason="embedding_failed")

        # 3. Retrieve
        try:
            retrieved = self._store.search(
                query_embedding,
                k=self._top_k,
                device_class_filter=features.device_class
                if features.device_class != "unknown"
                else None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("retrieval_failed", request_id=request_id, error=str(exc))
            return self._use_fallback(metric, anomalies, reason="retrieval_failed")

        top_similarity = retrieved[0].similarity if retrieved else 0.0

        # Cold start — empty store or all retrievals too dissimilar
        if not retrieved or top_similarity < self._min_similarity:
            logger.info(
                "cold_start_fallback",
                request_id=request_id,
                interface=metric.interface_id,
                store_size=self._store.count(),
                top_similarity=top_similarity,
                min_similarity=self._min_similarity,
            )
            return self._use_fallback(metric, anomalies, reason="cold_start")

        # 4. Build prompt
        user_prompt = build_user_prompt(features, retrieved)

        # If using the stub LLM, hand it the retrieved list directly
        if isinstance(self._llm, StubLLMClient):
            self._llm.set_retrieved(retrieved)

        # 5. LLM call
        try:
            raw = self._llm.complete(
                system_prompt=self._sop,
                user_prompt=user_prompt,
                max_tokens=1024,
                temperature=0.0,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("llm_call_failed", request_id=request_id, error=str(exc))
            return self._use_fallback(metric, anomalies, reason="llm_call_failed")

        # 6. Parse + validate
        try:
            parsed = parse_llm_response(raw)
        except ParseError as exc:
            logger.warning(
                "llm_parse_failed",
                request_id=request_id,
                error=exc.message,
                details=exc.details,
            )
            return self._use_fallback(metric, anomalies, reason="parse_failed")

        # 7. Confidence threshold
        if parsed.confidence < self._min_confidence:
            logger.info(
                "low_confidence_fallback",
                request_id=request_id,
                llm_confidence=parsed.confidence,
                min_confidence=self._min_confidence,
            )
            return self._use_fallback(metric, anomalies, reason="low_confidence")

        # 8. Done
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        logger.info(
            "root_cause_v2_success",
            request_id=request_id,
            interface=metric.interface_id,
            confidence=parsed.confidence,
            top_similarity=top_similarity,
            references=parsed.referenced_incident_ids,
            elapsed_ms=round(elapsed_ms, 1),
        )

        return RootCauseSuggestion(
            probable_cause=parsed.probable_cause,
            confidence=parsed.confidence,
            details=parsed.details,
            recommended_actions=parsed.recommended_actions,
        )

    # ---------------- helpers ----------------

    def _use_fallback(
        self,
        metric: InterfaceMetric,
        anomalies: list[Anomaly],
        reason: str,
    ) -> Optional[RootCauseSuggestion]:
        """Fall back to the v1 rule engine; annotate confidence."""
        result = self._fallback.suggest(metric, anomalies)
        if result is None:
            return None
        # Mark fallback by capping confidence and tagging details
        capped_confidence = min(result.confidence, 0.7)
        return RootCauseSuggestion(
            probable_cause=result.probable_cause,
            confidence=capped_confidence,
            details=f"[Rule-based fallback: {reason}] {result.details}",
            recommended_actions=result.recommended_actions,
        )

    # ---------------- knowledge base management ----------------

    def add_incident(self, incident, embedding=None) -> None:
        """Add a labeled historical incident to the knowledge base.

        If `embedding` is None, it is computed from `incident.text`.
        """
        if embedding is None:
            embedding = self._embedder.embed(incident.text)
        self._store.add(incident, embedding)
        logger.info(
            "incident_added_to_kb",
            incident_id=incident.incident_id,
            store_size=self._store.count(),
        )

    @property
    def knowledge_base_size(self) -> int:
        return self._store.count()
