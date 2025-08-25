# Client CLI

A minimal command-line interface for interacting with the myGPT API.

## Setup

Ensure the API server from this repository is running and accessible. Set the
API base URL and key as environment variables if needed:

```bash
export API_BASE_URL="http://localhost:8000"
export API_KEY="your-secret-key"
```

## Usage

Run the CLI with Python. Examples:

```bash
python client/cli.py conversations            # List conversation IDs
python client/cli.py summary 123              # Show summary for conversation 123
python client/cli.py tasks                    # List all summary tasks
python client/cli.py suggest 123 --limit 2    # Suggest replies for conversation 123
```

Each command accepts optional `--base-url` and `--api-key` arguments to override
the environment variables.
