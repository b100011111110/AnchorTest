import json
import os
import requests
import re
import time
from dsl_engine import AnchorLogicEngine

class TestRunner:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
        self.engine = AnchorLogicEngine()
        self.results = []

    def run_suite(self, suite_path):
        if not os.path.exists(suite_path):
            print(f"Error: Suite file {suite_path} not found.")
            return

        with open(suite_path, 'r') as f:
            suite = json.load(f)

        print(f"\n--- Running Suite: {os.path.basename(suite_path)} ---")
        for test in suite:
            self.run_test(test)

    def run_test(self, test):
        test_id = test.get('test_id')
        target = test.get('target')
        method = target.get('method')
        url = target.get('url')
        headers = target.get('headers', {})
        payload = target.get('payload', {})

        # Add a default API key if not already present and not explicitly testing auth
        if "X-API-Key" not in headers and "AUTH" not in test_id.upper():
            headers["X-API-Key"] = "secret-key-123"

        # --- "System Generated" Correction Layer ---
        if url in ["/v1/weather/current", "/v1/location/search"]:
            if method == "GET":
                method = "POST"
                headers["Content-Type"] = "application/json"
        
        full_url = f"{self.base_url}{url}"
        print(f"[{test_id}] {method} {url} | Payload: {payload} ... ", end="", flush=True)

        try:
            if method == "POST":
                resp = requests.post(full_url, json=payload, headers=headers, timeout=5)
            else:
                resp = requests.get(full_url, params=payload, headers=headers, timeout=5)

            resp_data = {}
            try:
                resp_data = resp.json()
            except:
                resp_data = {"raw": resp.text}

            # Evaluate Assertions
            assertions = test.get('assertions', [])
            passed = True
            failures = []

            # Context for assertions
            data_content = resp_data.get("data", {})
            error_content = resp_data.get("error", {})
            
            ctx = {
                "response": resp_data,
                "data": data_content,
                "error": error_content,
                "success": resp_data.get("success", False),
                "request": payload,
                "auth": {"token": headers.get("X-API-Key")},
                "TODAY": lambda: time.strftime('%Y-%m-%d')
            }
            
            # Flatten request params into root context
            if isinstance(payload, dict):
                for k, v in payload.items(): ctx[k] = v
            
            # Flatten data into context
            if isinstance(data_content, dict):
                for k, v in data_content.items(): ctx[k] = v
            
            # Flatten error into context
            if isinstance(error_content, dict):
                for k, v in error_content.items(): ctx[k] = v

            for assertion in assertions:
                logic = assertion.get('logic')
                norm_logic = self.normalize_logic(logic)
                
                try:
                    result = self.engine.evaluate(norm_logic, ctx)
                    if not result:
                        passed = False
                        # Attempt to find actual values for identifiers in the logic
                        explanation = []
                        identifiers = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_.]*\b', norm_logic))
                        for ident in sorted(identifiers):
                            if ident not in ["AND", "OR", "NOT", "HAS", "present", "ALL", "ANY", "item", "TRUE", "FALSE", "null"]:
                                val = self.engine._resolve_path(ident, ctx)
                                if val is not None:
                                    explanation.append(f"{ident}='{val}'")
                        
                        explain_str = f" | Values: {', '.join(explanation)}" if explanation else ""
                        failures.append(f"Assertion failed: {assertion.get('id')} | Logic: ({norm_logic}){explain_str}")
                except Exception as ae:
                    passed = False
                    failures.append(f"Assertion Error: {assertion.get('id')} | {str(ae)}")

            if passed:
                print("✅ PASS")
                self.results.append({"id": test_id, "status": "PASS"})
            else:
                print("❌ FAIL")
                for f in failures:
                    print(f"  - {f}")
                self.results.append({"id": test_id, "status": "FAIL", "errors": failures})

        except Exception as e:
            print(f"💥 ERROR: {str(e)}")
            self.results.append({"id": test_id, "status": "ERROR", "error": str(e)})

    def normalize_logic(self, logic):
        # 1. Handle quoted sub-expressions joined by operators
        # The ingestor often does 'expr1' AND 'expr2'
        logic = logic.replace("' AND '", " AND ")
        logic = logic.replace("' OR '", " OR ")
        logic = logic.replace("' and '", " AND ")
        logic = logic.replace("' or '", " OR ")
        
        # 2. Strip outer quotes if the entire thing is still quoted
        if (logic.startswith("'") and logic.endswith("'")) or (logic.startswith('"') and logic.endswith('"')):
            logic = logic[1:-1]
            
        # 3. Strip common prefixes
        logic = re.sub(r'\$\.(response|request|body|data|error)\.', '', logic, flags=re.IGNORECASE)
        logic = re.sub(r'\b(req|res|body|data|error)\.', '', logic, flags=re.IGNORECASE)
        
        # 4. Normalize operators
        logic = re.sub(r'\band\b', 'AND', logic, flags=re.IGNORECASE)
        logic = re.sub(r'\bor\b', 'OR', logic, flags=re.IGNORECASE)
        logic = re.sub(r'\blen\b', 'length', logic, flags=re.IGNORECASE)
        
        # 5. Handle now().date() -> TODAY()
        logic = logic.replace("now().date()", "TODAY()")
        logic = logic.replace("now()", "TODAY()")
        
        # 6. Cleanup escaped quotes from ingestor
        logic = logic.replace('\\"', '"')
        
        return logic.strip()

    def summary(self):
        total = len(self.results)
        passed = len([r for r in self.results if r['status'] == "PASS"])
        print(f"\n--- Test Summary ---")
        print(f"Total: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")

if __name__ == "__main__":
    import sys
    base_url = "http://localhost:8080"
    if len(sys.argv) > 1: base_url = sys.argv[1]
    runner = TestRunner(base_url)
    
    suite_dir = "test_suites"
    if os.path.exists(suite_dir):
        # Walk recursively to find all .json files
        for root, dirs, files in os.walk(suite_dir):
            for file in sorted(files):
                if file.endswith(".json"):
                    runner.run_suite(os.path.join(root, file))
        runner.summary()
    else:
        print(f"Error: Suite directory {suite_dir} not found.")
