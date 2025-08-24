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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variables
stored_prompt = None
response_history = []

@app.route('/send-prompt', methods=['POST'])
def send_prompt():
    """Receive a prompt from a Python script."""
    global stored_prompt
    
    try:
        data = request.get_json()
        if not data or 'prompt' not in data:
            return jsonify({'error': 'No prompt provided'}), 400
        
        prompt = data['prompt']
        stored_prompt = prompt
        
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
    global stored_prompt
    
    prompt_to_send = stored_prompt
    if prompt_to_send:
        stored_prompt = None
        logger.info(f'Prompt sent to userscript: "{prompt_to_send}"')
    
    return jsonify({'prompt': prompt_to_send})


@app.route('/ack-prompt', methods=['POST'])
def ack_prompt():
    """Acknowledge the prompt and clear it if present."""
    global stored_prompt

    if stored_prompt is not None:
        logger.info('Prompt acknowledged and cleared')
    else:
        logger.info('Ack called but no prompt stored')

    stored_prompt = None
    return jsonify({'status': 'success'})

@app.route('/process-response', methods=['POST'])
def process_response():
    """Receive the AI response from the userscript."""
    global response_history
    
    try:
        data = request.get_json()
        if not data or 'response' not in data:
            return jsonify({'error': 'No response provided'}), 400
        
        response = data['response']
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Store response in history
        response_history.append({
            'timestamp': timestamp,
            'response': response
        })
        
        # Keep only last 10 responses
        if len(response_history) > 10:
            response_history.pop(0)
        
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
    """Generate a response by calling the external myGPT API."""
    global stored_prompt, response_history

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

        # Store response in history
        response_history.append({
            'timestamp': timestamp,
            'response': test_response
        })

        # Keep only last 10 responses
        if len(response_history) > 10:
            response_history.pop(0)

        logger.info(f'Response received from myGPT API: {len(test_response)} chars')

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
        'stored_prompt': stored_prompt is not None,
        'response_count': len(response_history),
        'recent_responses': [
            {
                'timestamp': r['timestamp'],
                'length': len(r['response'])
            }
            for r in response_history[-5:]  # Last 5 responses
        ]
    })

@app.route('/history', methods=['GET'])
def get_history():
    """Get response history."""
    return jsonify({
        'total_responses': len(response_history),
        'responses': response_history
    })

@app.route('/clear', methods=['POST'])
def clear_data():
    """Clear stored prompt and response history."""
    global stored_prompt, response_history
    
    stored_prompt = None
    response_history.clear()
    
    logger.info('Stored prompt and response history cleared')
    return jsonify({
        'status': 'success',
        'message': 'Data cleared'
    })

if __name__ == '__main__':
    print('='*60)
    print('myGPT API Server - Python Version')
    print('='*60)
    print('Server starting on http://localhost:5000')
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
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print('\nServer stopped by user')
    except Exception as e:
        logger.error(f'Server error: {str(e)}')
