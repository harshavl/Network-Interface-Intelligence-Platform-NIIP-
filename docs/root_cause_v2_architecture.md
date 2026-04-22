# Root Cause Engine v2 — RAG + LLM Architecture

## Pattern: RCACopilot (EuroSys 2024)

This module replaces the v1 hand-coded rule engine in `app/ml/root_cause.py`
with a Retrieval-Augmented Generation (RAG) pipeline backed by a frontier LLM.

The architecture follows the RCACopilot paper from Microsoft, which has been
in production at Microsoft for 4+ years across 30+ teams.

## Why RAG instead of fine-tuning?

The Microsoft team rigorously evaluated both approaches and concluded:

> Fine-tuning has limitations: (1) accurate RCA requires various sources of
> complex unstructured data — just using a generic title and summary might
> miss useful signals; (2) fine-tuning is costly and may require a huge
> volume of training samples; (3) it is challenging to continuously update
> a fine-tuned GPT model with the evolving nature and scope of incidents.

RAG sidesteps all three problems: new incidents are added by inserting one
vector, not retraining a model.

## Pipeline (5 stages)

```
1. Featurize     │ telemetry → structured incident description
2. Retrieve      │ embed query → top-K similar historical incidents
3. Compose       │ build prompt: SOP + telemetry + retrieved cases
4. Reason        │ LLM generates root cause + actions + confidence
5. Validate      │ schema check + confidence threshold + fallback to rules
```

## Why a fallback to rules?

LLM RCA can hallucinate. The Flow-of-Action paper (WebConf 2025) addresses
this with SOP-constrained generation. We adopt a simpler version: if the LLM's
self-reported confidence is below a threshold, or if its output fails schema
validation, we fall back to the v1 rule engine. This guarantees the system
always produces *something* sensible.

## Confidence calibration

We follow the LM-PACE approach (FSE Industry 2024) — the LLM is prompted to
emit a numeric confidence (0.0–1.0) along with its reasoning. We then
recalibrate this against historical accuracy on a held-out set, since raw
LLM confidence is poorly calibrated by default.

## Components

| File                    | Purpose                                    |
| ----------------------- | ------------------------------------------ |
| `incident_store.py`     | Vector DB abstraction (pgvector default)   |
| `embedder.py`           | Text → embedding (sentence-transformers)   |
| `featurizer.py`         | Telemetry → natural-language description   |
| `retriever.py`          | Top-K similar incident lookup              |
| `prompt_builder.py`     | Assemble RAG prompt from components        |
| `llm_client.py`         | Anthropic API wrapper (configurable)       |
| `parser.py`             | Parse + validate LLM output                |
| `engine.py`             | Orchestrator — the public interface        |
| `sop/`                  | Standard Operating Procedure documents     |
| `fallback.py`           | Re-export of v1 rule engine for fallback   |
```

## Public interface (drop-in compatible with v1)

```python
from app.ml.root_cause_v2 import RootCauseEngineV2

engine = RootCauseEngineV2(settings)
suggestion = engine.suggest(metric, anomalies)  # → RootCauseSuggestion | None
```

The return type is unchanged, so the orchestrator in
`app/services/analysis_service.py` requires only the import to be swapped.

## Operational dependencies

- Anthropic API key (or OpenAI / Bedrock — provider is pluggable)
- PostgreSQL with pgvector extension (or in-memory fallback for dev)
- sentence-transformers model: `all-MiniLM-L6-v2` (90 MB, runs CPU-fast)
- Historical incident corpus: bootstrap with 50–100 labeled examples
