import os
import json
from typing import Type, TypeVar
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import instructor

load_dotenv()

T = TypeVar("T", bound=BaseModel)

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("CEREBRAS_API_KEY")
        self.base_url = "https://api.cerebras.ai/v1"
        self.model = "qwen-3-235b-a22b-instruct-2507" 
        self.client = instructor.patch(OpenAI(base_url=self.base_url, api_key=self.api_key))

    def extract(self, prompt: str, schema: Type[T], text: str) -> T:
        full_prompt = f"DOCUMENT TEXT:\n\n{text}\n\nTASK:\n{prompt}"
        return self.client.chat.completions.create(
            model=self.model,
            response_model=schema,
            messages=[
                {"role": "system", "content": "You are a precise data extractor. Your goal is to output valid JSON."},
                {"role": "user", "content": full_prompt}
            ],
            max_retries=3
        )

def extract_api_info(text: str):
    from schema import SystemInfo, EndpointsList, LogicInfo
    client = LLMClient()
    
    print("Stage 1: Global Discovery (Systems, Features, Entities, Enums & Envelopes)...")
    system_info = client.extract(
        """Extract high-level system information, features, and entities. 
        NEW REQUIREMENTS:
        1. Global Enums: Extract all named enums (e.g. System_State, Weather_Condition) into the global_enums list.
        2. Envelopes: Extract the standard Success/Error response structures into the envelopes list.
        3. Entity Fields: For every field, capture name, type, required, min/max, regex, and faker_provider. 
           - Assign a specific faker_provider (e.g. 'name', 'iban', 'email', 'date_of_birth').
           - provide example_valid and example_invalid samples.""",
        SystemInfo,
        text
    )
    
    print("Stage 2: Endpoint Details (The Technical Core)...")
    endpoints = client.extract(
        """Extract all API endpoints. For each endpoint, you MUST capture:
        1. Concurrency: Explicitly map to 'Parallelizable', 'Row-level lock', 'Global system lock', or 'Optimistic concurrency' based on the document.
        2. Validation Priority: Extract the 'Validation Order' or 'Validation Priority' list as an array of strings.
        3. Idempotency: Label as 'Idempotent' or 'Non-Idempotent'.
        4. Field Locations: Specify location as 'body', 'path', 'query', or 'header'.
        5. State Vectors: Define pre_state and post_state accurately.
        6. Validation & Integrity Sequence: List ranked LogicGates with error_code, error_msg, 'expression', and 'scope'.
           - SCOPE: Label as 'INPUT' (for request guards/pre-conditions) or 'OUTPUT' (for response/state integrity/post-conditions).
           - NAME: Use specific, unique names for each gate (e.g. 'AuthCheck', 'SchemaValidation', 'FieldConstraints', 'BusinessRules', 'LocationExists', 'CrossFieldRule', 'ResponseStructure', 'ResponseIntegrity').
           - ERROR_CODE: Use these STANDARD codes if not specified:
             - AuthCheck: 'AUTH_FAILED'
             - SchemaValidation: 'INVALID_SCHEMA'
             - FieldConstraints: 'INVALID_SCHEMA'
             - BusinessRules: 'DATE_OUT_OF_RANGE'
             - LocationExists: 'INVALID_LOCATION'
           - ERROR_MSG: MANDATORY: Pick up messages DIRECTLY from the design document.
             - If the document DOES NOT specify an error message for a gate, leave 'error_msg' as an EMPTY STRING "".
             - DO NOT hallucinate or provide defaults.
           - TRANSLATE them into 'expression' using AnchorLogic v2.1 Syntax:
             - Path: Use 'data.field', 'error.code', or 'response.data[0].field'.
             - Logical: 'AND', 'OR', 'NOT'.
             - Comparison: '==', '!=', '<', '>', '<=', '>='.
             - Quantifiers: 'ALL(collection)(item.field == value)' or 'ANY(collection)(item.field > 0)'.
             - Presence: 'present(field)' or 'HAS(field)'.
             - String: 'field.length >= 2'.
        7. Field Constraints: For EVERY field, capture 'min' and 'max' if mentioned in text (e.g. 'humidity: 0 to 100', 'name: 3-100 chars').
        7. Oracle: Include sql_id and description for all mutations.
        
        CRITICAL RECOGNITION RULE:
        Every field listed in 'Response Fields' or appearing in a 'Success Payload' example, you MUST mark it as 'required: True'. You are only allowed to set 'required: False' if the document explicitly uses the words 'optional', 'nullable', or 'Required: False' for that specific response field. RESPONSE DATA DEFAULTS TO REQUIRED. Query/Path params follow document-specific rules.""",
        EndpointsList,
        text
    )
    for ep in endpoints.endpoints:
        for gate in ep.validation_sequence:
            if gate.expression:
                print(f"DEBUG [AnchorLogic]: {ep.name} -> {gate.name}: {gate.expression}")
    
    print("Stage 3: Logic, Scenarios, & Templates...")
    logic = client.extract(
        """Extract test scenarios and test templates. 
        Ensure Test Templates have a strictly continuous sequence starting at Step 1.""",
        LogicInfo,
        text
    )
    
    return system_info, endpoints, logic
