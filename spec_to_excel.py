import pandas as pd
from llm_utils import extract_api_info
import json
import os

def generate_excel(doc_path, system_name):
    print(f"Reading {doc_path}...")
    with open(doc_path, "r") as f:
        text = f.read()
    
    print(f"Extracting details from {doc_path}...")
    system_info, endpoints_list, logic_info = extract_api_info(text)
    
    # Flatten details for Excel
    rows = []
    
    # Envelopes
    envelopes = system_info.envelopes
    for env in envelopes:
        rows.append({
            "Type": "Envelope",
            "Name": env.name,
            "Details": "",
            "Logic/Structure": json.dumps([f.model_dump() for f in env.fields], indent=2),
            "Error Code": "",
            "Error Message": ""
        })
        
    # Enums
    enums = system_info.global_enums
    for en in enums:
        rows.append({
            "Type": "Enum",
            "Name": en.name,
            "Details": "",
            "Logic/Structure": ", ".join(en.values),
            "Error Code": "",
            "Error Message": ""
        })

    # Endpoints and Gates
    for ep in endpoints_list.endpoints:
        ep_name = f"{ep.method} {ep.path}"
        
        # Add a row for the endpoint itself
        rows.append({
            "Type": "Endpoint",
            "Name": ep_name,
            "Details": f"Feature: {ep.feature}",
            "Logic/Structure": f"Idempotency: {ep.idempotency}",
            "Error Code": "",
            "Error Message": ""
        })
        
        # Gates
        gates = ep.validation_sequence
        for gate in gates:
            rows.append({
                "Type": f"LogicGate ({gate.scope})",
                "Name": gate.name,
                "Details": ep_name,
                "Logic/Structure": gate.expression,
                "Error Code": gate.error_code,
                "Error Message": gate.error_msg
            })
            
    # Scenarios
    for sc in logic_info.scenarios:
        rows.append({
            "Type": f"Scenario ({sc.type})",
            "Name": sc.name,
            "Details": f"{sc.endpoint_name} -> HTTP {sc.status_code}",
            "Logic/Structure": sc.description,
            "Error Code": sc.error_code or "",
            "Error Message": ""
        })
            
    df = pd.DataFrame(rows)
    
    output_path = "API_Spec_Analysis.xlsx"
    print(f"Writing to {output_path}...")
    df.to_excel(output_path, index=False)
    print("Done.")
    return output_path

if __name__ == "__main__":
    doc = "DOCS/weather_v1.txt"
    system = "Weather API"
    generate_excel(doc, system)
