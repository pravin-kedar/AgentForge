# AgentForge

**An LLM travel-planning agent that shows how to do function calling safely:
the model decides *which* tool to call, and the backend owns everything else.**

AgentForge is a full-stack reference implementation of an agentic LLM application. A user chats in natural
language ("Plan a 4-day trip to Goa, I like beaches"), and the agent decides which of 11 backend tools to call,
chains several of them together, and answers from the tools' results instead of from its own memory.

The interesting part is not the travel domain. It's the boundary between what the LLM is trusted to do and what
it isn't:

| The LLM decides | The backend enforces |
|---|---|
| Whether a tool is needed | Who the user is (JWT, never the model) |
| Which tool, with which arguments | That the tool exists and the arguments are valid |
| How to phrase the final answer | That the user owns the data being touched |
| | That state changes happen exactly once (idempotency) |
| | That a failed tool is never reported as a success |

### What this project demonstrates

- **LLM agent loop** with multi-step tool chaining and a hard iteration cap
- **Function calling / tool orchestration** over an OpenAI-compatible API (Groq)
- **Central tool registry** with startup duplicate-name detection and auto-generated JSON schemas
- **Tool validation** (name → arguments → authorization), with controlled retry when the model picks a bad tool
- **Idempotency** for state-changing tools, keyed on `(conversation_id, tool_call_id)`
- **LLM provider abstraction** so Groq is swappable without touching the agent
- **JWT auth and per-user data isolation** enforced outside the model
- **Evaluation harness** for tool-selection accuracy, runnable mocked in CI or live against the real model
- **Structured observability**: every LLM call and tool execution logged as JSON with request, user and conversation ids

---

## Architecture

```text
                         React Frontend  (Vite + TS + Tailwind + TanStack Query)
                               |
                               | REST (JWT bearer)
                               v
                         FastAPI Backend
                               |
                     JWT → current_user           <- identity decided here, never by the LLM
                               |
                               v
                     Conversation Manager         (load / create, persist every message)
                               |
                               v
                         Agent Runtime            app/agent/agent.py
                               |
                    +----------+----------+
                    |                     |
                    v                     v
               Tool Registry          LLMProvider (abstract)
               11 tools + schemas         |
                    |                     v
                    |                GroqProvider  -> Groq API
                    |                     |
                    +----------+----------+
                               |
                   Tool call requested by the model
                               |
                               v
             Validate: name -> JSON args -> Pydantic schema
                               |
                               v
             Execute: idempotency check -> handler(args, db, current_user)
                               |                     \
                               |                      -> ownership check inside handler
                    +----------+----------+
                    |          |          |
                 Hotels   Activities   Weather   Trips      (PostgreSQL-backed mock data)
                    |          |          |
                    +----------+----------+
                               |
                   Tool result persisted + sent back to the LLM
                               |
                   ... loop until the model stops calling tools ...
                               |
                               v
                         Final response  ->  frontend (+ list of tools used)
```

### Agent flow

```text
User message
 ↓
JWT validated → current_user
 ↓
Load conversation history (system prompt + prior turns)
 ↓
LLM called with messages + tool schemas
 ↓
Tool requested? ── no ──→ final response, persisted, returned
 │
 yes
 ↓
Tool name exists?            ── no ──→ error fed back to LLM, retry (max 2), then graceful failure
Arguments valid JSON?        ── no ──→ same
Arguments match schema?      ── no ──→ same
 ↓
State-changing + already succeeded with this tool_call_id? ──→ replay cached result
 ↓
Execute handler with backend-supplied current_user
 ↓
Ownership check fails / DB error / exception ──→ recorded as FAILED, LLM told it failed
 ↓
Tool result persisted (messages + tool_executions) and appended to the prompt
 ↓
Back to the LLM (up to 8 round trips per turn)
```

---

## Example conversation

*Illustrative. At runtime the model chooses its own wording and tool sequence; the trace below shows the shape
of a multi-step turn.*

> **User:** Plan a 4-day trip to Goa for me. I like beaches and outdoor activities.
>
> *Agent calls:* `get_destination_info(destination="Goa")`
> *Agent calls:* `search_activities(destination="Goa")`
> *Agent calls:* `get_weather(destination="Goa")`
> *Agent calls:* `search_hotels(destination="Goa")`
>
> **AgentForge:** Goa's a great fit, and November to February is its best season. For outdoor activities
> there's scuba diving at Grande Island (₹3,500, 4 hrs) and an evening sunset cruise on the Mandovi (₹900).
> Two hotels have availability: Sunset Sands Resort (4★, from ₹6,500/night) and Palm Grove Inn (3★, from
> ₹3,200/night). What dates are you thinking of? I can save the trip once I have them.

Note what the agent *didn't* do: it didn't call `create_trip`, because no dates were given. The system prompt
tells it to ask rather than invent them, and `create_trip`'s schema requires them anyway.

In the UI, the assistant bubble shows `used: get_destination_info, search_activities, get_weather, search_hotels`
underneath. Tool names are shown, but never raw tool payloads or model reasoning.

