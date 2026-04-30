import argparse
import sys
import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from llm_utils import extract_api_info
from ingestor import Neo4jIngestor
from generator import TestCaseFactory
from validator import GraphValidator
from db_connect import load_connections
from neo4j import GraphDatabase
from test_runner import TestRunner

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)

def get_system_databases():
    cfg = load_connections()["neo4j"]
    driver = GraphDatabase.driver(cfg["url"], auth=(cfg["userid"], cfg["password"]))
    databases = []
    try:
        with driver.session(database="system") as session:
            res = session.run("SHOW DATABASES")
            for record in res:
                name = record["name"]
                if name != "system":
                    databases.append(name)
    except:
        # Fallback for systems that don't support SHOW DATABASES
        databases = ["neo4j"]
    finally:
        driver.close()
    return databases

def main():
    parser = argparse.ArgumentParser(description="AnchorTest CLI — Graph Ingestor, Generator & Runner")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # init command
    init_parser = subparsers.add_parser("init", help="Initialize the graph from a document (clears DB by default)")
    init_parser.add_argument("--document", required=True, help="Path to the document file")
    init_parser.add_argument("--no-clear", action="store_true", help="Do NOT clear the database before ingestion")
    
    # validate command
    subparsers.add_parser("validate", help="Validate the graph against architectural constraints")
    
    # generate command
    gen_parser = subparsers.add_parser("generate", help="Generate test cases from the graph")
    gen_parser.add_argument("--system", help="Target a specific system name (e.g. 'Weather API')")
    gen_parser.add_argument("--output", default="test_suites", help="Output directory (default: test_suites)")
    
    # test command
    test_parser = subparsers.add_parser("test", help="Execute generated test cases against the server")
    test_parser.add_argument("--url", default="http://localhost:8080", help="Base URL of the target server")
    test_parser.add_argument("--suite-dir", default="test_suites", help="Directory containing test suites")
    test_parser.add_argument("--system", help="Target a specific system name (e.g. 'Weather API')")
    
    # run-all command (The "Everything" command)
    all_parser = subparsers.add_parser("run-all", help="Init, Generate, and Test in one go")
    all_parser.add_argument("--document", required=True, help="Path to the document file")
    all_parser.add_argument("--system", required=True, help="Target system name")
    all_parser.add_argument("--url", default="http://localhost:8080", help="Base URL of the target server")

    args = parser.parse_args()
    
    if args.command == "init" or args.command == "run-all":
        doc_path = Path(args.document)
        if not doc_path.exists():
            print(f"Error: Document {doc_path} not found.")
            sys.exit(1)
            
        print(f"Reading document: {doc_path}")
        with open(doc_path, "r") as f:
            text = f.read()
            
        print("Starting extraction...")
        try:
            system_info, endpoints, logic = extract_api_info(text)
            print(f"Extraction complete for system: {system_info.name}")
            
            ingestor = Neo4jIngestor()
            # Clear by default unless --no-clear is passed (and we are in 'init' mode)
            should_clear = True
            if args.command == "init" and args.no_clear:
                should_clear = False
                
            if should_clear:
                db_name = ingestor._normalize_db_name(system_info.name)
                print(f"Clearing database: {db_name}")
                ingestor._ensure_database(db_name)
                ingestor.clear_db(db_name)
                
            ingestor.ingest(system_info, endpoints, logic)
            ingestor.close()
            print("Ingestion complete.")
            
        except Exception as e:
            print(f"Error during ingestion: {e}")
            if args.command != "run-all": sys.exit(1)
            
    if args.command == "generate" or args.command == "run-all":
        # Get target system from run-all or from generate arg
        target_system = getattr(args, 'system', None)
        
        db_list = get_system_databases()
        output_dir = getattr(args, 'output', 'test_suites')
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        for db in db_list:
            print(f"Processing database: {db}...")
            factory = TestCaseFactory(database=db)
            systems = factory.nav.get_all_systems()
            
            for sys_name in systems:
                if target_system and sys_name != target_system:
                    continue
                    
                print(f"  Generating tests for system: {sys_name}...")
                suite = factory.generate_suite_for_system(sys_name)
                
                system_dir = os.path.join(output_dir, sys_name.replace(' ', '_'))
                if not os.path.exists(system_dir):
                    os.makedirs(system_dir)
                    
                features = {}
                for test in suite:
                    feat = test.get('feature', 'General')
                    if feat not in features: features[feat] = []
                    features[feat].append(test)
                    
                for feat, tests in features.items():
                    fname = f"{feat.replace(' ', '_')}.json"
                    target_path = os.path.join(system_dir, fname)
                    with open(target_path, "w") as f:
                        json.dump(tests, f, indent=2, cls=DateTimeEncoder)
                    print(f"    Wrote {len(tests)} tests to {target_path}")
                    
            factory.close()
        print("Generation complete.")
        
    if args.command == "test" or args.command == "run-all":
        base_url = getattr(args, 'url', "http://localhost:8080")
        suite_root = getattr(args, 'suite_dir', "test_suites")
        target_system = getattr(args, 'system', None)
        
        print(f"\n--- Starting Test Execution against {base_url} ---")
        runner = TestRunner(base_url=base_url)
        
        if target_system:
            # Run only for the specific system
            system_dir = os.path.join(suite_root, target_system.replace(' ', '_'))
            if os.path.exists(system_dir):
                for filename in sorted(os.listdir(system_dir)):
                    if filename.endswith(".json"):
                        runner.run_suite(os.path.join(system_dir, filename))
            else:
                print(f"Error: System directory {system_dir} not found.")
        else:
            # Run everything in suite_root
            for root, dirs, files in os.walk(suite_root):
                for filename in sorted(files):
                    if filename.endswith(".json"):
                        runner.run_suite(os.path.join(root, filename))
        
        runner.summary()
        
    if not args.command:
        parser.print_help()

if __name__ == "__main__":
    main()
