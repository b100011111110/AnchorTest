import json
import os
import random
import re
import uuid
from datetime import datetime, timedelta
from neo4j import GraphDatabase

def load_connections():
    with open(".env", "r") as f:
        lines = f.readlines()
    config = {"neo4j": {}}
    for line in lines:
        if "=" in line:
            k, v = line.strip().split("=", 1)
            if k == "NEO4J_URL": config["neo4j"]["url"] = v
            if k == "NEO4J_USER": config["neo4j"]["userid"] = v
            if k == "NEO4J_PASSWORD": config["neo4j"]["password"] = v
    return config

class GraphNavigator:
    def __init__(self, driver, database=None):
        self.driver = driver
        self.database = database

    def get_all_systems(self):
        query = "MATCH (e:Endpoint) RETURN DISTINCT e.system as name"
        with self.driver.session(database=self.database) as session:
            result = session.run(query)
            return [record["name"] for record in result]

    def get_all_endpoints(self, system_name):
        query = "MATCH (e:Endpoint {system: $system}) RETURN e.name as name"
        with self.driver.session(database=self.database) as session:
            result = session.run(query, system=system_name)
            return [record["name"] for record in result]

    def get_endpoint_details(self, endpoint_name, system_name):
        query = """
        MATCH (e:Endpoint {name: $endpoint, system: $system})
        OPTIONAL MATCH (e)-[:AT_PATH]->(p:Path)
        OPTIONAL MATCH (e)-[:ACCEPTS]->(rf:Field)
        OPTIONAL MATCH (e)-[:RETURNS]->(rsf:Field)
        RETURN e, p.template as path, collect(DISTINCT rf) as req_fields, collect(DISTINCT rsf) as res_fields
        """
        with self.driver.session(database=self.database) as session:
            record = session.run(query, system=system_name, endpoint=endpoint_name).single()
            if not record: return None, None, [], []
            return record["e"], record["path"], record["req_fields"], record["res_fields"]

    def get_logic_gates(self, endpoint_name, system_name):
        query = """
        MATCH (e:Endpoint {name: $endpoint, system: $system})-[rel:ENFORCES]->(g:LogicGate)
        OPTIONAL MATCH (g)-[:ON_FAIL_THROWS]->(err:Error)
        RETURN g, err.code as error_code, err.msg as error_msg
        ORDER BY rel.rank
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, system=system_name, endpoint=endpoint_name)
            gates = []
            for record in result:
                g = dict(record["g"])
                g["error_code"] = record["error_code"]
                g["error_msg"] = record["error_msg"]
                gates.append(g)
            return gates

class DataSynthesizer:
    def __init__(self, nav):
        self.nav = nav

    def synthesize_field(self, field, mode='VALID'):
        name = str(field.get('name', 'field')).lower()
        type_name = str(field.get('type', 'String')).lower()
        
        if mode == 'VALID':
            if 'location' in name or 'query' in name: return "London"
            if 'date' in name: return (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
            if 'days' in name: return 5
            if 'lat' in name: return 51.5
            if 'lon' in name: return -0.12
            if 'int' in type_name: return 10
            return "test_value"
        else:
            if 'location' in name or 'query' in name: return "X" 
            if 'date' in name: return (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
            if 'days' in name: return 99
            if 'lat' in name: return 150.0
            return "INVALID"

class TestCaseFactory:
    def __init__(self, database=None):
        cfg = load_connections()["neo4j"]
        self.driver = GraphDatabase.driver(cfg["url"], auth=(cfg["userid"], cfg["password"]))
        self.nav = GraphNavigator(self.driver, database=database)
        self.synth = DataSynthesizer(self.nav)

    def close(self):
        self.driver.close()

    def generate_suite_for_system(self, system_name):
        endpoints = self.nav.get_all_endpoints(system_name)
        suite = []
        for ep_name in endpoints:
            ep, path, req, res = self.nav.get_endpoint_details(ep_name, system_name)
            gates = self.nav.get_logic_gates(ep_name, system_name)
            
            # POSITIVE TEST CASE
            payload = {f.get('name'): self.synth.synthesize_field(f, mode='VALID') for f in req if f.get('name')}
            pos_assertions = []
            for g in gates:
                expr = g.get('expression', "").strip()
                if expr:
                    # Strip common prefixes from expression
                    expr = re.sub(r'\b(req|res|body|data|error)\.', '', expr)
                    pos_assertions.append({"id": f"RULE_{g['name'].upper()}", "logic": expr})
            
            suite.append({
                "test_id": f"POS_{ep_name.upper().replace(' ', '_')}_SUCCESS",
                "target": {"method": ep.get('method'), "url": path, "payload": payload},
                "assertions": pos_assertions
            })

            # NEGATIVE TEST CASES (Only for INPUT guards)
            for g in gates:
                # Skip negative tests for OUTPUT integrity gates as they can't be triggered by input mutation
                if g.get('scope') == 'OUTPUT' or 'integrity' in g['name'].lower() or 'structure' in g['name'].lower():
                    continue

                neg_payload = payload.copy()
                gate_name = g['name'].lower()
                headers = {}
                
                # Surgical mutations based on gate intent
                if "auth" in gate_name:
                    headers["X-API-Key"] = ""
                elif "latlon" in gate_name or "crossfield" in gate_name:
                    neg_payload["lat"] = 51.5; neg_payload["lon"] = None
                elif "schemavalidation" in gate_name or "fieldconstraints" in gate_name:
                    # Violate basic type or format
                    if req:
                        f = random.choice([f for f in req if f.get('name')])
                        if f['name'] == 'days': neg_payload[f['name']] = "not_a_number"
                        elif f['name'] == 'lat': neg_payload[f['name']] = "invalid"
                        else: neg_payload[f['name']] = ""
                elif "latrange" in gate_name or "lonrange" in gate_name:
                    for f in req:
                        if f.get('name') in ['lat', 'lon']: neg_payload[f['name']] = 999.0
                elif "locationexists" in gate_name or "exists" in gate_name:
                    for f in req:
                        if f.get('name') in ['location', 'query']: neg_payload[f['name']] = "NonExistentLocation_404"
                elif "businessrule" in gate_name or "rules" in gate_name:
                    # Look for fields mentioned in the gate name or just pick a relevant one
                    if "days" in gate_name:
                        if "days" in neg_payload: neg_payload["days"] = 99
                    elif "date" in gate_name:
                        if "date" in neg_payload: neg_payload["date"] = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                    elif "lat" in gate_name or "lon" in gate_name:
                        if "lat" in neg_payload: neg_payload["lat"] = 999.0
                    else:
                        # Pick any field and use INVALID mode
                        f_list = [f for f in req if f.get('name') and f['name'] in neg_payload]
                        if f_list:
                            f = random.choice(f_list)
                            neg_payload[f['name']] = self.synth.synthesize_field(f, mode='INVALID')
                elif "querylength" in gate_name or "length" in gate_name:
                    for f in req:
                        if f.get('name') == 'query' and 'query' in neg_payload: neg_payload[f['name']] = "X"
                else:
                    # Fallback mutation
                    f_list = [f for f in req if f.get('name')]
                    if f_list:
                        f = random.choice(f_list)
                        neg_payload[f['name']] = self.synth.synthesize_field(f, mode='INVALID')

                suite.append({
                    "test_id": f"NEG_{ep_name.upper().replace(' ', '_')}_{g['name'].upper()}",
                    "target": {"method": ep.get('method'), "url": path, "payload": neg_payload, "headers": headers},
                    "assertions": [
                        {"id": "CHECK_ERROR_CODE", "logic": f"code == '{g.get('error_code', 'ERROR')}'"},
                        {"id": "CHECK_ERROR_MESSAGE", "logic": f"message == '{g.get('error_msg', 'Error')}'"}
                    ]
                })
        return suite
