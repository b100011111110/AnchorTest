import os
import time
from dotenv import load_dotenv
from cerebras.cloud.sdk import Cerebras

# Load environment variables
load_dotenv()

def test_cerebras():
    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        print("❌ Cerebras: API key not set.")
        return

    print(f"Testing Cerebras (llama3.1-8b)...")
    try:
        client = Cerebras(api_key=api_key)
        start_time = time.time()
        completion = client.chat.completions.create(
            model="llama3.1-8b",
            messages=[{"role": "user", "content": "Say 'Cerebras connection successful!'"}]
        )
        duration = time.time() - start_time
        response = completion.choices[0].message.content
        print(f"✅ Cerebras Success: {response}")
        print(f"   Latency: {duration:.4f}s")
    except Exception as e:
        print(f"❌ Cerebras Failed: {str(e)}")

if __name__ == "__main__":
    print("--- Cerebras API Connectivity Test ---\n")
    test_cerebras()
    print("\n--- Test Complete ---")
