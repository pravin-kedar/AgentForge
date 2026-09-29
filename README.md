# AgentForge ✈️

**An AI travel-planning assistant built on LLM function calling.**
You chat in plain English, like *"Plan a 4-day trip to Goa, I like beaches"*. The AI decides which backend
functions to call (hotels, activities, weather, trips), the backend runs them, and the AI answers using
real data instead of guessing.

Stack: **FastAPI · PostgreSQL · Groq LLM · React + TypeScript · Docker**

---

## How it works (60-second version)

```text
 You ──► React UI ──► FastAPI ──► Agent loop ──► LLM (Groq)
                                     ▲    │
                                     │    ▼  "call get_weather(destination='Goa')"
                                     │  Backend validates + runs the function
                                     │    │
                                     └────┘  result goes back to the LLM
                                             ... repeat until the LLM has what it needs
                                     ▼
                              Final answer ──► UI
```

**What is function calling?** With every request, we send the LLM a list of available functions (we
call them *tools*), each with a name, a description, and a JSON schema for its arguments. The LLM doesn't
run any code. It replies either with text or with *"please call `search_hotels` with
`{"destination": "Goa"}`"*. Our backend runs that function and sends the result back to the LLM, which can
then call another tool or write the final answer.

**Who does what:**

| The LLM (Groq) decides | The backend (our code) enforces |
|---|---|
| Whether a tool is needed at all | **Who the user is**: identity comes from the JWT login token, never from the LLM |
| Which tool, with what arguments | That the tool exists and the arguments are valid (Pydantic schemas) |
| How to word the final reply | That users can only see or change **their own** trips |
| | That a failed tool is never reported as a success |
| | That saving a trip twice by accident doesn't create duplicates |

**A typical turn**, for *"What's the weather in Goa and what can I do there?"*:
1. The LLM receives the message and 11 tool definitions.
2. The LLM asks to call `get_weather("Goa")` → the backend runs it → the result goes back.
3. The LLM asks to call `search_activities("Goa")` → the backend runs it → the result goes back.
4. The LLM writes the final answer from those two results. The UI shows the reply plus chips
   like 🌤️ *Checked weather* · 🏄 *Found activities*.

If the LLM asks for a tool that doesn't exist or sends bad arguments, nothing runs. The error is sent back so
it can correct itself (up to 2 retries). After that the user gets a polite failure message. The core of all
this is in [backend/app/agent/agent.py](backend/app/agent/agent.py).

---

## Quick start (Docker, recommended)

You need **Docker Desktop** and a free **Groq API key**. You don't need Python, Node, or Postgres installed.

### 1. Get a Groq API key
Sign up at [console.groq.com](https://console.groq.com) → **API Keys** → **Create API Key**. Copy it (it
starts with `gsk_`).

### 2. Create your `.env` file
```bash
cp backend/.env.example backend/.env        # Windows PowerShell: copy backend\.env.example backend\.env
```
Open `backend/.env` and set these two lines:
```env
GROQ_API_KEY=gsk_your_real_key_here
JWT_SECRET_KEY=any-long-random-string-at-least-32-characters
```
Leave everything else as it is. `backend/.env` is gitignored, so your key is never committed.

### 3. Start everything
```bash
docker compose up --build
```
The first run takes a few minutes to build. After that, three containers are running:

| Service | URL / port | What it is |
|---|---|---|
| **frontend** | http://localhost:5173 | React chat UI (open this in your browser) |
| **api** | http://localhost:8000 | FastAPI backend. Interactive API docs at http://localhost:8000/docs |
| **db** | localhost:5432 | PostgreSQL 16 |

On every start, the API container automatically:
1. creates or updates the database tables (`alembic upgrade head`),
2. loads demo travel data (6 destinations, 12 hotels, 19 activities; skipped if already loaded),
3. starts the server.

### 4. Use it
Open http://localhost:5173 → **Register** → **Chat**, and try:
- *"What's the weather in Goa and what outdoor activities are there?"*
- *"Find hotels in Jaipur for 2 guests"*
- *"Plan a 4-day trip to Kerala from Dec 10 to Dec 14 and save it"*
- *"Show my saved trips"*

### 5. Stop it
```bash
docker compose down          # stop containers, keep database data
docker compose down -v       # stop and DELETE all database data
```

> **Changed `backend/.env`?** Containers only read it when they're created. Apply changes with:
> `docker compose up -d --force-recreate api`

---

## Configuration (`backend/.env`)

| Variable | Default | Notes |
|---|---|---|
| `GROQ_API_KEY` | none | **Required.** Your Groq key |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Must be a model your key can access and that supports tool calling |
| `JWT_SECRET_KEY` | none | **Required.** Signs login tokens; use a long random string |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | How long a login lasts |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@db:5432/agentforge` | Host `db` only works *inside* Docker (see below) |
| `MAX_TOOL_RETRIES` | `2` | How many times the LLM may retry after an invalid tool call |
| `LOG_LEVEL` | `INFO` | |

The app refuses to start if a required variable is missing.

---

## Database

- **PostgreSQL 16** in the `db` container. User `postgres`, password `postgres`, database `agentforge`.
- Data is kept in the Docker volume `agentforge_pgdata`, so it survives restarts. `docker compose down -v` wipes it.
- The schema is managed by **Alembic** ([backend/alembic/versions/](backend/alembic/versions/)).
- Tables: `users`, `conversations`, `messages`, `tool_executions` (a log of every tool call), and demo data
  in `destinations`, `hotels`, `hotel_rooms`, `activities`, `trips`.

To open a SQL shell:
```bash
docker compose exec db psql -U postgres -d agentforge
# e.g.  select tool_name, status, latency_ms from tool_executions order by id desc limit 10;
```
Or connect any SQL client to `localhost:5432` with the credentials above.

> Port 5432 is published for local development only. Don't expose it on a real server.

---

## Running without Docker (for development)

Use this if you want hot reload while editing code. You'll still need Postgres, and the easiest source is
the Docker `db` service.

### Backend (Python 3.12)
```bash
docker compose up -d db                       # Postgres only

