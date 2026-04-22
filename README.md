# Network Interface Intelligence Platform (NIIP)

ML-powered observability layer for network interface telemetry. Ingests data from LogicMonitor (and similar NPM tools), and provides:

- **Anomaly Detection** — Multivariate (Isolation Forest) + univariate (Z-score on residuals) anomaly detection
- **Forecasting** — Holt-Winters exponential smoothing for capacity planning
- **Root Cause Suggestions** — Rule-augmented classifier for actionable diagnostics
- **Health Scoring** — Composite 0–100 score per interface

## Architecture

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ LogicMonitor CSV │───▶│  Flask REST API  │───▶│   ML Pipeline    │
│   (or upload)    │    │  (Flask-RESTX)   │    │  (4 engines)     │
└──────────────────┘    └──────────────────┘    └──────────────────┘
                                │                         │
                                ▼                         ▼
                        ┌──────────────────────────────────────┐
                        │  JSON Response + Persisted Reports   │
                        └──────────────────────────────────────┘
```

## Requirements

- Python 3.10–3.12
- Poetry 1.5+

## Quick Start

```bash
# 1. Install dependencies
poetry install

# 2. Copy environment file
cp .env.example .env

# 3. Run the API server
poetry run python -m app.main

# Or via gunicorn (production-like)
poetry run gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

The API will be available at `http://localhost:5000`.
Interactive Swagger UI at `http://localhost:5000/api/docs`.

## Test the API

A sample LogicMonitor-style CSV is included at `data/input/sample_logicmonitor_export.csv`.

### Health check
```bash
curl http://localhost:5000/api/v1/health
```

### Analyze the sample CSV file
```bash
curl -X POST http://localhost:5000/api/v1/analysis/upload \
  -F "file=@data/input/sample_logicmonitor_export.csv" \
  -H "Accept: application/json" | python -m json.tool
```

### Analyze JSON payload directly
```bash
curl -X POST http://localhost:5000/api/v1/analysis/analyze \
  -H "Content-Type: application/json" \
  -d @data/input/sample_payload.json | python -m json.tool
```

### Get analysis summary only
```bash
curl -X POST http://localhost:5000/api/v1/analysis/summary \
  -F "file=@data/input/sample_logicmonitor_export.csv" | python -m json.tool
```

## CLI Usage

```bash
# Analyze a file via the CLI
poetry run python -m app.cli analyze data/input/sample_logicmonitor_export.csv

# Output as JSON
poetry run python -m app.cli analyze data/input/sample_logicmonitor_export.csv --format json

# Save report to file
poetry run python -m app.cli analyze data/input/sample_logicmonitor_export.csv -o report.json
```

## Run Tests

```bash
poetry run pytest
poetry run pytest --cov=app --cov-report=html
```

## Project Structure

```
niip/
├── app/
│   ├── api/              # Flask REST endpoints
│   ├── core/             # Config, logging, error handlers
│   ├── ml/               # 4 ML engines
│   ├── models/           # Domain models (dataclasses)
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── utils/            # Helpers
│   ├── __init__.py       # App factory
│   ├── cli.py            # Command-line interface
│   └── main.py           # Entry point
├── tests/                # pytest test suite
├── data/
│   ├── input/            # Sample CSV inputs
│   └── output/           # Generated reports
├── pyproject.toml        # Poetry configuration
└── README.md
```

## Expected Input Schema

The CSV must have these columns (case-insensitive, spaces or underscores both fine):

| Column                       | Type    | Description                       |
| ---------------------------- | ------- | --------------------------------- |
| `device_name`                | string  | Network device hostname           |
| `interface_name`             | string  | Interface identifier              |
| `interface_description`      | string  | Free-text description             |
| `in_utilization_percent`     | float   | Inbound utilization (0–100)       |
| `out_utilization_percent`    | float   | Outbound utilization (0–100)      |
| `in_errors_1h`               | int     | Inbound errors in last hour       |
| `out_errors_1h`              | int     | Outbound errors in last hour      |
| `in_discards_1h`             | int     | Inbound discards in last hour     |
| `out_discards_1h`            | int     | Outbound discards in last hour    |

## License

MIT

---

# Operator Dashboard (React frontend)

A React + Vite operator dashboard lives in the `frontend/` directory.

## Quick start

```bash
# Terminal 1 — Flask backend
poetry run python -m app.main

# Terminal 2 — Vite dev server
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Click **LOAD SAMPLE** to analyze the bundled CSV, or drag-and-drop your own.

See `frontend/README.md` for production build and nginx deployment examples.

## Design

Industrial NOC terminal aesthetic — dense monospace UI (JetBrains Mono + Space Grotesk), tactical color palette (cyan/amber/red on near-black). Built for engineers who want signal, not decoration.

**Components**: live status bar with backend health polling, six-tile KPI summary, score-distribution histogram, sortable/filterable fleet table with search, click-to-drill interface detail panel showing anomalies / forecast / root cause / recommended actions. Fully keyboard-accessible and responsive.

---

# Root Cause Engine v2 (RAG + LLM)

In addition to the v1 rule-based engine, this project includes a second-generation root cause engine based on the RCACopilot architecture (Microsoft, EuroSys 2024) with SOP-constrained generation (Flow-of-Action, Web Conf 2025).

See `docs/root_cause_v2_architecture.md` for the design rationale.

## Quick start (stub mode — no API key required)

```bash
# 1. Bootstrap the knowledge base from the seed incidents
poetry run python -m app.ml.root_cause_v2.bootstrap \
    --input data/incidents/seed_incidents.json \
    --output data/incidents/incident_store.json

# 2. Use v2 in code
python3 -c "
from app.core import get_settings
from app.ml.root_cause_v2 import RootCauseEngineV2
from app.ml.root_cause_v2.embedder import HashFallbackEmbedder
from app.ml.root_cause_v2.incident_store import InMemoryIncidentStore
from app.ml.root_cause_v2.llm_client import StubLLMClient
from pathlib import Path

embedder = HashFallbackEmbedder()
store = InMemoryIncidentStore.load(Path('data/incidents/incident_store.json'), embedder)
engine = RootCauseEngineV2(
    get_settings(), embedder=embedder, store=store,
    llm_client=StubLLMClient(),
)
print(f'KB has {engine.knowledge_base_size} incidents')
"
```

## Production mode

```bash
# 1. Install optional extras
poetry install --extras rca_v2          # with pgvector: --extras rca_v2_pg

# 2. Set environment
export ANTHROPIC_API_KEY=sk-ant-...

# 3. Bootstrap with real sentence-transformer embeddings
poetry run python -m app.ml.root_cause_v2.bootstrap

# 4. Swap the import in app/services/analysis_service.py:
#    from app.ml import RootCauseEngine          → old
#    from app.ml.root_cause_v2 import RootCauseEngineV2 as RootCauseEngine
```

## Adding new labeled incidents to the knowledge base

Append to `data/incidents/seed_incidents.json` and re-run bootstrap — or call
`engine.add_incident(...)` at runtime to grow the KB without a restart.

## PostgreSQL + pgvector schema

See `app/ml/root_cause_v2/schema.sql`. Apply with:
```bash
psql -U niip -d niip -f app/ml/root_cause_v2/schema.sql
```