---

## Tool registry

All tools live in [backend/app/tools/](backend/app/tools/) and are registered in
[registry.py](backend/app/tools/registry.py). Each has a Pydantic input model; the JSON schema sent to the LLM
is generated from it, so validation and the model-facing schema can't drift apart.

| Tool | Purpose | Mutates state |
|---|---|:---:|
| `search_hotels` | Hotels in a destination, filtered by guest capacity | |
| `get_hotel_details` | Rooms, prices, amenities for one hotel | |
| `check_hotel_availability` | Rooms + estimated total for a date range | |
| `get_destination_info` | Description and best season | |
| `search_activities` | Things to do, optional category filter | |
| `get_weather` | Forecast for a destination/date (deterministic simulation, see below) | |
| `create_trip` | Save a trip with optional hotel + activities and a cost estimate | ✓ |
| `get_my_trips` | List the current user's trips | |
| `get_trip` | One trip, ownership-checked | |
| `update_trip` | Change dates / budget / notes / status, ownership-checked | ✓ |
| `delete_trip` | Delete a trip, ownership-checked | ✓ |

**No tool accepts a `user_id` argument.** User-scoped tools receive `current_user` from the executor, and it
comes from the JWT. The model has no way to name whose data to read.

Travel data (6 Indian destinations, 12 hotels, 19 activities) is seeded into Postgres on startup from
[seed.py](backend/app/db/seed.py). `get_weather` is a deterministic generator (same destination + date → same
forecast), not a live feed, and says so in its output. The project intentionally avoids paid external APIs.

---

## Error handling

**Invalid tool calls.** If the model requests a tool that doesn't exist (e.g. `fetch_hotel_information`), sends
malformed JSON, or omits a required argument, nothing is executed. The validation error is returned to the
model as a tool result so it can correct itself. After `MAX_TOOL_RETRIES` (default 2) failed rounds, the user
gets a graceful "I wasn't able to complete that" reply and the failure is logged.

**Tool execution failures.** Authorization denials, validation errors, database errors, and unexpected
exceptions are all caught in [executor.py](backend/app/agent/executor.py), rolled back, persisted to
`tool_executions` as `failed`, and passed to the model as an explicit error. The system prompt forbids claiming
success unless the tool succeeded. Internal exception details go to the logs, never to the model or user.

**Idempotency.** `create_trip`, `update_trip` and `delete_trip` are flagged `mutates_state`. Before running one,
the executor checks for an existing *successful* execution with the same `(conversation_id, tool_call_id)`
(a DB unique constraint). If there is one, it replays the cached result instead of creating a duplicate trip.
A previously *failed* attempt doesn't block a retry. A concurrent duplicate insert is caught via the unique
constraint and resolved to the winner's result.

**LLM provider failures.** Timeouts, connection errors, non-2xx responses and malformed payloads become an
`LLMProviderError` → HTTP 502 with a generic message.

**Runaway loops.** An agent turn is capped at 8 LLM round trips.

---

## Security

- **Authentication:** bcrypt password hashing; HS256 JWTs with expiry; every `/api/v1/*` route requires
  `Authorization: Bearer <token>`.
- **Authorization lives outside the model.** `current_user` is resolved from the JWT before the agent runs. Trip
  tools check `trip.user_id == current_user.id` and raise `ToolAuthorizationError` otherwise. Conversations are
  always queried with `user_id` in the `WHERE` clause, so another user's conversation id returns 404.
- **Data isolation is tested.** There are integration tests where the model is scripted to request another
  user's trip id. The tool execution is recorded as `failed` with no result.
- **No internals exposed.** The system prompt is stored but filtered out of the conversation API. Tool payloads
  and reasoning are never returned to the frontend.
- **Secrets:** loaded via Pydantic Settings from environment / `.env` (gitignored). Missing required secrets fail
  at startup. `.dockerignore` keeps `.env` out of images.
- **Logs** redact password/token/key fields. JWTs and API keys never appear in them.

---

## Running it

