# Satellite Telemetry Platform

A mission-control-style backend simulating a ground station that receives state-of-health data from a fleet of small Earth observation satellites. The system ingests spacecraft readings, evaluates configurable alert rules as readings arrive, and exposes a REST API for telemetry queries and alert management.

---

## Highlights

- Dockerized FastAPI backend with PostgreSQL, Redis, Alembic, and APScheduler
- Simulates 5 satellites streaming state-of-health telemetry
- Evaluates 28 configurable alert rules across EPS, Thermal, C&DH, Communications, and ADCS
- Supports alert acknowledgement, duplicate suppression, auto-resolution, and loss-of-signal detection
- Includes Redis caching, database indexes, migration support, and 27 pytest tests across routes/services/workers

---

## Why I Built This

I built this project to demonstrate backend engineering relevant to space software. It simulates satellite state-of-health telemetry, evaluates configurable alert rules across spacecraft subsystems, detects loss of signal, and supports operational alert workflows such as acknowledgement, resolution, and duplicate suppression.

---

## Project Status

This project is actively being developed as a backend/systems portfolio project.

Current functionality includes telemetry ingestion, PostgreSQL persistence, Redis caching, configurable alert rules, alert lifecycle management, loss-of-signal detection, migrations, tests, and local Docker Compose setup.

Not yet implemented: duration-based alert windows, queue-based ingestion, deployment, and frontend dashboard.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI, Python |
| Data validation | Pydantic v2 |
| ORM | SQLAlchemy 2.0 (sync sessions) |
| Database | PostgreSQL 16 |
| DB driver | psycopg3 (binary) |
| Cache | Redis 7 (30s TTL on telemetry queries) |
| Background jobs | APScheduler 3.10 |
| Migrations | Alembic |
| Containerization | Docker Compose |

---

## Architecture

```
  simulate.py        REST clients
  (SAT-1–SAT-5)           │
        │                 │
        └───────┬─────────┘
                │
        ┌───────▼─────────┐
        │   FastAPI app   │
        │    (uvicorn)    │
        └───────┬─────────┘
                │
        ┌───────┴───────────┐
        │                   │
┌───────▼──────────┐  ┌─────▼────────────────┐
│  Redis 7         │  │  PostgreSQL 16       │
│  (30s TTL)       │  │                      │
│                  │  │  telemetry_readings  │
│  GET /telemetry  │  │  alert_rules         │
│  /recent cache   │  │  alerts              │
└──────────────────┘  └─────▲────────────────┘
                            │
                        ┌───┴──────────────┐
                        │     Worker       │
                        │  (APScheduler)   │
                        │  LOS check / 60s │
                        └──────────────────┘
```

Four Docker Compose services: `server`, `worker`, `db`, `redis`. The `server` and `worker` containers share the same image; the worker overrides the startup command to run `python worker.py` instead of `uvicorn`.

---

## Database Schema

### `telemetry_readings`

Stores every raw sensor reading ingested via `POST /telemetry`.

| Column | Type | Notes |
|---|---|---|
| id | integer PK | auto-increment |
| source_id | varchar(100) | satellite identifier, e.g. `SAT-1` |
| metric | varchar(100) | e.g. `battery_soc_percent` |
| value | numeric(12,4) | sensor reading |
| unit | varchar(50) | e.g. `%`, `V`, `dBm` |
| timestamp | timestamptz | satellite-reported time (nullable) |
| received_at | timestamptz | server arrival time, default `now()` |

Index: `ix_timestamp_desc` — descending index on `timestamp` for fast recency queries.

### `alert_rules`

Configurable rules evaluated on every ingested reading.

