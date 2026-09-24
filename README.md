# MetricMind — Governed Conversational BI with an Enterprise Semantic Layer

An agentic-AI analytics platform where **the LLM never writes SQL**. The model orchestrates a
governed [Cube.dev](https://cube.dev) semantic layer: it picks *what* to ask (governed metrics,
dimensions, time ranges) and the semantic layer decides *how* every number is computed.

```bash
docker compose -f infra/docker-compose.yml up --build
# → open http://localhost:3000 and ask:
#   "Why did European margins drop last quarter?"
```

---

## Architecture

```text
┌──────────────────────────────── apps/web ────────────────────────────────┐
│ Next.js 14 · Tremor · ECharts                                           │
│  Chat panel (SSE streaming) · reasoning cards · bar/line/KPI charts     │
│  "Metric definition used: …" badges · governed-vs-rogue code-gen view   │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ POST /api/chat  (SSE, proxied /api/*)
┌───────────────────────────────▼──────────────── apps/api ────────────────┐
│ FastAPI agent orchestrator (LangChain)                                  │
│  system prompt: NEVER SQL · always cite the metric definition           │
│  tools: list_metrics() · query_metric() · compare_periods()             │
│  drivers: OpenAI-compatible LLM (Llama 3 / OpenAI) or offline mock      │
│  chart/KPI specs + rogue Text-to-SQL comparison (embedded DuckDB)       │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ validated JSON queries (never SQL)
                        ┌───────▼──────────────────────────┐
                        │ Cube REST API  :4000             │
                        │ /cubejs-api/v1/meta   /load      │
                        │ services/semantic (metrics-as-   │
                        │ code YAML + pre-aggregations)    │
                        └───────┬──────────────────────────┘
                                │ SQL emitted by the semantic layer only
                        ┌───────▼──────────────────────────┐
                        │ Postgres (governed warehouse)    │
                        │ seeded from seeds/*.csv on boot  │
                        └──────────────────────────────────┘
```

```mermaid
flowchart LR
    U[Business user] -->|natural language| W["apps/web<br/>Next.js + Tremor + ECharts"]
    W -->|POST /api/chat (SSE)| A["apps/api<br/>FastAPI + LangChain agent"]
    A -->|"tool calls: list_metrics /<br/>query_metric / compare_periods"| C["Cube REST API<br/>services/semantic"]
    C -->|SQL only here| P[(Postgres<br/>seeded demo data)]
    A -.->|embedded DuckDB| R["rogue Text-to-SQL<br/>(problem demo)"]
    C -->|metric definitions| A
    A -->|steps · charts · KPIs · badges| W
```

**Repo layout**

```text
metricmind/
├── apps/web/           # Next.js 14 + Tremor + ECharts chat UI
├── apps/api/           # FastAPI agent orchestrator (LangChain, SSE)
├── services/semantic/  # Cube.dev semantic layer — metrics as code (YAML)
├── infra/              # Docker Compose: Postgres · Cube · API · Web
└── seeds/              # ~14k rows of demo sales/finance data (EU/US/APAC, last 4 quarters)
```

---

## Quickstart

**Prerequisites:** Docker + Docker Compose v2.

```bash
docker compose -f infra/docker-compose.yml up --build
```

On first boot Postgres runs `seeds/01_schema.sql` + `seeds/02_load.sql` (10k orders,
800 customers, 3 regions, 3,200 customer-quarter retention rows across EU/US/APAC for the
last 4 quarters), Cube compiles the semantic model, the API starts, Next.js builds.

| Service | URL | What it is |
|---|---|---|
| Web UI | http://localhost:3000 | Conversational BI interface |
| API | http://localhost:8010/docs | FastAPI orchestrator (SSE at `POST /api/chat`) |
| Cube | http://localhost:4000 | Semantic layer REST API (`/cubejs-api/v1/load`, `/meta`) |

Ports are overridable (`WEB_PORT`, `API_PORT`, `CUBE_PORT`); the API defaults to
**8010** because 8000 is a busy dev port. Containers talk to each other on their
internal ports regardless.