**Prerequisites:** Docker Desktop, and a [Groq API key](https://console.groq.com/keys) for live chat.

```bash
cp backend/.env.example backend/.env
# edit backend/.env: set GROQ_API_KEY and a long random JWT_SECRET_KEY

docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000 |
| API docs (Swagger / ReDoc) | http://localhost:8000/docs · http://localhost:8000/redoc |
| PostgreSQL | localhost:5432 (exposed for local dev only) |

On startup the API container runs `alembic upgrade head`, then the idempotent seeder, then uvicorn.

Without a real `GROQ_API_KEY`, everything except chat works; chat returns a 502 from the provider.

### API

| Method | Path | |
|---|---|---|
| `POST` | `/auth/register` | Create account, returns JWT |
| `POST` | `/auth/login` | Returns JWT |
| `POST` | `/api/v1/chat` | `{conversation_id?, message}` → `{conversation_id, message, tool_activity}` |
| `GET` | `/api/v1/conversations` | Current user's conversations |
| `GET` | `/api/v1/conversations/{id}` | One conversation (user + assistant messages only) |
| `DELETE` | `/api/v1/conversations/{id}` | Delete a conversation |

---

## Testing

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -r requirements.txt

pytest                       # unit + integration + mocked evals (no API key, no Docker needed)
pytest --cov=app             # with coverage
ruff check app tests
mypy app
```

Current results: **57 passed, 1 skipped (the live eval), 95% line coverage**. Ruff and mypy are clean.

Tests never call Groq. They swap in a scripted `FakeLLMProvider` ([tests/fake_llm.py](backend/tests/fake_llm.py))
that returns a predetermined sequence of tool calls and replies, which makes multi-step agent behavior
deterministic. Tests run against a throwaway SQLite database, and the test config refuses to inherit any
ambient `DATABASE_URL`.

| Suite | Covers |
|---|---|
| `tests/unit` | Password hashing, JWT, tool registry, tool validation, every tool handler against seed data, executor idempotency + failure containment, agent loop (multi-step, invalid-tool recovery, retry exhaustion), Groq response parsing and error mapping, prompt, history reconstruction |
| `tests/integration` | HTTP → agent → tool → DB: auth flows, chat with tool calls, multi-turn continuation, cross-user trip access denied, failed tool not reported as success, conversation isolation, system prompt hidden |
| `tests/evals` | Tool-selection evaluation harness |

### Tool-selection evaluation

[tests/evals/data/tool_selection_cases.json](backend/tests/evals/data/tool_selection_cases.json) maps inputs to
the tool that should be selected (or `null` for "no tool"). The harness reports tool-selection accuracy and
invalid-tool rate.

- **Mocked (CI):** the scripted provider gets one case deliberately wrong. The test asserts **90%** accuracy,
  which proves the scoring discriminates. It says nothing about any real model.
- **Live:** measures the actual model.

  ```bash
  GROQ_API_KEY=<your-key> pytest tests/evals --live-llm -s
  # or, with the stack running and the key in backend/.env:
  docker compose exec api pytest tests/evals --live-llm -s
  ```

---

## Observability

Every log line is JSON and carries `request_id`, and inside an agent turn also `user_id` and `conversation_id`.

- `llm_call` / `llm_call_failed`: model, latency, finish reason, requested tools, prompt/completion tokens
- `tool_executed`: tool name, `tool_call_id`, status, latency
- `invalid_tool_call`, `tool_retries_exhausted`, `tool_idempotent_replay`, `agent_iteration_limit_hit`
- `request_completed`: method, path, status, duration

Each tool execution is also stored in the `tool_executions` table (arguments redacted, result or error,
latency), so agent behavior can be queried after the fact.

---

## Project structure

```text
backend/
  app/
    agent/      agent.py (loop) · executor.py (validate→execute→persist) · prompts.py · state.py
    llm/        base.py (LLMProvider) · groq.py · factory.py
    tools/      registry.py · schemas.py · validator.py · hotel/activity/weather/trip_tools.py
    api/        auth.py · chat.py · conversations.py        (thin routes, no business logic)
    services/   auth_service.py · conversation_service.py
    core/       config.py · security.py · logging.py · exceptions.py
    db/         database.py · models.py · seed.py
  alembic/      migrations
  tests/        unit/ · integration/ · evals/
frontend/
  src/          pages/ · components/ · hooks/ · services/api.ts · types/
docker-compose.yml
```

## Design decisions and known limitations

- **Chat is request/response, not streamed.** The tool-activity indicator is filled in when the response
  arrives, with a "thinking" placeholder while the request is in flight. Live per-step progress would need
  SSE or WebSockets.
- **Tests use SQLite; the app uses Postgres.** This keeps `pytest` free of Docker. The Alembic migration is
  checked separately against Postgres (`alembic check`), since the test suite builds its schema from the
  models rather than the migration.
- **Hotel availability is inventory-only.** There's no bookings table, so "available" means the room type
  exists with capacity. Trips are itineraries with cost estimates, not reservations.
- **If the LLM provider fails mid-turn**, the user's message is already saved without a reply. Retrying adds
  a new turn.

## Roadmap

The agent runtime depends only on the `LLMProvider` interface and the tool registry. Each phase below plugs in
at one of those seams rather than requiring a rewrite.

- **Phase 2: Dynamic tool retrieval.** Select a relevant subset of tools per request instead of sending all of
  them, via `get_llm_tool_schemas()`.
- **Phase 3: Vector search / RAG.** Destination guides and reviews retrieved as a tool, or as context injected
  in `state.py`.
- **Phase 4: Guardrails.** Input/output policy checks around `run_agent_loop`.
- **Phase 5: Rubric-based evaluation.** Score full responses against rubrics, beyond tool selection.
- **Phase 6: LLM-as-a-Judge.** Automated grading of groundedness (answer matches tool results).
- **Phase 7: Agent observability dashboard.** Visualize `tool_executions` and `llm_call` logs.

## License

[Apache 2.0](LICENSE)
