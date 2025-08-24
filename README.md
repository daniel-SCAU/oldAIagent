# oldAIagent
old ai agent version

## Services

- **Flask service** (`server.py`) runs on port `5000`.
- **FastAPI service** (`app.py`) runs on port `8000`.

Use `python main.py` to launch both servers simultaneously.

## Background Jobs and Summaries

The FastAPI service now runs a background scheduler powered by
`APScheduler`. Two periodic jobs are registered on startup:

1. **Message categorization** – new messages inserted via `/messages`
   are checked for a simple question/statement category and the result is
   stored in the `Chat.category` column.
2. **Conversation summarization** – pending tasks stored in the
   `summary_tasks` table are processed and populated with a short summary
   of the associated conversation thread.

Create summarization tasks with the new CRUD endpoints under `/tasks`
and the scheduler will fill in the `summary` field once processed.

### Configuration

APScheduler runs with in-memory settings and requires no additional
setup. PostgreSQL connection parameters can be provided via the
environment variables `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` and
`DB_NAME`. An API key is expected in the `x-api-key` header; override the
default using the `API_KEY` environment variable.
