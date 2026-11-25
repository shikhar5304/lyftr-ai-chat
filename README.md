# Lyftr AI Chat — LLM Chatbot with Key Failover and Response Caching

A full-stack AI chat application built for the Lyftr full-stack assessment. The application uses React on the frontend, FastAPI on the backend, LiteLLM for model access/caching, and SQLite for persistent per-session conversation history.

The backend maintains multi-turn context, tracks per-request token usage and latency, automatically falls back across an ordered API-key pool for retryable provider failures, and exposes the required `X-Simulate-Failure` hook for deterministic failover verification.

## 1. Live URLs

> Fill these in after deployment.

- **Frontend:** `https://<your-frontend-url>`
- **Backend:** `https://<your-backend-url>`
- **Backend health:** `https://<your-backend-url>/health`

Both URLs must be publicly reachable without login before submission.

## 2. Run locally: with Docker and without

### Prerequisites

- Docker Desktop + Docker Compose (recommended), or
- Python 3.12+ and Node.js 20+ for running without Docker
- At least **two API keys** for the provider/model configured in `LLM_MODEL`

Copy the environment template:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and provide at least two real keys:

```env
LLM_API_KEYS=first-real-key,second-real-key
LLM_MODEL=gemini/gemini-2.0-flash
DATABASE_URL=sqlite:////data/app.db
ALLOWED_ORIGINS=http://localhost:3000
ENABLE_FAILURE_SIMULATION=true
CACHE_ENABLED=true
LITELLM_CACHE_TYPE=local
VITE_API_URL=http://localhost:8000
```

Never commit `.env` or real API keys.

### Run with Docker

From the repository root:

```bash
make up
```

Equivalent command:

```bash
docker compose up --build
```

Services become available at:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Health endpoint: `http://localhost:8000/health`

SQLite is stored at `/data/app.db` inside the backend container and `/data` is backed by the named Docker volume `lyftr_sqlite_data`, so history survives normal container restarts.

Stop the stack with:

```bash
make down
```

### Run without Docker

For a non-Docker local run, change `DATABASE_URL` to a writable local path:

```env
DATABASE_URL=sqlite:///./data/app.db
```

#### Backend

From `backend/`:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend

In another terminal, from `frontend/`:

```bash
npm install
npm run dev
```

The Vite development server is configured for port `3000`.

### Tests and production build

Backend tests:

```bash
cd backend
pytest -v
```

Frontend production build:

```bash
cd frontend
npm install
npm run build
```

## 3. Design decisions: key fallback, caching, SQLite session storage

### Key pool and automatic fallback

`LLM_API_KEYS` is parsed as an ordered comma-separated pool. Keys are assigned safe logical IDs in order: `key_1`, `key_2`, and so on. Raw secrets are never returned in API responses.

For each live request, the backend attempts keys in order. Retryable provider failures such as HTTP 429/rate limits, quota exhaustion, transient timeouts, and 5xx provider errors cause the next key to be attempted. The successful response reports only its logical `key_id` and the number of failed keys in `fallback_attempts`. If no configured key succeeds, the API returns:

```json
{"detail":"all providers unavailable"}
```

with HTTP 503. Failed requests are not persisted to conversation history.

### Failure-simulation hook

When `ENABLE_FAILURE_SIMULATION=true`, `POST /chat` accepts the required `X-Simulate-Failure` header. Examples:

- `key_1=429`
- `key_1=500,key_2=503`
- `*=429`

Simulation applies only to the current request. Simulated requests bypass cache so the failover path is actually exercised and a successful fallback still returns a real model answer.

### LiteLLM response caching

The application configures LiteLLM's built-in `Cache` and calls `litellm.acompletion` with caching enabled for ordinary requests. The effective cache identity is based on the model and the complete message list sent to the model: system prompt + stored history + new user message.

This means the same first message in two new sessions can reuse a cached completion, while a different message or different conversation context does not incorrectly reuse it.

Responses are labeled:

- `LIVE_INFERENCE` for a newly generated completion
- `LLM_CACHE` when LiteLLM reports a cache hit

On a cache hit, `key_id` is `null`, `fallback_attempts` is `0`, and token usage comes from the cached LiteLLM response.

`LITELLM_CACHE_TYPE=local` uses LiteLLM's local in-memory cache. `disk` is also supported by the backend configuration when persistent local cache storage is desired.

### SQLite session storage

SQLite is the only application database. The schema is created automatically at startup. A `messages` table stores user/assistant turns and serialized assistant metadata; a small `sessions` table stores session-level system-prompt state. Messages are read oldest-first for context reconstruction.

The client sends only the new message. Before each LLM call, the backend loads the session's existing messages from SQLite and reconstructs:

1. effective system prompt,
2. previous user/assistant turns,
3. the new user message.

Successful user and assistant messages are committed atomically. Different `session_id` values remain isolated.

### Token and latency tracking

LiteLLM response usage is normalized into `input_tokens` and `output_tokens` for the individual request. These values are not running conversation totals. `latency_ms` is measured server-side using a monotonic high-resolution timer and returned as an integer.

## 4. Verification: how to see failover, cache hits and per-message token usage

The examples below assume the backend is running at `http://localhost:8000`.

### Health

```bash
curl http://localhost:8000/health
```

Expected shape:

```json
{
  "status": "ok",
  "keys_configured": 2,
  "cache_enabled": true
}
```

### Live inference

Use a fresh session ID and a message that has not already been cached:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"live-demo-1","message":"Explain why the sky looks blue in one sentence."}'
```

Inspect `metadata`. A newly generated answer reports `LIVE_INFERENCE`, the model, latency, per-request input/output tokens, the logical key ID, and fallback attempts.

### Cache hit

For the clearest cache demonstration, use the same first message in two different fresh sessions:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"cache-demo-a","message":"What is the capital of France?"}'
```

