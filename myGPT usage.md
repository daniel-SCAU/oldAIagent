# myGPT API - Python Version

A Python-based API server and client for automating myGPT interactions through a Tampermonkey userscript.

## Features

- **Python Flask Server**: Lightweight HTTP server for managing prompts and responses
- **Python Client Library**: Easy-to-use client for integrating myGPT into your Python projects
- **Response History**: Track and retrieve previous conversations
- **Status Monitoring**: Check server health and activity
- **Error Handling**: Robust error handling and logging
- **CORS Support**: Works with web applications

## Requirements

- Python 3.7+
- Flask
- Flask-CORS
- requests

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install the Tampermonkey userscript** (`userscript.js`) in your browser

3. **Make sure myGPT is open** in your browser

## Quick Start

### 1. Start the Server

```bash
python server.py
```

The server will start on `http://localhost:5000`

### 2. Use the Interactive Client

```bash
python prompt_sender.py
```

This gives you an interactive prompt interface similar to the Node.js version.

### 3. Use as a Python Library

```python
from prompt_sender import myGPTAPI

# Initialize the API client
api = myGPTAPI()

# Send a prompt and wait for response
result = api.ask("What is artificial intelligence?")

if result['response_received']:
    print(f"Response: {result['response']}")
else:
    print(f"Error: {result.get('error')}")
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/send-prompt` | Send a prompt from Python |
| `GET` | `/get-prompt` | Get prompt (userscript) |
| `POST` | `/process-response` | Receive AI response (userscript) |
| `GET` | `/status` | Server status |
| `GET` | `/history` | Response history |
| `POST` | `/clear` | Clear data |

## Python Client Methods

### `myGPTAPI` Class

#### Constructor
```python
api = myGPTAPI(server_url="http://localhost:5000")
```

#### Methods

- **`send_prompt(prompt: str)`**: Send a prompt to the server
- **`ask(prompt: str, wait_for_response: bool = True, timeout: int = 120)`**: Send prompt and optionally wait for response
- **`wait_for_response(timeout: int = 120, check_interval: int = 2)`**: Wait for a response
- **`get_status()`**: Get server status
- **`get_history()`**: Get response history
- **`clear_data()`**: Clear stored data

## Usage Examples

### Basic Usage

```python
from prompt_sender import myGPTAPI

api = myGPTAPI()

# Simple question
result = api.ask("What is the capital of France?")
print(result['response'])
```

### Async-Style Usage

```python
# Send prompt without waiting
result = api.ask("Explain quantum computing", wait_for_response=False)

# Do other work...
time.sleep(5)

# Check if response is ready
status = api.get_status()
if status['response_count'] > 0:
    history = api.get_history()
    latest = history['responses'][-1]
    print(latest['response'])
```

### Batch Processing

```python
prompts = [
    "What is machine learning?",
    "Explain neural networks",
    "What is deep learning?"
]

responses = []
for prompt in prompts:
    result = api.ask(prompt, wait_for_response=True, timeout=60)
    if result['response_received']:
        responses.append(result['response'])
```

### Custom Integration

```python
class MyApplication:
    def __init__(self):
        self.mygpt = myGPTAPI()
    
    def process_user_question(self, question: str) -> str:
        result = self.mygpt.ask(question)
        if result['response_received']:
            return result['response']
        else:
            return f"Error: {result.get('error')}"

# Use in your application
app = MyApplication()
answer = app.process_user_question("How do I implement a REST API?")
```

## Error Handling

The client includes comprehensive error handling:

```python
try:
    result = api.ask("What is Python?")
    if result['response_received']:
        print(result['response'])
    else:
        print(f"Error: {result.get('error')}")
except Exception as e:
    print(f"Connection error: {e}")
```

## Configuration

### Server Configuration

Edit `server.py` to change:
- Port number (default: 5000)
- Host binding (default: 0.0.0.0)
- Logging level
- Response history size

### Client Configuration

Edit `prompt_sender.py` to change:
- Default server URL
- Timeout values
- Retry logic
- Logging configuration

## Troubleshooting

### Common Issues

1. **"Connection refused"**: Make sure the server is running
2. **"No response received"**: Check that myGPT is open and the userscript is active
3. **"Response timeout"**: Increase timeout value or check myGPT status

### Debug Mode

Enable debug logging in the client:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Server Logs

The server provides detailed logging:
- Prompt reception
- Response processing
- Error details
- Activity timestamps

## Integration with Other Projects

The Python client is designed to be easily integrated:

1. **Copy `prompt_sender.py`** to your project
2. **Import the `myGPTAPI` class**
3. **Use the methods** as shown in examples
4. **Handle responses** in your application logic

## Performance Notes

- **Response time**: Depends on myGPT's response generation speed
- **Concurrent requests**: The server handles one prompt at a time
- **Memory usage**: Response history is kept in memory (configurable)
- **Network**: Minimal overhead, just HTTP requests

## Security Considerations

- **Local server only**: Server runs on localhost by default
- **No authentication**: Intended for local development use
- **CORS enabled**: Allows web applications to connect
- **Input validation**: Basic validation on server endpoints

## License

This project is provided as-is for educational and development purposes.
