# oldAIagent
old ai agent version

## Services

- **Flask service** (`server.py`) runs on port `5000`.
- **FastAPI service** (`app.py`) runs on port `8000`.

Use `python main.py` to launch both servers simultaneously.

## API Key

The FastAPI service requires a simple header-based API key. For development
and automated tests, use the canonical key `dev-api-key` by including it in the
`X-API-KEY` header of each request. The server can be configured to expect a
different key by setting the `API_KEY` environment variable before startup.
