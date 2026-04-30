from neo4j import GraphDatabase
from db_connect import load_connections

class GraphValidator:
    def __init__(self):
        cfg = load_connections()["neo4j"]
        self.driver = GraphDatabase.driver(
            cfg["url"], 
            auth=(cfg["userid"], cfg["password"])
        )

    def close(self):
        self.driver.close()

    def run_validation(self):
        print("--- Starting Execution Graph Validation (Universal Cold Logic Constraints) ---")
        violations = []

        with self.driver.session() as session:
            # 1. Unique Operation Key (per System)
            res = session.run("""
                MATCH (e:Endpoint)-[:USES_METHOD]->(m:Method),
                      (e)-[:AT_PATH]->(p:Path)
                WITH e.system as system, m.name as method, p.template as path, count(*) as c
                WHERE c > 1
                RETURN system, method, path, c
            """)
            for r in res:
                violations.append(f"Constraint 1 (Unique Operation Key) Violated: {r['system']} - {r['method']} {r['path']} appears {r['c']} times")

            # 2. Primitive/Enum Mapping
            res = session.run("MATCH (f:Field) WHERE NOT (f)-[:OF_TYPE]->() RETURN f.name, f.context")
            for r in res:
                violations.append(f"Constraint 2 (Type Mapping) Violated: Field {r['f.name']} ({r['f.context']}) has no OF_TYPE link")

            # 3. Range Bounds
            res = session.run("""
                MATCH (f:Field)-[:OF_TYPE]->(p:Primitive) 
                WHERE p.name IN ['Int', 'Float'] AND (f.min IS NULL OR f.max IS NULL) 
                RETURN f.name, f.context
            """)
            for r in res:
                violations.append(f"Constraint 3 (Range Bounds) Violated: Numeric Field {r['f.name']} ({r['f.context']}) missing min/max")

            # 4. String Rigidity
            res = session.run("""
                MATCH (f:Field)-[:OF_TYPE]->(p:Primitive) 
                WHERE p.name = 'String' AND f.regex IS NULL AND f.min IS NULL 
                RETURN f.name, f.context
            """)
            for r in res:
                violations.append(f"Constraint 4 (String Rigidity) Violated: String Field {r['f.name']} ({r['f.context']}) missing regex/min")

            # 5. Enum Integrity
            res = session.run("MATCH (f:Field)-[:OF_TYPE]->(e:Enum) WHERE NOT (e)-[:HAS_VALUE]->() RETURN f.name, e.name")
            for r in res:
                violations.append(f"Constraint 5 (Enum Integrity) Violated: Field {r['f.name']} linked to Enum {r['e.name']} with no values")

            # 6. Pre-condition Mapping
            res = session.run("MATCH (e:Endpoint) WHERE NOT (e)-[:REQUIRES_STATE]->(:StateVector) AND NOT e.name CONTAINS 'Create' AND NOT e.method = 'GET' RETURN e.name")
            for r in res:
                violations.append(f"Constraint 6 (Pre-condition Mapping) Violated: Mutation Endpoint {r['e.name']} missing StateVector pre-conditions")

            # 7. Post-condition Delta
            res = session.run("MATCH (e:Endpoint) WHERE NOT (e)-[:TRANSITIONS_TO]->(:StateVector) AND NOT e.method = 'GET' RETURN e.name")
            for r in res:
                violations.append(f"Constraint 7 (Post-condition Delta) Violated: Mutation Endpoint {r['e.name']} missing StateVector transitions")

            # 8. Validation Ranking
            res = session.run("MATCH (e:Endpoint) WHERE NOT (e)-[:ENFORCES]->(:LogicGate) RETURN e.name")
            for r in res:
                violations.append(f"Constraint 8 (Validation Ranking) Violated: Endpoint {r['e.name']} missing ranked LogicGates")

            # 9. Error-Code Parity
            res = session.run("MATCH (g:LogicGate) WHERE NOT (g)-[:ON_FAIL_THROWS]->(:Error) RETURN g.name")
            for r in res:
                violations.append(f"Constraint 9 (Error-Code Parity) Violated: LogicGate {r['g.name']} not linked to an Error node")

            # 10. Idempotency Tag
            res = session.run("MATCH (e:Endpoint) WHERE e.idempotency IS NULL OR NOT e.idempotency IN ['Idempotent', 'Non-Idempotent'] RETURN e.name")
            for r in res:
                violations.append(f"Constraint 10 (Idempotency Tag) Violated: Endpoint {r['e.name']} has invalid idempotency tag")

            # 11. Path-Param Parity
            res = session.run("""
                MATCH (p:Path)
                WITH p, split(p.template, '{') as parts
                UNWIND range(1, size(parts)-1) as i
                WITH p, split(parts[i], '}') [0] as param_name
                MATCH (e:Endpoint)-[:AT_PATH]->(p)
                WHERE NOT (e)-[:ACCEPTS]->(:Field {name: param_name, location: 'path'})
                RETURN e.name, param_name
            """)
            for r in res:
                violations.append(f"Constraint 11 (Path-Param Parity) Violated: Endpoint {r['e.name']} missing Field for path param {{{r['param_name']}}}")

            # 12. Mandatory Binary
            res = session.run("MATCH (f:Field) WHERE f.required IS NULL RETURN f.name, f.context")
            for r in res:
                violations.append(f"Constraint 12 (Mandatory Binary) Violated: Field {r['f.name']} ({r['f.context']}) missing 'required' boolean")

            # 13. System Integrity
            res = session.run("MATCH (e:Endpoint) WHERE e.system IS NULL RETURN e.name")
            for r in res:
                violations.append(f"Constraint 13 (System Integrity) Violated: Endpoint {r['e.name']} has no associated system")

            # 14. Faker Coverage
            res = session.run("MATCH (f:Field) WHERE f.required = True AND f.context = 'request' AND f.faker_provider IS NULL RETURN f.name")
            for r in res:
                violations.append(f"Constraint 14 (Faker Coverage) Violated: Required Request Field {r['f.name']} missing faker_provider")

            # 15. Oracle Reference
            res = session.run("MATCH (e:Endpoint)-[:TRANSITIONS_TO]->() WHERE NOT (e)-[:VERIFIED_BY]->(:Oracle) RETURN e.name")
            for r in res:
                violations.append(f"Constraint 15 (Oracle Reference) Violated: Mutation Endpoint {r['e.name']} missing Oracle verification link")

            # 16. Concurrency Model
            res = session.run("MATCH (e:Endpoint) WHERE NOT (e)-[:HAS_CONCURRENCY]->(:ConcurrencyModel) RETURN e.name")
            for r in res:
                violations.append(f"Constraint 16 (Concurrency Model) Violated: Endpoint {r['e.name']} missing ConcurrencyModel")

        if not violations:
            print("✅ All constraints passed! Graph is fully deterministic across all systems.")
        else:
            print("================================================================")
            print("  API ARCHITECTURAL POLICE - SYSTEM AUDIT")
            print("================================================================")
            for v in violations:
                print(f"  - {v}")
        
        return len(violations) == 0

if __name__ == "__main__":
    validator = GraphValidator()
    success = validator.run_validation()
    validator.close()
    if not success:
        exit(1)