cd backend
python -m venv .venv
source .venv/bin/activate                     # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# .env points at host "db" (Docker-internal); outside Docker, use localhost instead:
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agentforge
#   PowerShell: $env:DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/agentforge"

alembic upgrade head                          # create tables
python -m app.db.seed                         # load demo data
uvicorn app.main:app --reload --port 8000     # http://localhost:8000/docs
```
Stop the Docker `api` container first (`docker compose stop api`), or port 8000 will already be in use.

### Frontend (Node 20+)
```bash
cd frontend
npm install
npm run dev                                   # http://localhost:5173
```
The UI calls `http://localhost:8000` by default (override with `VITE_API_BASE_URL` in `frontend/.env`).
The API only accepts browser requests from `http://localhost:5173`, so keep that port.

---

## The tools the LLM can call

| Tool | What it does | Changes data? |
|---|---|:---:|
| `search_hotels` | Hotels in a destination, filtered by number of guests | |
| `get_hotel_details` | Rooms, prices, amenities for one hotel | |
| `check_hotel_availability` | Rooms and total price for a date range | |
| `get_destination_info` | Description and best season to visit | |
| `search_activities` | Things to do, optionally filtered by category | |
| `get_weather` | Forecast for a place and date (simulated demo data) | |
| `create_trip` | Save a trip, with hotel, activities and a cost estimate | ✓ |
| `get_my_trips` / `get_trip` | Read *your* saved trips | |
| `update_trip` / `delete_trip` | Change or remove *your* trip | ✓ |

Each tool is a Python function plus a Pydantic input model in [backend/app/tools/](backend/app/tools/). The
JSON schema sent to the LLM is generated from that model, so the LLM's view and our validation can't drift
apart. **No tool takes a `user_id` argument.** The backend always supplies the logged-in user, so the LLM
can't ask for someone else's data.

---

## Safety and reliability

- **Login:** passwords are hashed with bcrypt. Every chat and conversation endpoint requires a JWT.
- **Data isolation:** trip tools check ownership. Another user's trip or conversation is refused or returns 404.
- **Honest failures:** DB errors and exceptions are caught, recorded as `failed`, and reported to the LLM as
  failures. The prompt forbids claiming success unless the tool actually succeeded.
- **No duplicates:** the create, update, and delete tools are idempotent per `(conversation_id, tool_call_id)`.
- **Loop limit:** at most 8 LLM round trips per message.
- **Nothing internal leaks:** the system prompt, raw tool payloads, and secrets are never sent to the UI or
  written to logs.
- **Swappable LLM:** the agent talks to an `LLMProvider` interface ([backend/app/llm/](backend/app/llm/)), so
  adding OpenAI or Azure means writing one class.

---

## Tests

```bash
# Inside Docker (no local setup needed):
docker compose exec api pytest

# Or locally, from backend/ with the venv active:
pytest                    # 59 tests, uses a throwaway SQLite DB and a fake LLM
pytest --cov=app          # coverage (~95%)
ruff check app tests && mypy app
```
Tests never call Groq. A scripted fake LLM makes multi-step tool calling deterministic.

**Measure real tool-selection accuracy** (uses your Groq key and makes live API calls):
```bash
docker compose exec api pytest tests/evals --live-llm -s
```
This sends the 20 questions in
[tool_selection_cases.json](backend/tests/evals/data/tool_selection_cases.json) to the real model. Each
question lists the function it should trigger (or none). The run prints a pass/fail table plus
**tool-selection accuracy**, **argument accuracy** and **invalid-tool rate**. It pauses between requests
and retries rate limits, so it takes about a minute on a free Groq key.

Latest run (`openai/gpt-oss-120b`): **20/20 correct tools, 100% argument accuracy, 0% invalid tools.**
To add a scenario, append a question and its expected tool to the JSON file.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Chat shows *"LLM provider returned an error: 401"* | Wrong or missing `GROQ_API_KEY`. Fix `backend/.env`, then `docker compose up -d --force-recreate api` |
| Chat shows *"...error: 404"* | Your key can't use `GROQ_MODEL`. Pick a tool-calling model from your Groq console |
| `port is already allocated` | Something else is using 5173, 8000 or 5432. Stop it, or change the left-hand port in `docker-compose.yml`. If you move 5173 or 8000, also update `allow_origins` in `backend/app/main.py` or `VITE_API_BASE_URL` |
| UI loads but requests fail | Check the API is up: `docker compose logs api` |
| Want a clean database | `docker compose down -v && docker compose up` |

---

## Project structure

```text
backend/app/
  agent/     agent.py (the loop) · executor.py (validate → run → record) · prompts.py (system prompt)
  llm/       base.py (LLMProvider interface) · groq.py · factory.py
  tools/     registry.py · schemas.py · validator.py · hotel/activity/weather/trip_tools.py
  api/       auth.py · chat.py · conversations.py
  core/      config.py · security.py · logging.py · exceptions.py
  db/        models.py · database.py · seed.py
backend/tests/    unit/ · integration/ · evals/
frontend/src/     pages/ · components/ · hooks/ · services/api.ts
docker-compose.yml
```

## Roadmap
Dynamic tool retrieval → RAG / vector search → guardrails → rubric evals → LLM-as-a-judge →
observability dashboard. Each plugs into the existing tool registry or `LLMProvider` without rewriting the
agent loop.

## License
[Apache 2.0](LICENSE)
