# API Examples

This document provides `curl` examples for all HTTP endpoints exposed by the project. Replace `$API_KEY` with your API key and adjust host/port if needed.

## Flask service (`server.py`)

### `POST /send-prompt`
Send a prompt to the server.
```bash
curl -X POST http://localhost:8001/send-prompt \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello from curl"}'
```

### `GET /get-prompt`
Retrieve the latest prompt and clear it.
```bash
curl http://localhost:8001/get-prompt \
  -H "X-API-KEY: $API_KEY"
```

### `POST /ack-prompt`
Acknowledge and clear the stored prompt.
```bash
curl -X POST http://localhost:8001/ack-prompt \
  -H "X-API-KEY: $API_KEY"
```

### `POST /process-response`
Send an AI response from the userscript.
```bash
curl -X POST http://localhost:8001/process-response \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"response":"This is a test response"}'
```

### `POST /test-response`
Request a test response from the myGPT API.
```bash
curl -X POST http://localhost:8001/test-response \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Need a quick summary"}'
```

### `GET /status`
Check server status and recent activity.
```bash
curl http://localhost:8001/status \
  -H "X-API-KEY: $API_KEY"
```

### `GET /history`
Fetch response history.
```bash
curl http://localhost:8001/history \
  -H "X-API-KEY: $API_KEY"
```

### `POST /clear`
Clear the stored prompt and response history.
```bash
curl -X POST http://localhost:8001/clear \
  -H "X-API-KEY: $API_KEY"
```

## FastAPI service (`app.py`)

### `GET /health`
Simple health check (no API key required).
```bash
curl http://localhost:8000/health
```

### `POST /messages`
Store a message.
```bash
curl -X POST http://localhost:8000/messages \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"sender":"alice","app":"sms","message":"Hello","conversation_id":"123"}'
```

### `POST /suggestions`
Generate reply suggestions for a conversation.
```bash
curl -X POST http://localhost:8000/suggestions \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"123"}'
```

### `GET /search`
Search messages by text.
```bash
curl http://localhost:8000/search?query=hello \
  -H "X-API-KEY: $API_KEY"
```

### `GET /conversations/{conversation_id}/messages`
List messages for a conversation.
```bash
curl http://localhost:8000/conversations/123/messages \
  -H "X-API-KEY: $API_KEY"
```

### `POST /tasks`
Create a summarization task.
```bash
curl -X POST http://localhost:8000/tasks \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"123"}'
```

### `GET /tasks`
List tasks.
```bash
curl http://localhost:8000/tasks \
  -H "X-API-KEY: $API_KEY"
```

### `GET /tasks/{task_id}`
Get a single task.
```bash
curl http://localhost:8000/tasks/1 \
  -H "X-API-KEY: $API_KEY"
```

### `DELETE /tasks/{task_id}`
Delete a task.
```bash
curl -X DELETE http://localhost:8000/tasks/1 \
  -H "X-API-KEY: $API_KEY"
```

### `POST /context`
Store additional context.
```bash
curl -X POST http://localhost:8000/context \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"123","context":"extra notes"}'
```

