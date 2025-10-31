from __future__ import annotations

import json
from typing import Dict, Any, List


def load_data_json(data_json_path: str) -> Dict[str, Any]:
    """Load the full data JSON file."""
    with open(data_json_path, "r") as f:
        return json.load(f)


def extract_data_array(data: Dict[str, Any], data_source: str) -> List[Dict[str, Any]]:
    """
    Extract the actual data array from JSON structure.
    
    Expected structure:
    {
        "answer": "...",
        "metrics": {
            "monthly_data": [...],  or "channel_breakdown": [...]
        }
    }
    
    The data_source (e.g., "total_sales_over_time.json") is used to infer the key.
    """
    metrics = data.get("metrics", {})
    
    # Try common keys
    for key in ["monthly_data", "channel_breakdown", "data"]:
        if key in metrics:
            return metrics[key]
    
    # If no standard key, try to find any list in metrics
    for key, value in metrics.items():
        if isinstance(value, list):
            return value
    
    raise ValueError(f"Could not find data array in metrics for {data_source}")


def get_data_json_path_from_schema(schema_json_path: str) -> str:
    """
    Extract the data JSON file path from the schema file.
    The schema JSON has the data file name as the top-level key.
    """
    with open(schema_json_path, "r") as f:
        schema = json.load(f)
    
    # The top-level key is the data JSON filename
    data_file = list(schema.keys())[0]
    
    # Construct path relative to schema file location
    import os
    schema_dir = os.path.dirname(os.path.abspath(schema_json_path))
    data_path = os.path.join(schema_dir, data_file)
    
    return data_path


def extract_currency_from_answer(data: Dict[str, Any]) -> str | None:
    """
    Extract currency unit from the 'answer' field in data JSON.
    Looks for currency symbols like $, €, £, ¥ or currency codes.
    
    Returns currency code (e.g., 'USD', 'EUR') or None if not found.
    """
    answer = data.get("answer", "")
    if not answer:
        return None
    
    answer_str = str(answer).upper()
    
    # Check for currency symbols
    if "$" in answer_str or "USD" in answer_str or "DOLLAR" in answer_str:
        return "USD"
    if "€" in answer_str or "EUR" in answer_str or "EURO" in answer_str:
        return "EUR"
    if "£" in answer_str or "GBP" in answer_str or "POUND" in answer_str:
        return "GBP"
    if "¥" in answer_str or "JPY" in answer_str or "YEN" in answer_str:
        return "JPY"
    
    return None

