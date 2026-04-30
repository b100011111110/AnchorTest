from neo4j import GraphDatabase
from db_connect import load_connections

def debug():
    cfg = load_connections()["neo4j"]
    driver = GraphDatabase.driver(cfg["url"], auth=(cfg["userid"], cfg["password"]))
    with driver.session(database="neo4j") as session:
        print("\n--- Fields for CURRENT WEATHER ---")
        res = session.run("""
            MATCH (e:Endpoint {name: 'CURRENT WEATHER', system: 'Weather API'})-[:ACCEPTS]->(f:Field)
            RETURN f.name as name, f.required as required, f.type as type
        """)
        for r in res: print(f"{r['name']}: required={r['required']}, type={r['type']}")

        print("\n--- Logic Gates for CURRENT WEATHER ---")
        res = session.run("""
            MATCH (e:Endpoint {name: 'CURRENT WEATHER', system: 'Weather API'})-[:ENFORCES]->(g:LogicGate)
            RETURN g.name as name, g.expression as expression
        """)
        for r in res: print(f"{r['name']}: {r['expression']}")

    driver.close()

if __name__ == "__main__":
    debug()
