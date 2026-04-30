from llm_utils import extract_api_info
from pathlib import Path

doc_path = Path("DOCS/bank_v1.txt")
with open(doc_path, "r") as f:
    text = f.read()

print("Starting extraction...")
system_info, endpoints, logic = extract_api_info(text)

print("\n--- EXTRACTED ENDPOINTS ---")
for ep in endpoints.endpoints:
    print(f"Endpoint: {ep.name} ({ep.method} {ep.path})")
    print(f"  Gates: {[g.name for g in ep.validation_sequence]}")
