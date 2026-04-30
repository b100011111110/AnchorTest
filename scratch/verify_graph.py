from neo4j import GraphDatabase
import json
import os
from dotenv import load_dotenv

def check_graph():
    load_dotenv()
    url = os.getenv("NEO4J_URL")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    
    driver = GraphDatabase.driver(url, auth=(user, password))
    
    with driver.session() as session:
        # Check Systems
        systems = session.run("MATCH (s:System) RETURN s.name as name").value()
        print(f"Systems found: {systems}")
        
        # Check Primitives
        primitives = session.run("MATCH (p:Primitive) RETURN p.name as name").value()
        print(f"Primitives found: {primitives}")
        
        # Check Enums
        enums = session.run("MATCH (e:Enum) RETURN e.name as name").value()
        print(f"Enums found: {enums}")
        
        # Check Concurrency Models
        concurrency = session.run("MATCH (c:ConcurrencyModel) RETURN c.name as name").value()
        print(f"Concurrency Models found: {concurrency}")
        
        # Check Method nodes
        methods = session.run("MATCH (m:Method) RETURN m.name as name").value()
        print(f"Methods found: {methods}")
        
        # Check Fields linked to Primitives
        linked_fields = session.run("MATCH (f:Field)-[:OF_TYPE]->(p:Primitive) RETURN count(f) as count").single()["count"]
        print(f"Fields linked to Primitives: {linked_fields}")

    driver.close()

if __name__ == "__main__":
    check_graph()
