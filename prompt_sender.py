#!/usr/bin/env python3
"""
myGPT Prompt Sender - Python Version
A Python script to send prompts to the myGPT API server.
Can be used as a module in other Python projects.
"""

import requests
import json
import time
from typing import Optional, Dict, Any
import logging
import os
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

__all__ = ["myGPTAPI", "myGPTConfig"]


@dataclass
class myGPTConfig:
    """Configuration for accessing the myGPT API."""
    api_url: str = os.getenv("MYGPT_API_URL", "")
    api_key: str = os.getenv("MYGPT_API_KEY", "")

class myGPTAPI:
    """Python client for the myGPT API server."""

    def __init__(self, server_url: str = "http://localhost:8001", config: Optional[myGPTConfig] = None):
        """
        Initialize the myGPT API client.

        Args:
            server_url (str): URL of the myGPT API server
            config (myGPTConfig, optional): myGPT API credentials
        """
        self.server_url = server_url.rstrip('/')
        self.config = config or myGPTConfig()
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'myGPT-Python-Client/1.0'
        })
        # Include API key header if provided (aligns with server's X-API-KEY)
        api_key = os.getenv("API_KEY", "")
        if api_key:
            self.session.headers.update({'X-API-KEY': api_key})
    
    def send_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        Send a prompt to the myGPT server.
        
        Args:
            prompt (str): The prompt to send to myGPT
            
        Returns:
            Dict[str, Any]: Server response with status and timestamp
            
        Raises:
            requests.RequestException: If the request fails
        """
        try:
            response = self.session.post(
                f"{self.server_url}/send-prompt",
                json={"prompt": prompt}
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Prompt sent successfully: {prompt[:50]}...")
            return result
            
        except requests.RequestException as e:
            logger.error(f"Failed to send prompt: {e}")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current server status.
        
        Returns:
            Dict[str, Any]: Server status information
        """
        try:
            response = self.session.get(f"{self.server_url}/status")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get status: {e}")
            raise
    
    def get_history(self) -> Dict[str, Any]:
        """
        Get response history from the server.
        
        Returns:
            Dict[str, Any]: Response history
        """
        try:
            response = self.session.get(f"{self.server_url}/history")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get history: {e}")
            raise
    
    def clear_data(self) -> Dict[str, Any]:
        """
        Clear stored prompt and response history.
        
        Returns:
            Dict[str, Any]: Server response
        """
        try:
            response = self.session.post(f"{self.server_url}/clear")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to clear data: {e}")
            raise
    
    def wait_for_response(self, timeout: int = 120, check_interval: int = 2) -> Optional[str]:
        """
        Wait for a response from myGPT.
        
        Args:
            timeout (int): Maximum time to wait in seconds
            check_interval (int): How often to check for new responses in seconds
            
        Returns:
            Optional[str]: The response text if received, None if timeout
        """
        start_time = time.time()
        initial_count = 0
        
        try:
            # Get initial response count
            status = self.get_status()
            initial_count = status.get('response_count', 0)
            logger.info(f"Waiting for response... (current count: {initial_count})")
            
            while time.time() - start_time < timeout:
                time.sleep(check_interval)
                
                try:
                    status = self.get_status()
                    current_count = status.get('response_count', 0)
                    
                    if current_count > initial_count:
                        # New response received
                        history = self.get_history()
                        if history.get('responses'):
                            latest_response = history['responses'][-1]
                            logger.info(f"Response received after {time.time() - start_time:.1f} seconds")
                            return latest_response['response']
                
                except requests.RequestException:
                    # Continue waiting even if status check fails
                    pass
            
            logger.warning(f"Timeout waiting for response after {timeout} seconds")
            return None
            
        except Exception as e:
            logger.error(f"Error waiting for response: {e}")
            return None
    
    def ask(self, prompt: str, wait_for_response: bool = True, timeout: int = 120) -> Dict[str, Any]:
        """
        Send a prompt and optionally wait for the response.
        
        Args:
            prompt (str): The prompt to send
            wait_for_response (bool): Whether to wait for the response
            timeout (int): Maximum time to wait for response in seconds
            
        Returns:
            Dict[str, Any]: Result containing prompt status and optionally the response
        """
        result = {
            'prompt_sent': False,
            'response_received': False,
            'response': None,
            'error': None
        }
        
        try:
            # Send the prompt
            prompt_result = self.send_prompt(prompt)
            result['prompt_sent'] = True
            result['prompt_timestamp'] = prompt_result.get('timestamp')
            
            if wait_for_response:
                # Wait for the response
                response = self.wait_for_response(timeout=timeout)
                if response:
                    result['response_received'] = True
                    result['response'] = response
                else:
                    result['error'] = 'Response timeout'
            else:
                result['message'] = 'Prompt sent, not waiting for response'
                
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Error in ask(): {e}")
        
        return result

    def generate_test_response(self, prompt: str) -> Dict[str, Any]:
        """
        Generate a test response using the test endpoint (for testing without userscript).
        
        Args:
            prompt (str): The prompt to generate a response for
            
        Returns:
            Dict[str, Any]: Test response with status and response text
        """
        try:
            response = self.session.post(
                f"{self.server_url}/test-response",
                json={"prompt": prompt}
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Test response generated successfully: {len(result.get('response', ''))} chars")
            return result
            
        except requests.RequestException as e:
            logger.error(f"Failed to generate test response: {e}")
            raise

def interactive_mode():
    """Run the script in interactive mode."""
    print("="*60)
    print("myGPT Prompt Sender - Interactive Mode")
    print("="*60)
    print("Type your prompt and press Enter to send it to myGPT.")
    print("Type 'status' to check server status.")
    print("Type 'history' to see response history.")
    print("Type 'clear' to clear data.")
    print("Type 'exit' to quit.")
    print("="*60)
    
    api = myGPTAPI()
    
    try:
        while True:
            try:
                user_input = input("\nEnter prompt (or command): ").strip()
                
                if not user_input:
                    continue
                    
                if user_input.lower() == 'exit':
                    print("Goodbye!")
                    break
                    
                elif user_input.lower() == 'status':
                    status = api.get_status()
                    print(f"\nServer Status:")
                    print(f"  Status: {status.get('status')}")
                    print(f"  Has stored prompt: {status.get('stored_prompt')}")
                    print(f"  Response count: {status.get('response_count')}")
                    
                elif user_input.lower() == 'history':
                    history = api.get_history()
                    responses = history.get('responses', [])
                    print(f"\nResponse History ({len(responses)} responses):")
                    for i, resp in enumerate(responses[-5:], 1):  # Show last 5
                        print(f"  {i}. [{resp['timestamp']}] - {len(resp['response'])} chars")
                        
                elif user_input.lower() == 'clear':
                    result = api.clear_data()
                    print(f"Data cleared: {result.get('message')}")
                    
                else:
                    # Send the prompt
                    print(f"\nSending prompt: {user_input}")
                    result = api.ask(user_input, wait_for_response=True)
                    
                    if result['prompt_sent']:
                        if result['response_received']:
                            print(f"\n✅ Response received ({len(result['response'])} characters)")
                        else:
                            print(f"\n❌ No response received: {result.get('error', 'Unknown error')}")
                    else:
                        print(f"\n❌ Failed to send prompt: {result.get('error', 'Unknown error')}")
                        
            except KeyboardInterrupt:
                print("\n\nExiting...")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    interactive_mode()
