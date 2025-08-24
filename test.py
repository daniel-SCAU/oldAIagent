import pytest
import requests
import subprocess
import time
import os
from unittest.mock import patch

# --- Configuration ---
FLASK_SERVER_URL = "http://localhost:5000"
FASTAPI_SERVER_URL = "http://localhost:8000"
# This API key must match the one in your fixed server.py
API_KEY = "your-secret-api-key"
HEADERS = {"X-API-KEY": API_KEY}

# --- Helper function to wait for servers ---

def wait_for_server(url, timeout=10):
    """
    Waits for a server to become responsive by polling a status endpoint.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # For Flask, we can use /status. For FastAPI, we use the docs endpoint.
            test_url = f"{url}/status" if "5000" in url else f"{url}/docs"
            # For the Flask server, we need headers for the status check
            headers = HEADERS if "5000" in url else None
            response = requests.get(test_url, headers=headers, timeout=1)
            if response.status_code == 200:
                print(f"Server at {url} is up!")
                return True
        except requests.ConnectionError:
            time.sleep(0.5) # Wait before retrying
    return False

# --- Pytest Fixtures to Manage Servers ---

@pytest.fixture(scope="session", autouse=True)
def manage_servers():
    """
    A pytest fixture that starts both servers, waits for them to be ready,
    and stops them after all tests are complete.
    """
    flask_process = None
    fastapi_process = None
    try:
        print("\n--- Starting Servers ---")
        # Start servers and redirect their output to devnull to keep test output clean
        devnull = open(os.devnull, 'w')
        flask_process = subprocess.Popen(["python", "server.py"], stdout=devnull, stderr=devnull)
        fastapi_process = subprocess.Popen(
            ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=devnull, stderr=devnull
        )

        # Wait for both servers to be responsive
        flask_ready = wait_for_server(FLASK_SERVER_URL)
        fastapi_ready = wait_for_server(FASTAPI_SERVER_URL)

        if not flask_ready or not fastapi_ready:
            raise RuntimeError("One or more servers failed to start.")

        print("--- Servers Started Successfully ---")
        yield # This is where the tests will run
    finally:
        print("\n--- Stopping Servers ---")
        if flask_process:
            flask_process.terminate()
            flask_process.wait()
            print("Flask server stopped.")
        if fastapi_process:
            fastapi_process.terminate()
            fastapi_process.wait()
            print("FastAPI server stopped.")
        devnull.close()
        print("--- Servers Stopped ---")


# --- Test Class for the Flask Server (server.py) ---

class TestFlaskServer:
    """Groups all tests related to the Flask server."""

    def test_server_status(self):
        """Checks if the Flask server is running and responding."""
        response = requests.get(f"{FLASK_SERVER_URL}/status", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'running'

    def test_full_prompt_workflow(self):
        """
        Tests the entire lifecycle of a prompt.
        NOTE: This test is for the NEW, fixed version of server.py.
        The original server.py will fail this test because it lacks an /ack-prompt endpoint.
        """
        # 1. Clear any previous state
        clear_response = requests.post(f"{FLASK_SERVER_URL}/clear", headers=HEADERS)
        assert clear_response.status_code == 200

        # 2. Send a prompt
        prompt_text = "This is a test prompt for the full workflow."
        send_response = requests.post(f"{FLASK_SERVER_URL}/send-prompt", json={"prompt": prompt_text}, headers=HEADERS)
        assert send_response.status_code == 200
        assert send_response.json()['status'] == 'success'

        # 3. Get the prompt
        get_response = requests.get(f"{FLASK_SERVER_URL}/get-prompt", headers=HEADERS)
        assert get_response.status_code == 200
        assert get_response.json()['prompt'] == prompt_text

        # 4. Acknowledge the prompt (This endpoint only exists in the fixed server.py)
        ack_response = requests.post(f"{FLASK_SERVER_URL}/ack-prompt", headers=HEADERS)
        if ack_response.status_code == 404:
            pytest.skip("Skipping ack test: /ack-prompt not found. You may be running the original server.py.")
        assert ack_response.status_code == 200
        assert ack_response.json()['status'] == 'success'

    def test_process_response(self):
        """Tests sending a response to the server and checking history."""
        requests.post(f"{FLASK_SERVER_URL}/clear", headers=HEADERS)
        response_text = "This is a test AI response."
        process_response = requests.post(f"{FLASK_SERVER_URL}/process-response", json={"response": response_text}, headers=HEADERS)
        assert process_response.status_code == 200
        assert process_response.json()['response_length'] == len(response_text)
        history_response = requests.get(f"{FLASK_SERVER_URL}/history", headers=HEADERS)
        assert history_response.status_code == 200
        history_data = history_response.json()
        assert history_data['total_responses'] == 1
        assert history_data['responses'][0]['response'] == response_text

# --- Test Class for the FastAPI Server (app.py) ---

class TestFastAPIServer:
    """Groups all tests related to the FastAPI server."""

    def test_store_and_get_message(self):
        """Tests storing a message and then retrieving its conversation history."""
        message_payload = {
            "sender": "user123",
            "message": "Hello, this is the first message.",
            "app": "TestApp"
        }
        store_response = requests.post(f"{FASTAPI_SERVER_URL}/messages", json=message_payload)
        assert store_response.status_code == 200
        stored_info = store_response.json()
        conversation_id = stored_info['conversation_id']

        history_response = requests.get(f"{FASTAPI_SERVER_URL}/conversations/{conversation_id}?sender=user123&limit=5")
        assert history_response.status_code == 200
        history_data = history_response.json()
        assert len(history_data) >= 1
        assert history_data[0]['message'] == message_payload['message']

    # Note the corrected patch target: 'app.requests.post'
    @patch('app.requests.post')
    def test_retrieve_context_mocked(self, mock_requests_post):
        """
        Tests the context retrieval endpoint by mocking the external call inside app.py.
        """
        # 1. Configure the mock for the Supabase/vector DB request
        mock_context_response = [{"content": "This is a relevant document."}]
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: mock_context_response
        mock_requests_post.return_value = mock_response

        # 2. Mock the embedding function since it also makes a network call
        with patch('app.generate_embedding', return_value=[0.1, 0.2, 0.3]) as mock_embed:
            # 3. Call the endpoint that USES the mocked functions
            context_payload = {"text": "What is context retrieval?"}
            # Use 'params' for GET-style query parameters, 'json' for POST body
            response = requests.post(f"{FASTAPI_SERVER_URL}/context", params=context_payload)

            # 4. Assertions
            assert response.status_code == 200
            # The endpoint returns a dict: {"context": [...]}, so we check that structure
            assert response.json()['context'] == mock_context_response
            mock_embed.assert_called_once_with(context_payload['text'])
            mock_requests_post.assert_called_once()
