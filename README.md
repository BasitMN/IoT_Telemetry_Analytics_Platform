# IoT Telemetry & Analytics Platform


It's a small containerized microservice that takes in telemetry from IoT sensors
(temperature, humidity, energy usage etc), saves it in a database and gives it back through
a REST API. Everything runs with Docker Compose and the API is contract-tested with
Schemathesis against an OpenAPI 3.0 spec.

Tested on Docker Desktop on Windows, works on my machine.

## Stack

- Python + Flask (the API)
- PostgreSQL 15 (storage, with a Docker volume so data is not lost)
- Docker / Docker Compose
- Schemathesis for the contract tests
- OpenAPI 3.0 as the contract

## How it works

Three services in `docker-compose.yml`:

- **db** – PostgreSQL. Has a healthcheck (`pg_isready`) and a named volume `postgres_data`.
- **api** – the Flask app. Starts only after the db is healthy and has its own healthcheck on `/health`.
- **tests** – runs Schemathesis against the api.

For the networks I used two of them. `api` is on `frontend` and `backend`, but the database
is only on `backend` which is `internal: true`. So the db can not be reached from outside,
only the api can talk to it. That is the network isolation.

## Run it

From the `starter-template` folder:

```bash
docker-compose up --build -d
docker-compose ps
```

You should see db and api healthy.

Stop it:

```bash
docker-compose down        # keeps the data
docker-compose down -v     # deletes the db volume too
```

## Endpoints

- `GET /health` → `{"status": "healthy"}`
- `GET /openapi.json` → the OpenAPI contract as JSON (Schemathesis reads this)
- `POST /api/v1/telemetry` → create a record
- `GET /api/v1/telemetry` → get all records

`sensor_id`, `metric_type` and `value` are required, `timestamp` is optional (if you skip it
the current time is used).

Example:

```bash
curl -X POST http://127.0.0.1:5000/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d "{\"sensor_id\":\"temp-sensor-01\",\"metric_type\":\"temperature\",\"value\":22.5}"
```

Valid data gives `201`, bad data always gives a `400` (never a `500`). I do all the
validation before it hits the database so weird input can not crash it.

## Tests

```bash
docker-compose run tests
```

I run it with `--phases examples,coverage` (positive + negative tests). The newer
Schemathesis has a bug that crashes its Fuzzing phase, so I disable that phase, it is a
problem in the tool and not in my API. Output:

```
Schemathesis v4.25.1
━━━━━━━━━━━━━━━━━━━━
 ✅  Loaded specification from http://api:5000/openapi.json (in 0.47s)
     Base URL:         http://api:5000/
     Specification:    Open API 3.0.3
     Operations:       4 selected / 4 total
 ✅  API capabilities:
     Supports NULL byte in headers:                            ✓
     Accepts backslash and control characters in URL paths:    ✓
 ✅  Examples (in 0.23s)

     ✅ 1 passed  ⏭  3 skipped
 ✅  Coverage (in 1.82s)

     ✅ 4 passed
========================================= SUMMARY =========================================
API Operations:
  Selected: 4/4
  Tested: 4
Test Phases:
  ✅ Examples
  ✅ Coverage
  ⏭  Fuzzing (disabled)
  ⏭  Stateful (disabled)
Schema Coverage report: ./schema-coverage.html
Test cases:
  55 generated, 55 passed
Seed: 311004421840112479562616578664663284598
================================= No issues found in 2.10s ================================
```

So it passes with no contract violations.

## Persistence

Quick check that the volume works: POST a record, then `docker-compose down` (without `-v`),
then `docker-compose up -d` again and open `/api/v1/telemetry`. The record is still there.

## VG requirements

Where each VG point is in the code:

- Multi-stage build – `api/Dockerfile`, separate `builder` and `runtime` stages so gcc etc is not in the final image.
- Non-root – runs as `USER 1000`.
- Small/clean image – `--no-cache-dir` and apt lists removed.
- Healthchecks – db with `pg_isready`, api with its own check, and `depends_on: condition: service_healthy`.
- Network isolation – `frontend` + `backend` (`internal: true`), db not exposed.
- Persistence – `postgres_data` volume.
- Table created automatically – `CREATE TABLE IF NOT EXISTS` on startup.
- Contract testing without violations – the tests service passes (output above).

## Notes / what was tricky

A few things that took me time, writing them down in case someone reads the code:

- The `GET /openapi.json` returned **404** at first and the tests could not even start. It
  took me a while to understand it was a Docker build-context thing – `openapi.yaml` lives
  one level above the `api/` folder so it never got copied into the image. Fixed it by
  building from the project root (`context: .`) and adding `COPY openapi.yaml /openapi.yaml`
  in the Dockerfile.
- On Windows `http://localhost:5000` gave me `connection was reset` but `http://127.0.0.1:5000`
  worked fine. Turned out localhost goes to IPv6 first and the port is bound on IPv4. The
  tests don't care because they use the internal network (`http://api:5000`).
- Got `port 5000 already allocated` once because an old container was still running. `down`
  first, then `up` again fixed it.
- Schemathesis was also sending `{"timestamp": null}` and expecting a 400. My first version
  let it through with 201, so I had to check `"timestamp" in data` instead of `is not None`.

## Structure

```
starter-template/
├── openapi.yaml
├── docker-compose.yml
├── README.md
└── api/
    ├── app.py
    ├── requirements.txt
    └── Dockerfile
```
