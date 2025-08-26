#!/usr/bin/env python3
"""
Example usage of the myGPT API in other Python projects.
This shows how to integrate the myGPT API into your own applications.
"""

from prompt_sender import myGPTAPI
import time

def basic_usage():
    """Basic usage example."""
    print("=== Basic Usage Example ===")
    
    # Initialize the API client
    api = myGPTAPI()
    
    # Send a simple prompt
    result = api.ask("What is the capital of France?")
    
    if result['response_received']:
        print(f"Response: {result['response']}")
    else:
        print(f"Error: {result.get('error')}")

def async_style_usage():
    """Example of sending prompt without waiting for response."""
    print("\n=== Async-Style Usage Example ===")
    
    api = myGPTAPI()
    
    # Send prompt without waiting
    result = api.ask("Explain quantum computing", wait_for_response=False)
    print(f"Prompt sent: {result['prompt_sent']}")
    print(f"Message: {result.get('message')}")
    
    # You can do other work here while waiting for response
    print("Doing other work while waiting for response...")
    time.sleep(2)
    
    # Check status
    status = api.get_status()
    print(f"Response count: {status.get('response_count')}")

def batch_processing():
    """Example of processing multiple prompts."""
    print("\n=== Batch Processing Example ===")
    
    api = myGPTAPI()
    
    prompts = [
        "What is machine learning?",
        "Explain neural networks",
        "What is deep learning?"
    ]
    
    responses = []
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\nProcessing prompt {i}/{len(prompts)}: {prompt}")
        
        result = api.ask(prompt, wait_for_response=True, timeout=60)
        
        if result['response_received']:
            responses.append({
                'prompt': prompt,
                'response': result['response'],
                'length': len(result['response'])
            })
            print(f"✅ Response received ({len(result['response'])} chars)")
        else:
            print(f"❌ Failed: {result.get('error')}")
    
    print(f"\nBatch processing complete. {len(responses)}/{len(prompts)} successful.")
    
    # Show summary
    for resp in responses:
        print(f"\nPrompt: {resp['prompt']}")
        print(f"Response length: {resp['length']} characters")
        print(f"Response preview: {resp['response'][:100]}...")

def error_handling():
    """Example of proper error handling."""
    print("\n=== Error Handling Example ===")
    
    try:
        # Try to connect to a non-existent server
        api = myGPTAPI("http://localhost:9999")
        result = api.ask("This will fail")
        print("Unexpected success!")
        
    except Exception as e:
        print(f"Expected error caught: {e}")
    
    # Now try with correct server
    try:
        api = myGPTAPI()  # Default localhost:8001
        result = api.ask("This should work")
        print("Success with correct server!")
        
    except Exception as e:
        print(f"Unexpected error: {e}")

def custom_integration():
    """Example of custom integration in a larger application."""
    print("\n=== Custom Integration Example ===")
    
    class MyApplication:
        def __init__(self):
            self.mygpt = myGPTAPI()
            self.conversation_history = []
        
        def ask_question(self, question: str) -> str:
            """Ask a question and return the response."""
            print(f"🤔 Asking: {question}")
            
            result = self.mygpt.ask(question, wait_for_response=True, timeout=120)
            
            if result['response_received']:
                response = result['response']
                
                # Store in conversation history
                self.conversation_history.append({
                    'question': question,
                    'answer': response,
                    'timestamp': result.get('prompt_timestamp')
                })
                
                print(f"💡 Answer received ({len(response)} chars)")
                return response
            else:
                error_msg = f"Failed to get response: {result.get('error')}"
                print(f"❌ {error_msg}")
                return error_msg
        
        def get_conversation_summary(self) -> dict:
            """Get a summary of the conversation."""
            return {
                'total_exchanges': len(self.conversation_history),
                'total_questions': len([c for c in self.conversation_history if c['question']]),
                'total_answers': len([c for c in self.conversation_history if c['answer']]),
                'average_answer_length': sum(len(c.get('answer', '')) for c in self.conversation_history) / max(len(self.conversation_history), 1)
            }
    
    # Use the custom application
    app = MyApplication()
    
    # Ask some questions
    app.ask_question("What is artificial intelligence?")
    app.ask_question("How does AI differ from traditional programming?")
    
    # Get summary
    summary = app.get_conversation_summary()
    print(f"\n📊 Conversation Summary:")
    print(f"  Total exchanges: {summary['total_exchanges']}")
    print(f"  Average answer length: {summary['average_answer_length']:.0f} chars")

if __name__ == "__main__":
    print("myGPT API Integration Examples")
    print("=" * 50)
    
    # Make sure the server is running before running examples
    print("Note: Make sure the myGPT API server is running on localhost:8001")
    print("You can start it with: python server.py")
    print()
    
    try:
        # Test server connection first
        api = myGPTAPI()
        status = api.get_status()
        print(f"✅ Server connection successful: {status.get('status')}")
        print()
        
        # Run examples
        basic_usage()
        async_style_usage()
        batch_processing()
        error_handling()
        custom_integration()
        
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        print("Please start the server first with: python server.py")
