# oldAIagent
old ai agent version

## Authentication

Both the Flask and FastAPI services expect an API key. For local development and
testing, use the canonical key `dev-api-key` and include it in requests as
`X-API-KEY: dev-api-key`. Alternatively, set the `API_KEY` environment variable
before starting the FastAPI server.