| Column | Type | Notes |
|---|---|---|
| id | integer PK | auto-increment |
| name | varchar(100) UNIQUE | human-readable label |
| metric | varchar(100) | metric this rule targets |
| operator | varchar(3) | `<`, `>`, `<=`, `>=`, `==`, `!=` |
| threshold_value | numeric(12,4) | comparison value |
| duration_seconds | integer | sustained breach window (stored, not yet evaluated — see [design tradeoffs](#design-tradeoffs)) |
| severity | varchar(10) | `INFO`, `WARNING`, or `CRITICAL` |
| subsystem | varchar(100) | e.g. `Electrical Power System` |
| enabled | boolean | rules can be disabled without deletion |

Index: `ix_metric` — partial index on `metric WHERE enabled = TRUE`, used by the alert engine on every telemetry ingest.

### `alerts`

One row per alert event. Supports open/resolved lifecycle.

| Column | Type | Notes |
|---|---|---|
| id | integer PK | auto-increment |
| rule_id | integer FK | references `alert_rules.id` (RESTRICT) |
| reading_id | integer FK | references `telemetry_readings.id` (RESTRICT) |
| source_id | varchar(100) | satellite that triggered the alert |
| metric | varchar(100) | |
| observed_value | numeric(12,4) | value at time of trigger |
| message | varchar(500) | human-readable description |
| severity | varchar(10) | `INFO`, `WARNING`, or `CRITICAL` |
| acknowledged | boolean | operator has seen this alert |
| triggered_at | timestamptz | default `now()` |
| resolved_at | timestamptz | null while alert is open |

Index: `ix_triggered_at_desc` — descending index on `triggered_at`.

---

## Alert Engine

Alert evaluation runs synchronously inside the same database transaction as every `POST /telemetry` call.

**`check_for_alerts(reading, db)`** — fetches all enabled rules whose `metric` matches the incoming reading. For each matching rule it evaluates `reading.value {operator} rule.threshold_value` using Python's `operator` module. If the condition is breached, it checks whether an open alert (i.e. `resolved_at IS NULL`) already exists for that `rule_id` + `source_id` pair before creating a new one. This deduplication means a satellite can hold at threshold for hours without generating duplicate alerts.

**`resolve_alerts(reading, db)`** — called in the same transaction, after alert creation. For every open alert on the same `source_id` and `metric`, it re-evaluates the rule condition against the new value. If the condition is no longer breached, it stamps `resolved_at = now()`, closing the alert automatically.

The `duration_seconds` column is populated by the seed data (CPU rules carry 300s and 600s windows) but the engine currently fires on any single reading above threshold. Duration-based evaluation is tracked in the [backlog](#future-improvements).

---

## Background Worker — Loss of Signal (LOS)

Loss of signal cannot be detected from a single inbound reading. It requires noticing the *absence* of data. The `worker` container runs `worker.py`, which uses APScheduler to call `run_los_check(db)` on a configurable interval (default 60s, set via `LOS_CHECK_INTERVAL_SECONDS`).

For each distinct `source_id` in `telemetry_readings`, `run_los_check` computes:

```
age_min = (now - last_reading.received_at) / 60
```

It then evaluates this derived value against all enabled `last_contact_age_min` alert rules (e.g. `> 120` for WARNING, `> 240` for CRITICAL). LOS alert creation and resolution follow the same duplicate-suppression and auto-resolve patterns as the main alert engine. New LOS alerts are anchored to the most recent `reading_id` from that source.

The seed data includes two LOS rules (seeded alongside the other 26 rules via `python seed.py`).

---

## Tracked Metrics

| Subsystem | Metrics |
|---|---|
| Electrical Power System | `battery_voltage_v`, `battery_soc_percent`, `bus_voltage_v`, `solar_array_current_a`, `power_draw_w` |
| Thermal | `battery_temp_c` |
| Command and Data Handling | `obc_temp_c`, `obc_cpu_percent`, `storage_used_percent` |
| Communications | `rssi_dbm`, `link_margin_db` |
| ADCS | `attitude_error_deg` |
| Communications (derived) | `last_contact_age_min` — computed by the worker, not ingested directly |

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check — pings PostgreSQL, returns `503` if unavailable |
| `POST` | `/telemetry` | Ingest a reading; fires and resolves alerts in the same transaction |
| `GET` | `/telemetry/recent` | Paginated readings; filterable by `source_id`, `metric`, `from_time`, `to_time`; cached 30s in Redis |
| `GET` | `/sources` | List distinct source IDs seen in `telemetry_readings` |
| `GET` | `/alerts` | Paginated alerts sorted `CRITICAL→WARNING→INFO` then newest first; filterable by `source_id`, `severity`, `acknowledged` |
| `PATCH` | `/alerts/{id}` | Acknowledge or unacknowledge an alert |
| `POST` | `/alert-rules` | Create an alert rule (`409` on duplicate name) |
| `GET` | `/alert-rules` | List rules; optional `?enabled=true/false` filter |
| `PATCH` | `/alert-rules/{id}` | Partial update any mutable field |
| `DELETE` | `/alert-rules/{id}` | Delete a rule (`409` if alerts reference it) |

Query parameters for `GET /telemetry/recent`:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 100 | Max results per page (1–100) |
| `offset` | int | 0 | Pagination offset |
| `source_id` | string | — | Filter by satellite, e.g. `SAT-1` |
| `metric` | string | — | Filter by metric name |
| `from_time` | datetime | — | Readings at or after this timestamp |
| `to_time` | datetime | — | Readings at or before this timestamp |

Query parameters for `GET /alerts`:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 100 | Max results per page (1–100) |
| `offset` | int | 0 | Pagination offset |
| `source_id` | string | — | Filter by satellite |
| `severity` | string | — | `INFO`, `WARNING`, or `CRITICAL` |
| `acknowledged` | bool | — | Filter by acknowledgement status |

---

## API Examples

```bash
# Health check
curl http://localhost:8000/

# Ingest a reading
curl -X POST http://localhost:8000/telemetry \
  -H "Content-Type: application/json" \
  -d '{"source_id": "SAT-1", "metric": "battery_soc_percent", "value": 15.0, "unit": "%"}'

# Get recent readings for SAT-1, battery only
curl "http://localhost:8000/telemetry/recent?source_id=SAT-1&metric=battery_soc_percent&limit=10"

# Get readings within a time window
curl "http://localhost:8000/telemetry/recent?from_time=2026-06-24T00:00:00Z&to_time=2026-06-24T12:00:00Z"

# List all known source IDs
curl http://localhost:8000/sources

# Get unacknowledged CRITICAL alerts for SAT-3
curl "http://localhost:8000/alerts?source_id=SAT-3&severity=CRITICAL&acknowledged=false"

# Acknowledge alert 7
curl -X PATCH http://localhost:8000/alerts/7 \
  -H "Content-Type: application/json" \
  -d '{"acknowledged": true}'

# Create a custom alert rule
curl -X POST http://localhost:8000/alert-rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Attitude error warning",
    "metric": "attitude_error_deg",
    "operator": ">",
    "threshold_value": 5.0,
    "severity": "WARNING",
    "subsystem": "ADCS"
  }'

# List enabled rules only
curl "http://localhost:8000/alert-rules?enabled=true"

# Disable a rule without deleting it
curl -X PATCH http://localhost:8000/alert-rules/1 \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# Delete a rule (returns 409 if alerts reference it)
curl -X DELETE http://localhost:8000/alert-rules/1
```

---

## Sample JSON Responses

**`POST /telemetry`**

```json
{
  "id": 1042,
  "source_id": "SAT-1",
  "metric": "battery_soc_percent",
  "value": "15.0000",
  "unit": "%",
  "timestamp": null,
  "received_at": "2026-06-24T12:00:01.234567+00:00"
}
```

**`GET /telemetry/recent`**

```json
{
  "items": [
    {
      "id": 1042,
      "source_id": "SAT-1",
      "metric": "battery_soc_percent",
      "value": "15.0000",
      "unit": "%",
      "timestamp": null,
      "received_at": "2026-06-24T12:00:01.234567+00:00"
    }
  ],
  "total": 1042,
  "limit": 10,
  "offset": 0
}
```

**`GET /alerts`**

```json
{
  "items": [
    {
      "id": 3,
      "rule_id": 2,
      "reading_id": 1042,
      "source_id": "SAT-1",
      "metric": "battery_soc_percent",
      "observed_value": "15.0000",
      "message": "battery_soc_percent is 15.0, threshold: < 20.0000",
      "severity": "CRITICAL",
      "acknowledged": false,
      "triggered_at": "2026-06-24T12:00:01.234567+00:00",
      "resolved_at": null
    }
  ],
  "total": 3,
  "limit": 100,
  "offset": 0
}
```

**`GET /alert-rules` (one rule)**

```json
{
  "id": 2,
  "name": "Low battery critical",
  "metric": "battery_soc_percent",
  "operator": "<",
  "threshold_value": "20.0000",
  "duration_seconds": null,
  "severity": "CRITICAL",
  "subsystem": "Electrical Power System",
  "enabled": true
}
```

---

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) with Compose V2

### 1. Start the stack

```bash
docker compose up --build --watch
```

`--watch` enables live reload: file changes under `app/` sync into the container and restart the server without a full rebuild. Changes to `requirements.txt` trigger a full rebuild.

The API will be available at `http://localhost:8000`.

### 2. Apply database migrations

```bash
docker compose exec server alembic upgrade head
```

### 3. Seed alert rules

Loads 28 alert rules across EPS, Thermal, C&DH, Communications, and ADCS subsystems. The script is idempotent, so it is safe to run multiple times.

```bash
docker compose exec server python seed.py
```

### 4. Run the simulator (optional)

Streams simulated telemetry from five satellites (`SAT-1` through `SAT-5`) to the API at random 1–5 second intervals. 10% of readings are seeded into anomaly ranges to trigger alerts.

Requires the stack to be running. Run locally (not in Docker):

```bash
pip install requests
python simulate.py
```

---

## Demo Flow

To see the full system working locally:

1. Start the Docker Compose stack.
2. Apply database migrations.
3. Seed the alert rules.
4. Run the simulator.
5. Query `/telemetry/recent` to view incoming readings.
6. Query `/alerts` to view generated WARNING and CRITICAL alerts.
7. Acknowledge an alert with `PATCH /alerts/{id}`.
8. Stop the simulator. Note: the seeded LOS threshold is 120 minutes, so a loss-of-signal alert will take 2+ hours to fire against real data. To test LOS locally, seed a short-duration rule (last_contact_age_min > 5) and wait one worker cycle.

---

## Environment Variables

The `server` and `worker` containers read their configuration from environment variables. Docker Compose sets `DATABASE_URL` and `REDIS_URL` directly in `compose.yaml`. For local development outside Docker, create a `.env` file:

```
# .env.example
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/telemetry_db
REDIS_URL=redis://localhost:6379

# Optional — defaults shown
LOG_LEVEL=INFO
ALLOWED_ORIGINS=*
LOS_CHECK_INTERVAL_SECONDS=60
```

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | *(required)* | psycopg3 connection string |
| `REDIS_URL` | *(required)* | Redis connection string |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins, or `*` to allow all |
| `LOS_CHECK_INTERVAL_SECONDS` | `60` | How often the worker polls for loss-of-signal |

---

## Database Migrations

Schema changes are managed with [Alembic](https://alembic.sqlalchemy.org/). Migration files live in `migrations/versions/`.

```bash
# Apply all pending migrations
docker compose exec server alembic upgrade head

# Generate a new migration after editing app/models.py
docker compose exec server alembic revision --autogenerate -m "short description"

# Show current migration state
docker compose exec server alembic current

# Show migration history
docker compose exec server alembic history

# Roll back one migration
docker compose exec server alembic downgrade -1
```

---

## Testing

The current test suite includes 27 pytest tests across route integration tests, alert service unit tests, Redis cache behavior, and LOS worker behavior. Tests run against an in-memory SQLite database and `fakeredis`, so Docker is not required.

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -v
```

Test coverage:

| File | What it covers |
|---|---|
| `tests/test_services.py` | Alert engine unit tests — `check_for_alerts`, `resolve_alerts`, duplicate suppression |
| `tests/test_routes.py` | Route integration tests — telemetry ingest, filtering, alert CRUD, Redis cache hit/miss/fallback, constraint errors (409) |
| `tests/test_worker.py` | LOS worker tests — fires at threshold, suppresses duplicates, resolves on contact resume, handles multiple sources independently |

The test fixtures (`conftest.py`) use FastAPI's `TestClient` with dependency overrides to inject an isolated SQLite session and a `FakeRedis` instance per test.

---

## Design Tradeoffs

**Sync SQLAlchemy over async** — Synchronous sessions are simpler to reason about and sufficient for the throughput this system targets. Async would improve concurrency under heavy parallel load but adds significant complexity to session lifecycle management.

**Alert evaluation in-request** — `check_for_alerts` and `resolve_alerts` run inline in the same transaction as `POST /telemetry`. This guarantees every reading is evaluated before a 200 response goes back, and that alert state is consistent in the DB. The downside is added latency proportional to the number of matching rules. A write-ahead queue would decouple ingestion speed from alert speed, at the cost of eventual consistency.

**Redis as a soft dependency** — If Redis is unavailable, `GET /telemetry/recent` degrades gracefully to a direct DB query rather than returning an error. `RedisError` is caught and logged as a warning. This keeps the API available during cache outages at the cost of higher DB load.

**Partial index on `alert_rules.metric`** — The index is filtered to `WHERE enabled = TRUE`, which means the query that fires on every `POST /telemetry` only scans rows that are actually live. Disabled rules consume no index space and add no lookup cost.

**Window function for pagination** — Both `GET /telemetry/recent` and `GET /alerts` use `func.count().over()` to return the total count in a single query rather than issuing a separate `COUNT(*)`. This avoids a second round-trip at the cost of slightly more work per row.

**FK RESTRICT on rule deletion** — `alerts.rule_id` references `alert_rules.id` with `ondelete="RESTRICT"`. Deleting a rule with associated alerts returns a `409` rather than cascading. Historical alert records are preserved for audit and debugging.

**`duration_seconds` stored, not yet evaluated** — The seed data includes CPU rules with a sustained-breach requirement (e.g. `obc_cpu_percent > 85 for 5 min`). The column is in the schema and populated, but `check_for_alerts` currently fires on any single reading above threshold. This is a deliberate deferral — the schema is forward-compatible, and the engine change is contained to `services.py`.

---

## Future Improvements

**Duration-based evaluation** — Implement the rolling-window check for `duration_seconds` in `check_for_alerts`. Requires querying recent readings for the same source and metric within the window before firing.

**Correlation rules** — Multi-metric conditions such as `attitude_error_deg > 10 AND link_margin_db < 3` (possible antenna pointing issue). Requires schema migration to add a second metric/operator/threshold to `alert_rules` and updated evaluation logic.

**LOS simulation** — `simulate.py` sends readings on a 1–5 second loop, so no satellite ever goes silent. The LOS worker currently can't demonstrate against live simulated data. A per-satellite silence state with a configurable `LOS_THRESHOLD_MINUTES` would make the feature demonstrable end to end.

**Deployment** — The stack is Docker-ready and targets deployment to Fly.io or Railway.

**Frontend dashboard** — A separate-repo dashboard to visualize telemetry time series and surface active alerts in real time (not part of this repository).