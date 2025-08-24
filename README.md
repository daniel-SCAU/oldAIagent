# oldAIagent
old ai agent version

## Services

- **Flask service** (`server.py`) runs on port `5000`.
- **FastAPI service** (`app.py`) runs on port `8000`.

Use `python main.py` to launch both servers simultaneously.

## Message Ingestors

Modules under `ingestors/` retrieve messages from external platforms and push
normalized content to the FastAPI `POST /messages` endpoint.

| Module | Purpose | Required Credentials |
|-------|---------|----------------------|
| `ingestors/messenger.py` | Polls Facebook Messenger conversations via the Graph API. | `MESSENGER_PAGE_ID`, `MESSENGER_PAGE_TOKEN` |
| `ingestors/whatsapp.py` | Handles WhatsApp Cloud API messages via webhooks or optional polling. | `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TOKEN` |

Both modules require access to the FastAPI service:

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
