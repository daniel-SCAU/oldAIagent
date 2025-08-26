#!/usr/bin/env python3
"""
myGPT API Server - Python Version
A Flask server that acts as a communication hub between Python scripts and the myGPT userscript.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime
import os
import requests
from secrets import compare_digest

from threading import Lock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app = Flask(__name__)
if ALLOWED_ORIGINS == ["*"]:
    CORS(app)
else:
    CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

API_KEY = os.getenv("API_KEY", "dev-api-key")


@app.before_request
def check_api_key():
    """Validate the X-API-KEY header before handling requests."""
    if API_KEY:
        provided = request.headers.get("X-API-KEY", "")
        if not compare_digest(provided, API_KEY):
            return jsonify({"error": "Unauthorized"}), 401

# In-memory datastore protected by a lock


class InMemoryStore:
    """Thread-safe storage for prompts and responses."""

    def __init__(self):
        self._lock = Lock()
        self._prompt = None
        self._responses = []

    # Prompt operations -------------------------------------------------
    def set_prompt(self, prompt: str) -> None:
        with self._lock:
            self._prompt = prompt

    def pop_prompt(self):
        """Return and clear the stored prompt."""
        with self._lock:
            prompt = self._prompt
            self._prompt = None
            return prompt

    def clear_prompt(self) -> None:
        with self._lock:
            self._prompt = None

    def has_prompt(self) -> bool:
        with self._lock:
            return self._prompt is not None

    # Response history operations --------------------------------------
    def add_response(self, timestamp: str, response: str) -> None:
        with self._lock:
            self._responses.append({'timestamp': timestamp, 'response': response})
            if len(self._responses) > 10:
                self._responses.pop(0)

    def get_responses(self):
        with self._lock:
            return list(self._responses)

    def response_count(self) -> int:
        with self._lock:
            return len(self._responses)

    def recent_responses(self, n: int = 5):
        with self._lock:
            return [
                {'timestamp': r['timestamp'], 'length': len(r['response'])}
                for r in self._responses[-n:]
            ]

    def clear_all(self) -> None:
        with self._lock:
            self._prompt = None
            self._responses.clear()


store = InMemoryStore()

@app.route('/send-prompt', methods=['POST'])
def send_prompt():
    """Receive a prompt from a Python script."""

    try:
        data = request.get_json()
        if not data or 'prompt' not in data:
            return jsonify({'error': 'No prompt provided'}), 400

        prompt = data['prompt']
        store.set_prompt(prompt)

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f'Prompt received and stored [{timestamp}]: "{prompt}"')

        return jsonify({
            'status': 'success',
            'message': 'Prompt received',
            'timestamp': timestamp
        })

    except Exception as e:
        logger.error(f'Error processing prompt: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/get-prompt', methods=['GET'])
def get_prompt():
    """Send the stored prompt to the userscript and clear it."""

    prompt_to_send = store.pop_prompt()
    if prompt_to_send:
        logger.info(f'Prompt sent to userscript: "{prompt_to_send}"')

    return jsonify({'prompt': prompt_to_send})


@app.route('/ack-prompt', methods=['POST'])
def ack_prompt():
    """Acknowledge the prompt and clear it if present."""

    if store.has_prompt():
        logger.info('Prompt acknowledged and cleared')
    else:
        logger.info('Ack called but no prompt stored')

    store.clear_prompt()
    return jsonify({'status': 'success'})

@app.route('/process-response', methods=['POST'])
def process_response():
    """Receive the AI response from the userscript."""

    try:
        data = request.get_json()
        if not data or 'response' not in data:
            return jsonify({'error': 'No response provided'}), 400

        response = data['response']
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Store response in history
        store.add_response(timestamp, response)
        
        # Print the response
        print('\n' + '='*60)
        print(f'AI Response Received [{timestamp}]')
        print('='*60)
        print(response)
        print('='*60)
        
        logger.info(f'AI response received and processed (length: {len(response)} chars)')
        
        return jsonify({
            'status': 'success',
            'message': 'Response received',
            'timestamp': timestamp,
            'response_length': len(response)
        })
        
    except Exception as e:
        logger.error(f'Error processing response: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/test-response', methods=['POST'])
def generate_test_response():
    try:
        data = request.get_json()
        if not data or 'prompt' not in data:
            return jsonify({'error': 'No prompt provided'}), 400

        prompt = data['prompt']
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        api_url = os.getenv('MYGPT_API_URL')
        api_key = os.getenv('MYGPT_API_KEY')
        if not api_url or not api_key:
            logger.error('MYGPT_API_URL or MYGPT_API_KEY not configured')
            return jsonify({'error': 'myGPT API is not configured'}), 500

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        try:
            api_response = requests.post(
                api_url,
                headers=headers,
                json={'prompt': prompt},
                timeout=30
            )
            api_response.raise_for_status()
            api_data = api_response.json()
            test_response = api_data.get('response') or api_data.get('answer') or ''
        except requests.Timeout:
            logger.error('Request to myGPT API timed out')
            return jsonify({'error': 'myGPT API request timed out'}), 504
        except requests.RequestException as e:
            logger.error(f'myGPT API request failed: {e}')
            return jsonify({'error': 'myGPT API request failed', 'details': str(e)}), 502
        except ValueError:
            logger.error('Invalid JSON from myGPT API')
            return jsonify({'error': 'Invalid response from myGPT API'}), 502

        if not test_response:
            logger.warning('Empty response from myGPT API')
            return jsonify({'error': 'Empty response from myGPT API'}), 502

        logger.info(f'Response received from myGPT API: {len(test_response)} chars')

        # Generate a simple test response based on the prompt
        if "meeting" in prompt.lower() or "confirm" in prompt.lower():
            test_response = "Yes, the meeting is confirmed for 10 AM tomorrow. Looking forward to it!"
        elif "proposal" in prompt.lower() or "think" in prompt.lower():
            test_response = "I think it looks solid overall, but we might need to refine a couple of points before moving forward."
        elif "hvornår" in prompt.lower() or "mødes" in prompt.lower():
            test_response = "Hej! Vi kan mødes i morgen kl. 14:00. Hvad siger du til det?"
        elif "summary" in prompt.lower() or "status" in prompt.lower():
            test_response = "Based on the recent messages, here's a brief summary: Several questions were asked about meetings and proposals. All messages require responses."
        else:
            test_response = "Thank you for your message. I'll get back to you soon."

        # Store response in history
        store.add_response(timestamp, test_response)
        
        logger.info(f'Test response generated: {len(test_response)} chars')


        return jsonify({
            'status': 'success',
            'message': 'Response generated via myGPT API',
            'timestamp': timestamp,
            'response': test_response,
            'response_length': len(test_response)
        })

    except Exception as e:
        logger.error(f'Error generating test response: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/status', methods=['GET'])
def get_status():
    """Get server status and recent activity."""
    return jsonify({
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'stored_prompt': store.has_prompt(),
        'response_count': store.response_count(),
        'recent_responses': store.recent_responses(),
    })

@app.route('/history', methods=['GET'])
def get_history():
    """Get response history."""
    responses = store.get_responses()
    return jsonify({
        'total_responses': len(responses),
        'responses': responses
    })

@app.route('/clear', methods=['POST'])
def clear_data():
    """Clear stored prompt and response history."""

    store.clear_all()

    logger.info('Stored prompt and response history cleared')
    return jsonify({
        'status': 'success',
        'message': 'Data cleared'
    })

if __name__ == '__main__':
    print('='*60)
    print('myGPT API Server - Python Version')
    print('='*60)
    print('Server starting on http://localhost:8001')
    print('Available endpoints:')
    print('  POST /send-prompt    - Send a prompt from Python')
    print('  GET  /get-prompt     - Get prompt (userscript)')
    print('  POST /ack-prompt     - Acknowledge prompt')
    print('  POST /process-response - Receive AI response (userscript)')
    print('  POST /test-response  - Generate test response (for testing)')
    print('  GET  /status         - Server status')
    print('  GET  /history        - Response history')
    print('  POST /clear          - Clear data')
    print('='*60)
    
    try:
        app.run(host='0.0.0.0', port=8001, debug=False)
    except KeyboardInterrupt:
        print('\nServer stopped by user')
    except Exception as e:
        logger.error(f'Server error: {str(e)}')
