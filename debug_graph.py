from neo4j import GraphDatabase
from db_connect import load_connections

cfg = load_connections()["neo4j"]
driver = GraphDatabase.driver(cfg["url"], auth=(cfg["userid"], cfg["password"]))

with driver.session() as session:
    print("--- Endpoints ---")
    res = session.run("MATCH (e:Endpoint) RETURN e.name, e.auth_scope")
    for r in res:
        print(f"Endpoint: {r['e.name']}, Auth: {r['e.auth_scope']}")
    
    print("\n--- Fields for 'Create Account' ---")
    res = session.run("MATCH (e:Endpoint {name: 'Create Account'})-[:ACCEPTS_FIELD]->(f:Field) RETURN f.name, f.regex, f.required")
    for r in res:
        print(f"Field: {r['f.name']}, Regex: {r['f.regex']}, Required: {r['f.required']}")

    print("\n--- LogicGates for 'Create Account' ---")
    res = session.run("MATCH (e:Endpoint {name: 'Create Account'})-[rel:ENFORCES]->(g:LogicGate) RETURN g.name, g.type, rel.rank")
    for r in res:
        print(f"Gate: {r['g.name']}, Type: {r['g.type']}, Rank: {r['rel.rank']}")

driver.close()