Stop with `Ctrl-C` (or `docker compose -f infra/docker-compose.yml down`; add `-v` to reset
the warehouse).

### The end-to-end demo

Open http://localhost:3000 and ask **“Why did European margins drop last quarter?”** You will
watch the agent decompose it into governed steps:

1. `list_metrics` — load governed metric definitions from Cube's metadata API;
2. `query_metric` — margin by region, last completed quarter (isolates the EU drop);
3. `compare_periods` — margin per region, QoQ (EU −8.8pp while US/APAC rise);
4. `compare_periods` — EU COGS by category, QoQ (top cost drivers: Hardware, Software);
5. `query_metric` — EU margin trend over the last 4 quarters (context).

Then the streamed narration, an ECharts bar/line chart, delta KPI cards, the
**“Metric definition used: margin = (revenue − COGS) / revenue”** badges, and the
**code-gen panel** showing the governed Cube query next to the SQL an ungoverned
Text-to-SQL model would have written (and the numbers each one produced).

---

## Module 1 — Semantic layer (`services/semantic/`)

* **Cubes** (`model/*.yml`): `orders` (fact + joins to customers/regions), `customers`,
  `regions` (board-approved margin targets) and `customer_activity` (per-customer, per-quarter
  retention flags that make governed churn computable).
* **Metrics as code**, e.g. in `model/orders.yml`:

  ```yaml
  - name: revenue
    sql: order_amount
    type: sum          # revenue = SUM(order_amount)
  - name: margin
    sql: "({revenue} - {cogs}) / NULLIF({revenue}, 0)"
    type: number       # margin = (revenue − COGS) / revenue — ratio of sums
  ```

  Plus `churn_rate = churned_customers / active_customers`, `order_count`, `units_sold`,
  `average_discount`, and a `quarter` time dimension (`to_char(order_date, 'YYYY-"Q"Q')`).
* **Pre-aggregations**: an `orders_rollup` rollup (revenue/cogs/count/units ×
  region/market/category/channel/segment × quarter, `scheduled_refresh: true`) so governed
  queries answer from the materialised rollup; margin is derived from the constituents.
* **REST API**: everything goes through `/cubejs-api/v1/load` (JWT auth via `CUBE_API_SECRET`)
  and `/cubejs-api/v1/meta` (the metric catalog the agent cites).

## Module 2 — Agentic orchestrator (`apps/api/`)

* **Tools** (`app/tools.py`) — the *only* data path, all three return JSON:
  * `list_metrics()` — governed definitions fetched from the Cube metadata API;
  * `query_metric(metric, dimensions, time_range, filters, granularity)` — builds a Cube
    JSON query from **validated** metric/dimension names → `/cubejs-api/v1/load`;
  * `compare_periods(metric, dimensions, period_a, period_b, filters)` — two governed
    queries + per-dimension delta / delta_pct.
* **No SQL, enforced mechanically** (`app/catalog.py`, `app/tools.py`): every name is resolved
  against `/meta`; unknown metrics/dimensions are rejected with a helpful error; there is no
  SQL tool, no warehouse connection, and queries are JSON only. The system prompt
  (`app/prompts.py`) adds the behavioural contract: never generate SQL, never invent numbers,
  and end every answer with `Metric definition used: <formula>`.
* **Multi-step reasoning**: the prompt's playbook (isolate → drill down → trend → narrate) is
  what produces the decomposition above; each tool call is streamed to the UI as a reasoning
  card containing the exact Cube query and definitions used.
* **Drivers** (`app/drivers.py`): `LLM_PROVIDER=openai` talks to any OpenAI-compatible endpoint
  (Ollama + Llama 3, vLLM, OpenAI) through LangChain streaming tool calls;
  `LLM_PROVIDER=mock` (default) is a deterministic offline agent with the same tools, so the
  demo runs with **zero credentials** — every number it narrates is still parsed out of real
  tool payloads, never hardcoded.
* **Streaming**: `POST /api/chat` emits SSE events —
  `run → (text | step | chart | kpi | codegen)* → definitions → done`.
