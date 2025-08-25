# oldAIagent
old ai agent version

#<<<<<<< codex/decide-and-update-api-key
## Authentication

Both the Flask and FastAPI services expect an API key. For local development and
testing, use the canonical key `dev-api-key` and include it in requests as
`X-API-KEY: dev-api-key`. Alternatively, set the `API_KEY` environment variable
before starting the FastAPI server.
#=======
## Services

- **Flask service** (`server.py`) runs on port `5000`.
- **FastAPI service** (`app.py`) runs on port `8000`.

Use `python main.py` to launch both servers simultaneously.

#<<<<<<< codex/create-ingestor-modules-for-messaging-apis
## Message Ingestors

Modules under `ingestors/` retrieve messages from external platforms and push
normalized content to the FastAPI `POST /messages` endpoint.

| Module | Purpose | Required Credentials |
|-------|---------|----------------------|
| `ingestors/messenger.py` | Polls Facebook Messenger conversations via the Graph API. | `MESSENGER_PAGE_ID`, `MESSENGER_PAGE_TOKEN` |
| `ingestors/whatsapp.py` | Handles WhatsApp Cloud API messages via webhooks or optional polling. | `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TOKEN` |
| `ingestors/outlook.py` | Reads emails via Microsoft Graph API. | `OUTLOOK_TOKEN`, `OUTLOOK_USER_ID` |
| `ingestors/sms.py` | Fetches SMS messages from Twilio. | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` |
| `ingestors/aula.py` | Example integration with Aula platform. | `AULA_API_URL`, `AULA_TOKEN` |

All modules require access to the FastAPI service:

- `APP_API_URL` – base URL of the API (default `http://127.0.0.1:8000`).
- `API_KEY` – API key expected by the FastAPI service.

## Scheduling & Webhooks

### Messenger
Run periodically to pull new messages, e.g. using cron:

```bash
APP_API_URL=http://127.0.0.1:8000 API_KEY=dev-api-key \
MESSENGER_PAGE_ID=your_page_id MESSENGER_PAGE_TOKEN=token \
python -m ingestors.messenger
```

### WhatsApp
The WhatsApp Cloud API delivers messages via webhooks. Expose an HTTP endpoint
in your preferred framework and pass the received JSON payload to
`ingestors.whatsapp.handle_webhook(payload)`.

For simple polling or testing, schedule:

```bash
APP_API_URL=http://127.0.0.1:8000 API_KEY=dev-api-key \
WHATSAPP_PHONE_NUMBER_ID=phone_id WHATSAPP_TOKEN=token \
python -m ingestors.whatsapp
```
#=======
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

## Follow-up Task Detection

Incoming messages sent to `POST /messages` are now scanned for follow-up
phrases such as "please", "can you" or "todo". Detected tasks are stored
in a dedicated `followup_tasks` table with a default `pending` status so
they can be reviewed or acted on later.

## Reply Suggestions

Generate proposed replies for any conversation with the new
`POST /suggestions` endpoint. The service gathers the conversation
history, forwards it to the configured myGPT service and returns a list
of reply suggestions.

Example:

```bash
curl -X POST http://localhost:8000/suggestions \
  -H "X-API-Key: $API_KEY" \
  -d '{"conversation_id": "123"}'
```

Optional environment variables `MYGPT_API_URL` and `MYGPT_API_KEY` may be
set to point at a running myGPT instance.

### Configuration

APScheduler runs with in-memory settings and requires no additional
setup. PostgreSQL connection parameters can be provided via the
environment variables `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` and
`DB_NAME`. An API key is expected in the `x-api-key` header; override the
default using the `API_KEY` environment variable.

## Database Migrations

Alembic manages schema changes. Apply pending migrations with:

```bash
alembic upgrade head
```

To create a new migration after modifying the schema:

```bash
alembic revision -m "description of change"
```

The FastAPI service automatically runs `alembic upgrade head` on startup
to ensure the database is up to date.

## API Key

The FastAPI service requires a simple header-based API key. For development
and automated tests, use the canonical key `dev-api-key` by including it in the
`X-API-KEY` header of each request. The server can be configured to expect a
different key by setting the `API_KEY` environment variable before startup.
