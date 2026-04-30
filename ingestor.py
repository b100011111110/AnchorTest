import json
from neo4j import GraphDatabase
from db_connect import load_connections
from schema import SystemInfo, EndpointsList, LogicInfo

class Neo4jIngestor:
    def __init__(self):
        cfg = load_connections()["neo4j"]
        self.driver = GraphDatabase.driver(cfg["url"], auth=(cfg["userid"], cfg["password"]))

    def close(self):
        self.driver.close()

    def _normalize_db_name(self, name):
        import re
        db_name = name.lower()
        db_name = re.sub(r'[^a-z0-9.-]', '', db_name)
        if not db_name or not db_name[0].isalpha():
            db_name = "sys" + db_name
        return db_name[:63]

    def _ensure_database(self, db_name):
        # CREATE DATABASE requires connecting to 'system' and Enterprise Edition
        try:
            with self.driver.session(database="system") as session:
                print(f"Ensuring database '{db_name}' exists...")
                session.run(f"CREATE DATABASE {db_name} IF NOT EXISTS WAIT")
            return db_name
        except Exception as e:
            print(f"Warning: Could not create database '{db_name}' ({e}). Falling back to 'neo4j'.")
            return "neo4j"

    def clear_db(self, db_name):
        try:
            with self.driver.session(database=db_name) as session:
                session.run("MATCH (n) DETACH DELETE n")
        except:
            pass

    def clear_system(self, db_name, system_name):
        try:
            with self.driver.session(database=db_name) as session:
                print(f"Clearing existing nodes for system: {system_name} in DB: {db_name}...")
                session.run("MATCH (n) WHERE n.system = $sname DETACH DELETE n", sname=system_name)
        except:
            pass

    def ingest(self, system_info: SystemInfo, endpoints: EndpointsList, logic: LogicInfo):
        target_db = self._normalize_db_name(system_info.name)
        actual_db = self._ensure_database(target_db)
        
        # Automatically clear the system being ingested to prevent collisions
        self.clear_system(actual_db, system_info.name)
        
        with self.driver.session(database=actual_db) as session:
            # 1. Primitives & Global Taxonomy
            session.execute_write(self._create_primitives)
            session.execute_write(self._create_system_and_features_inst, system_info)
            session.execute_write(self._create_enums, system_info)
            session.execute_write(self._create_envelopes, system_info)
            
            # 2. Entities
            session.execute_write(self._create_entities_and_fields_inst, system_info)
            
            # 3. Endpoints & Logic
            session.execute_write(self._create_endpoints_inst, system_info.name, endpoints)
            session.execute_write(self._create_logic_and_scenarios_inst, system_info.name, logic)
            session.execute_write(self._create_test_templates_inst, logic) 
            session.execute_write(self._create_metrics_and_sql_inst, logic)
            session.execute_write(self._metadata_driven_linking, endpoints) 

    def _create_primitives(self, tx):
        types = ["String", "Int", "Float", "Bool", "Date"]
        for t in types:
            tx.run("MERGE (p:Primitive {name: $name})", name=t)

    def _create_system_and_features_inst(self, tx, data: SystemInfo):
        tx.run("MERGE (s:System {name: $name, version: $ver})", name=data.name, ver=data.version)
        for feat in data.features:
            tx.run("""
                MATCH (s:System {name: $sname})
                MERGE (f:Feature {name: $fname, system: $sname})
                MERGE (s)-[:HAS_FEATURE]->(f)
            """, sname=data.name, fname=feat.name)

    def _create_enums(self, tx, data: SystemInfo):
        for enum in data.global_enums:
            tx.run("MERGE (e:Enum {name: $name, system: $sname})", name=enum.name, sname=data.name)
            for val in enum.values:
                tx.run("""
                    MATCH (e:Enum {name: $ename, system: $sname})
                    MERGE (v:EnumValue {value: $val})
                    MERGE (e)-[:HAS_VALUE]->(v)
                """, ename=enum.name, val=val, sname=data.name)

    def _create_envelopes(self, tx, data: SystemInfo):
        for env in data.envelopes:
            tx.run("MERGE (e:Envelope {name: $name, system: $sname})", name=env.name, sname=data.name)
            for f in env.fields:
                tx.run("""
                    MATCH (e:Envelope {name: $ename, system: $sname})
                    MERGE (field:Field {name: $fname, context: 'envelope', owner: $ename, system: $sname})
                    SET field.type = $type, field.required = $req
                    MERGE (e)-[:HAS_FIELD]->(field)
                """, ename=env.name, fname=f.name, type=f.type, req=f.required, sname=data.name)

    def _create_entities_and_fields_inst(self, tx, data: SystemInfo):
        for ent in data.entities:
            tx.run("MERGE (e:Entity {name: $name, system: $sname})", name=ent.name, sname=data.name)
            for f in ent.fields:
                tx.run("""
                    MATCH (e:Entity {name: $ename, system: $sname})
                    MERGE (field:Field {name: $fname, context: 'entity', owner: $ename, system: $sname})
                    SET field.type = $type, field.required = $req, field.faker_provider = $faker
                    MERGE (e)-[:HAS_FIELD]->(field)
                """, ename=ent.name, fname=f.name, type=f.type, req=f.required, faker=f.faker_provider, sname=data.name)
                
                # Link to Primitive
                tx.run("""
                    MATCH (field:Field {name: $fname, context: 'entity', owner: $ename, system: $sname})
                    MATCH (p:Primitive {name: $type})
                    MERGE (field)-[:OF_TYPE]->(p)
                """, fname=f.name, type=f.type, ename=ent.name, sname=data.name)

    def _create_logic_gates(self, tx, gates, ep_name, system_name):
        for g in gates:
            tx.run("""
                MATCH (e:Endpoint {name: $ep_name, system: $sname})
                MERGE (g:LogicGate {name: $gname, system: $sname, endpoint: $ep_name})
                SET g.type = $type, g.category = $cat, g.stop_on_fail = $stop, g.expression = $expr, g.scope = $scope
                MERGE (e)-[rel:ENFORCES {rank: $rank}]->(g)
            """, ep_name=ep_name, sname=system_name, gname=g.name, type=g.type, cat=g.category, stop=g.stop_on_fail, rank=g.rank, expr=g.expression, scope=g.scope)
            if g.expression:
                print(f"INGEST DEBUG [AnchorLogic]: Saving {g.name} -> {g.expression}")
            
            if g.error_code or g.error_msg:
                error_code = g.error_code if g.error_code else f"ERR_{g.name.upper()}"
                tx.run("""
                    MATCH (g:LogicGate {name: $gname, system: $sname, endpoint: $ep_name})
                    MERGE (err:Error {code: $code, system: $sname, endpoint: $ep_name})
                    SET err.msg = $msg
                    MERGE (g)-[:ON_FAIL_THROWS]->(err)
                """, gname=g.name, sname=system_name, ep_name=ep_name, code=error_code, msg=g.error_msg)

    def _create_endpoints_inst(self, tx, system_name, data: EndpointsList):
        for ep in data.endpoints:
            # Identity & Path
            tx.run("""
                MERGE (e:Endpoint {name: $name, system: $sname})
                SET e.method = $method, e.feature = $feature, e.idempotency = $idemp
                MERGE (m:Method {name: $method})
                MERGE (e)-[:USES_METHOD]->(m)
                MERGE (p:Path {template: $path})
                MERGE (e)-[:AT_PATH]->(p)
                MERGE (c:ConcurrencyModel {name: $concurrency})
                MERGE (e)-[:HAS_CONCURRENCY]->(c)
            """, name=ep.name, sname=system_name, method=ep.method, 
                 feature=ep.feature, idemp=ep.idempotency, path=ep.path, 
                 concurrency=ep.concurrency.value)
            
            # Link to Feature
            tx.run("""
                MATCH (e:Endpoint {name: $ename, system: $sname})
                MATCH (f:Feature {name: $fname, system: $sname})
                MERGE (f)-[:EXPOSES]->(e)
            """, ename=ep.name, sname=system_name, fname=ep.feature)

            # Request Fields
            for f in ep.request_fields:
                tx.run("""
                    MATCH (e:Endpoint {name: $ename, system: $sname})
                    MERGE (field:Field {name: $fname, context: 'request', owner: $ename, system: $sname})
                    SET field.type = $type, field.location = $loc, field.required = $req, 
                        field.faker_provider = $faker, field.min = $min, field.max = $max
                    MERGE (e)-[:ACCEPTS]->(field)
                """, ename=ep.name, sname=system_name, fname=f.name, type=f.type, 
                     loc=f.location, req=f.required, faker=f.faker_provider,
                     min=f.min, max=f.max)
                
                # Type Linking
                tx.run("""
                    MATCH (field:Field {name: $fname, context: 'request', owner: $ename, system: $sname})
                    OPTIONAL MATCH (p:Primitive {name: $type})
                    OPTIONAL MATCH (enum:Enum {name: $type, system: $sname})
                    WITH field, p, enum
                    FOREACH (x IN CASE WHEN p IS NOT NULL THEN [p] ELSE [] END | MERGE (field)-[:OF_TYPE]->(p))
                    FOREACH (x IN CASE WHEN enum IS NOT NULL THEN [enum] ELSE [] END | MERGE (field)-[:OF_TYPE]->(enum))
                """, fname=f.name, type=f.type, ename=ep.name, sname=system_name)

            # Response Fields
            for f in ep.response_fields:
                tx.run("""
                    MATCH (e:Endpoint {name: $ename, system: $sname})
                    MERGE (field:Field {name: $fname, context: 'response', owner: $ename, system: $sname})
                    SET field.type = $type, field.is_dynamic = $is_dyn
                    MERGE (e)-[:RETURNS]->(field)
                """, ename=ep.name, sname=system_name, fname=f.name, type=f.type, is_dyn=f.is_dynamic)

            # Validation Sequence (LogicGates) - Unique per Endpoint
            self._create_logic_gates(tx, ep.validation_sequence, ep.name, system_name)

    def _metadata_driven_linking(self, tx, data: EndpointsList):
        # We need the system name here, but EndpointsList doesn't have it.
        # However, _create_endpoints_inst already linked them.
        # Let's use the endpoint names as provided.
        for ep in data.endpoints:
            # State Transitions
            for state in ep.post_state:
                tx.run("""
                    MATCH (e:Endpoint {name: $ep_name})
                    MERGE (s:StateVector {entity: $ent, property: $prop, value: $val})
                    MERGE (e)-[:TRANSITIONS_TO]->(s)
                """, ep_name=ep.name, ent=state.entity, prop=state.property, val=state.value)

            # State Requirements
            for state in ep.pre_state:
                tx.run("""
                    MATCH (e:Endpoint {name: $ep_name})
                    MERGE (s:StateVector {entity: $ent, property: $prop, value: $val})
                    MERGE (e)-[:REQUIRES_STATE]->(s)
                """, ep_name=ep.name, ent=state.entity, prop=state.property, val=state.value)

            # Oracle
            if ep.oracle:
                tx.run("""
                    MATCH (e:Endpoint {name: $ep_name})
                    MERGE (o:Oracle {sql_id: $sql_id})
                    SET o.description = $desc, o.timeout_ms = $timeout
                    MERGE (e)-[:VERIFIED_BY]->(o)
                """, ep_name=ep.name, sql_id=ep.oracle.sql_id, 
                     desc=ep.oracle.description, timeout=ep.oracle.timeout_ms)

    def _create_logic_and_scenarios_inst(self, tx, system_name, data: LogicInfo):
        for scene in data.scenarios:
            tx.run("MERGE (s:Scenario {name: $name, system: $sname})", name=scene.name, sname=system_name)
            if scene.endpoint_name:
                tx.run("""
                    MATCH (s:Scenario {name: $sname, system: $sys})
                    MATCH (e:Endpoint {name: $ename, system: $sys})
                    MERGE (s)-[:COVERS_ENDPOINT]->(e)
                """, sname=scene.name, sys=system_name, ename=scene.endpoint_name)

    def _create_test_templates_inst(self, tx, data: LogicInfo):
        for tt in data.test_templates:
            tx.run("MERGE (t:TestTemplate {name: $name}) SET t.severity = $sev", 
                   name=tt.name, sev=tt.severity)
            for step_data in tt.sequence:
                tx.run("""
                    MATCH (t:TestTemplate {name: $t_name})
                    MATCH (e:Endpoint {name: $e_name})
                    MERGE (t)-[:EXECUTES_SEQUENCE {step: $step}]->(e)
                """, t_name=tt.name, e_name=step_data.endpoint_name, step=step_data.step)

    def _create_metrics_and_sql_inst(self, tx, data: LogicInfo):
        for metric in data.metrics:
            tx.run("MERGE (m:Metric {name: $name})", name=metric.name)
            for q in metric.sql_queries:
                tx.run("""
                    MATCH (m:Metric {name: $mname})
                    MERGE (q:SQLQuery {query: $sql_query})
                    MERGE (m)-[:CALCULATED_BY]->(q)
                """, mname=metric.name, sql_query=q)

if __name__ == "__main__":
    # Integration test would be here if needed
    pass
