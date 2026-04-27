import os
import time
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI

# Load environment variables
load_dotenv()

def test_groq():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or "your_groq_api_key_here" in api_key:
        print("❌ Groq: API key not set or is still placeholder.")
        return

    print("Testing Groq (llama-3.1-8b-instant)...")
    try:
        client = Groq(api_key=api_key)
        start_time = time.time()
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Say 'Groq connection successful!'"}]
        )
        duration = time.time() - start_time
        response = completion.choices[0].message.content
        print(f"✅ Groq Success: {response}")
        print(f"   Latency: {duration:.2f}s")
    except Exception as e:
        print(f"❌ Groq Failed: {str(e)}")

def test_openrouter():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or "your_openrouter_api_key_here" in api_key:
        print("❌ OpenRouter: API key not set or is still placeholder.")
        return

    print("\nTesting OpenRouter (openai/gpt-oss-120b)...")
    try:
        # OpenRouter uses the OpenAI SDK
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        start_time = time.time()
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b", # Using the identified model
            messages=[{"role": "user", "content": "Say 'OpenRouter connection successful!'"}]
        )
        duration = time.time() - start_time
        response = completion.choices[0].message.content
        print(f"✅ OpenRouter Success: {response}")
        print(f"   Latency: {duration:.2f}s")
    except Exception as e:
        print(f"❌ OpenRouter Failed: {str(e)}")

if __name__ == "__main__":
    print("--- API Key Connectivity Test ---\n")
    test_groq()
    test_openrouter()
    print("\n--- Test Complete ---")
