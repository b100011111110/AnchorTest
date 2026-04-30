from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import Enum

# --- Stage 1: Global Discovery ---

class ConcurrencyModel(str, Enum):
    PARALLEL = "Parallelizable"
    ROW_LOCK = "Row-level lock"
    GLOBAL_LOCK = "Global system lock"
    OPTIMISTIC = "Optimistic concurrency"

class GlobalConstraint(BaseModel):
    name: str
    logic: str
    description: str

class GlobalEnum(BaseModel):
    name: str
    values: List[str]
    description: Optional[str] = None

class EnvelopeField(BaseModel):
    name: str
    type: str
    required: bool
    description: Optional[str] = None

class Envelope(BaseModel):
    name: str
    fields: List[EnvelopeField]

class EntityField(BaseModel):
    name: str
    type: str # Int, Float, String, Bool, Date
    required: bool
    min: Optional[Any] = None
    max: Optional[Any] = None
    regex: Optional[str] = None
    enum: Optional[List[str]] = None
    description: Optional[str] = None
    # Generator Hints
    faker_provider: Optional[str] = None
    example_valid: Optional[Any] = None
    example_invalid: List[Any] = []
    is_pii: bool = False
    dependency_ref: Optional[str] = None

class Entity(BaseModel):
    name: str
    fields: List[EntityField]
    description: Optional[str] = None

class Feature(BaseModel):
    name: str
    description: str

class SystemInfo(BaseModel):
    name: str
    version: str
    description: str
    features: List[Feature]
    entities: List[Entity]
    global_constraints: List[GlobalConstraint]
    global_enums: List[GlobalEnum] = []
    envelopes: List[Envelope] = []

# --- Stage 2: Endpoint Details ---

class FieldLocation(str, Enum):
    BODY = "body"
    PATH = "path"
    QUERY = "query"
    HEADER = "header"

class EndpointField(BaseModel):
    name: str
    type: str
    required: bool
    location: FieldLocation
    min: Optional[Any] = None
    max: Optional[Any] = None
    regex: Optional[str] = None
    enum: Optional[List[str]] = None
    description: Optional[str] = None
    # Generator Hints
    faker_provider: Optional[str] = None
    example_valid: Optional[Any] = None
    example_invalid: List[Any] = []
    is_pii: bool = False
    is_dynamic: bool = False
    dependency_ref: Optional[str] = None

class LogicGate(BaseModel):
    name: str
    type: str # "Identity", "Format", "Logic"
    category: str # "Auth", "Schema", "Business", "System"
    scope: str = "INPUT" # "INPUT" or "OUTPUT"
    rank: int
    stop_on_fail: bool = True
    error_code: Optional[Union[int, str]] = None
    error_msg: Optional[str] = None
    expression: str = "" # AnchorLogic DSL

class StateVector(BaseModel):
    entity: str
    property: str
    value: str
    comparison_operator: str = "eq" # eq, gt, lt, contains, regex_match
    persistence_layer: str = "SQL"

class Oracle(BaseModel):
    sql_id: str
    description: str
    timeout_ms: int = 500
    teardown_id: Optional[str] = None

class Endpoint(BaseModel):
    name: str
    method: str
    path: str
    feature: str
    description: str
    idempotency: str
    concurrency: ConcurrencyModel = ConcurrencyModel.PARALLEL
    auth_scope: Optional[str] = None
    request_fields: List[EndpointField]
    response_fields: List[EndpointField]
    validation_sequence: List[LogicGate]
    validation_priority_order: List[str] = [] # e.g. ["Auth", "Schema", "Business"]
    pre_state: List[StateVector]
    post_state: List[StateVector]
    oracle: Optional[Oracle] = None

class EndpointsList(BaseModel):
    endpoints: List[Endpoint]

# --- Stage 3: Scenarios & Logic ---

class Scenario(BaseModel):
    name: str
    type: str # "SUCCESS", "ERROR"
    endpoint_name: str
    status_code: int
    error_code: Optional[str] = None
    description: str
    request_payload: Optional[str] = None # JSON string
    response_payload: Optional[str] = None # JSON string
    pre_conditions: List[str]
    post_conditions: List[str]

class TestTemplateStep(BaseModel):
    step: int
    endpoint_name: str

class TestTemplate(BaseModel):
    name: str
    severity: str # "Critical", "High", "Medium", "Low"
    description: str
    sequence: List[TestTemplateStep]

class PersistenceQuery(BaseModel):
    endpoint_name: str
    query: str
    description: str

class Metric(BaseModel):
    name: str
    type: str
    description: str
    associated_features: List[str]
    sql_queries: List[str] = []

class LogicInfo(BaseModel):
    scenarios: List[Scenario]
    test_templates: List[TestTemplate]
    persistence_queries: List[PersistenceQuery]
    metrics: List[Metric]