Then:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"cache-demo-b","message":"What is the capital of France?"}'
```

The first uncached call should report `LIVE_INFERENCE`. The second equivalent fresh-session call should return the identical reply with `LLM_CACHE`, `key_id: null`, and `fallback_attempts: 0`. The cache-hit latency should normally be lower than the live provider call.

### Key failover

With at least two configured keys and `ENABLE_FAILURE_SIMULATION=true`:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d '{"session_id":"failover-demo","message":"Reply with the word resilient."}'
```

Expected: HTTP 200 with a real model answer, `key_id: "key_2"`, and `fallback_attempts: 1`.

A 5xx simulation can be verified similarly:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=500" \
  -d '{"session_id":"failover-500-demo","message":"Reply with OK."}'
```

### All providers unavailable

```bash
curl -i -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: *=429" \
  -d '{"session_id":"all-fail-demo","message":"This must not be saved."}'
```

Expected HTTP 503:

```json
{"detail":"all providers unavailable"}
```

Confirm the failed request was not stored:

```bash
curl -i http://localhost:8000/sessions/all-fail-demo/messages
```

Expected HTTP 404 with:

```json
{"detail":"session not found"}
```

### Multi-turn state and history

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"context-demo","message":"My favorite programming language is Python."}'
```

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"context-demo","message":"What programming language did I say was my favorite?"}'
```

Retrieve persisted history:

```bash
curl http://localhost:8000/sessions/context-demo/messages
```

The history endpoint returns messages oldest-first and excludes the system prompt.

### Frontend telemetry

Each assistant message displays:

- resolution source (`LIVE_INFERENCE` / `LLM_CACHE`)
- model
- latency in milliseconds
- input tokens
- output tokens
- logical key slot
- fallback count

The required automated-test selectors are present: `chat-input`, `send-button`, `assistant-message`, `meta-source`, `meta-model`, `meta-latency`, `meta-input-tokens`, `meta-output-tokens`, and the optional `system-prompt-input`.

## 5. Setup Used: your editor and AI tools

- **Editor / agent environment:** Google Antigravity IDE
- **AI assistance:** Gemini through Antigravity and ChatGPT for requirement review, debugging guidance, and final implementation audit/documentation
- **Implementation approach:** AI-assisted implementation followed by automated tests, production frontend build checks, source review, and manual verification steps documented above

AI tools were used as development assistants. The candidate remains responsible for understanding, testing, configuring, deploying, and demonstrating the submitted application.

## 6. Bonus features (if any): what you added beyond the requirements and why

- **Session system-prompt panel:** allows a custom prompt to be set for the active session and includes the optional `system-prompt-input` test selector.
- **Gateway/health status in the UI:** makes backend availability visible during demonstrations.
- **Response telemetry chips:** required metadata is presented compactly, with additional key-slot and fallback-count information to make resilience behavior easy to demonstrate.
- **Copy response action:** improves usability without changing the required contract.
- **Character counter and duplicate-submit protection:** helps prevent invalid/accidental requests and improves UX around the 4000-character limit.
- **New-session control:** makes session isolation and cache demonstrations easy while still creating a fresh session automatically on each page load.
- **Expanded backend tests:** coverage includes validation, health, session isolation/history, cache behavior, simulated failover, real retryable-error fallback, and non-persistence of failed requests.

---

## Deployment notes

A `render.yaml` is included for deployment readiness. Before deploying:

1. Configure the backend service with `LLM_API_KEYS` containing at least two real provider keys.
2. Keep `DATABASE_URL=sqlite:////data/app.db` and attach persistent storage at `/data`.
3. Keep `ENABLE_FAILURE_SIMULATION=true` for assessment verification.
4. Set backend `ALLOWED_ORIGINS` to the final public frontend origin.
5. Set frontend `VITE_API_URL` to the final public backend base URL **before the frontend build**.
6. After deployment, update the **Live URLs** section at the top of this README.

## Final requirement audit

- [x] React frontend
- [x] FastAPI backend
- [x] SQLite-only application storage
- [x] SQLite schema created automatically
- [x] SQLite Docker volume mounted at `/data`
- [x] Multi-turn history reconstructed by the backend
- [x] Separate sessions by `session_id`
- [x] LiteLLM integration
- [x] Ordered multi-key pool with safe `key_1`, `key_2`, ... identifiers
- [x] Automatic fallback handling for rate-limit/quota/transient 5xx conditions
- [x] `X-Simulate-Failure` support with required status codes and wildcard
- [x] Failure simulation controlled by `ENABLE_FAILURE_SIMULATION`
- [x] Clean HTTP 503 when all providers are unavailable
- [x] Failed 422/503 chat requests are not added to history
- [x] LiteLLM built-in response cache configured
- [x] `LIVE_INFERENCE` / `LLM_CACHE` metadata
- [x] Cache-hit `key_id = null` and `fallback_attempts = 0`
- [x] Per-request input/output token metadata
- [x] Integer server-side latency metadata
- [x] Exact required `/health`, `/chat`, and `/sessions/{session_id}/messages` paths
- [x] JSON error responses with `detail`
- [x] Required frontend `data-testid` attributes
- [x] Fresh client session on each page load
- [x] Readable frontend error states
- [x] Configurable CORS
- [x] Multi-stage backend and frontend Dockerfiles
- [x] Root `docker-compose.yml`
- [x] Root Makefile with `up` and `down`
- [x] Complete `.env.example` with placeholder values only
- [x] Backend automated tests
- [x] Deployment configuration included
- [ ] Public frontend/backend URLs — complete after deployment
- [ ] Real-provider live/cache/failover smoke test — complete after adding the candidate's real API keys
- [ ] 2–3 minute demo video — record after deployment verification