* **The problem demo** (`app/rogue.py`): from the governed query that just ran, it synthesises
  the SQL a naive Text-to-SQL model would emit (fan-out join, gross revenue ignoring discounts,
  hard-coded dates), executes it in **embedded DuckDB** over the raw seed CSVs, and returns
  both result sets so the UI can show the divergence.

## Module 3 — Conversational BI interface (`apps/web/`)

* Chat panel streaming answers token-by-token (custom SSE parser over `fetch`), with
  expandable **reasoning cards**: tool name, arguments, resolved period, filters, the exact
  Cube query and a preview of the rows it returned.
* Charts derived from **structured tool results**, never from prose: ECharts bar/line
  (margins by region, quarterly trend) + Tremor KPI cards with delta chips (pp for ratios,
  % for amounts, coloured by whether the move is good for that metric).
* **Trust badges** on every answer: `Metric definition used: margin = (revenue − COGS) / revenue`,
  sourced from the Cube metadata API.
* **Code-gen view**: side-by-side governed Cube query vs rogue Text-to-SQL, the detected
  defects (fan-out, gross revenue, hard-coded dates, ungoverned definitions) and a
  governed-vs-rogue number comparison.
* Sidebar: live health (Cube / API / LLM driver) and the governed metric catalog.

---

## Configuration

Copy `apps/api/.env.example` (all values have defaults; compose exposes them as variables):

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `mock` | `mock` (offline demo) or `openai` (OpenAI-compatible) |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | Ollama + `llama3.1:8b` | Point at Ollama, vLLM or OpenAI |
| `CUBE_URL` / `CUBE_API_SECRET` | `http://cube:4000` / `metricmind-dev-secret` | Semantic layer endpoint + JWT secret |
| `DATA_MAX_DATE` | `2026-06-30` | Relative ranges (“last quarter”) anchor to `min(today, DATA_MAX_DATE)` so the demo stays correct forever |
| `MAX_AGENT_STEPS` | `8` | Reasoning loop guard |

Running a local Llama 3 via Ollama:

```bash
LLM_PROVIDER=openai LLM_BASE_URL=http://host.docker.internal:11434/v1 \
LLM_API_KEY=ollama LLM_MODEL=llama3.1:8b \
docker compose -f infra/docker-compose.yml up --build
```

## Development (without Docker)

```bash
# API — needs a running Cube (services/semantic) or set CUBE_URL
cd apps/api
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # pip install on macOS/Linux
.venv/Scripts/python -m pytest -q                                           # 28 tests, no network needed
.venv/Scripts/uvicorn app.main:app --reload --port 8000

# Web
cd apps/web
npm install
API_PROXY_TARGET=http://localhost:8000 npm run dev
```

Regenerate seed data: `python seeds/generate_seeds.py` (deterministic; writes the four CSVs).

## Tests

* `apps/api` — `pytest -q`: time parsing, chart/KPI derivation, rogue-SQL synthesis + real
  DuckDB execution, mock driver narration, and a full end-to-end “European margins” run
  against a faked Cube backend asserting the whole SSE stream (5 governed steps, charts,
  KPIs, codegen, definition badges, no SQL anywhere).
* `apps/web` — `npx tsc --noEmit` and `npx next build` both pass.

## FAQ

**Where is the SQL?** Only inside Cube's semantic layer, generated from the YAML model —
never from the LLM. The agent's tools accept metric/dimension *names*, not expressions.

**How is the metric definition decided?** In `services/semantic/model/*.yml`, reviewed like
code. The API reads definitions from `/cubejs-api/v1/meta` and the UI shows them verbatim.

**Why does “last quarter” work months after the demo data ends?** Time phrases anchor to
`min(today, DATA_MAX_DATE)` (`apps/api/app/timeparse.py`), so with the seed ending
2026-06-30 the answer stays `2026-Q2`.

**Is the rogue SQL used for real answers?** Never. It is computed only to build the
side-by-side problem demo, is clearly labelled, and is never fed back to the agent.
