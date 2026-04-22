"""
Text embedder.

Production: `sentence-transformers/all-MiniLM-L6-v2` (90 MB, 384 dim).
Dev / CI / cold-start: deterministic hash-based fallback that does not
require the model download and produces vectors of the same dimension.

The fallback is *not good for retrieval quality* — it exists only so the
pipeline runs end-to-end in tests and air-gapped environments. The
contract is that swapping in the real model changes only embedding
quality, not any code path.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

import numpy as np

from app.core import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 384  # matches all-MiniLM-L6-v2


class Embedder(Protocol):
    """Embedder protocol — any implementation must obey this."""

    dim: int

    def embed(self, text: str) -> np.ndarray: ...
    def embed_batch(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Production embedder using sentence-transformers."""

    dim = EMBEDDING_DIM

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        # Lazy import keeps cold-start cheap and lets the fallback work
        # in environments without sentence-transformers installed.
        from sentence_transformers import SentenceTransformer

        logger.info("loading_sentence_transformer", model=model_name)
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> np.ndarray:
        v = self._model.encode(text, normalize_embeddings=True)
        return np.asarray(v, dtype=np.float32)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        v = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
        return np.asarray(v, dtype=np.float32)


class HashFallbackEmbedder:
    """Deterministic hash-based embedder for dev / CI / air-gapped use.

    Maps each text to a fixed-dimension unit vector by hashing tokens
    into bucket positions. This gives meaningful (if shallow) similarity
    for texts that share vocabulary, which is enough to verify the
    pipeline wiring works.
    """

    dim = EMBEDDING_DIM

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim
        logger.warning(
            "using_hash_fallback_embedder",
            note="install sentence-transformers for production retrieval quality",
        )

    def embed(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        # Token-level hashing
        tokens = [t for t in text.lower().split() if t]
        if not tokens:
            return v
        for token in tokens:
            h = hashlib.md5(token.encode("utf-8")).digest()
            # Distribute across multiple buckets per token for richer signal
            for i in range(0, len(h), 4):
                idx = int.from_bytes(h[i:i + 4], "big") % self.dim
                # Sign bit from a different hash byte for some negative entries
                sign = 1.0 if h[i % len(h)] & 1 else -1.0
                v[idx] += sign
        # L2-normalize
        norm = np.linalg.norm(v)
        if norm > 0:
            v = v / norm
        return v

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        return np.stack([self.embed(t) for t in texts]) if texts else np.zeros(
            (0, self.dim), dtype=np.float32
        )


def get_embedder(prefer_real: bool = True) -> Embedder:
    """Factory — try the real embedder, fall back to hash if unavailable."""
    if prefer_real:
        try:
            return SentenceTransformerEmbedder()
        except ImportError as exc:
            logger.warning(
                "sentence_transformers_unavailable",
                error=str(exc),
                action="falling back to hash embedder",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("real_embedder_init_failed", error=str(exc))
    return HashFallbackEmbedder()


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Numerically safe cosine similarity for two L2-normalized vectors."""
    if a.shape != b.shape:
        return 0.0
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom < 1e-9:
        return 0.0
    return float(np.dot(a, b) / denom)
