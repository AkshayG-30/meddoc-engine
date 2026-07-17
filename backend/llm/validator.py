"""LLM output validator — validates structured JSON output from the LLM.

Uses Pydantic for strict validation of the LLM response.
Error handling: retry once on malformed output, then fail with raw response attached.

KNOWN LIMITATION: No repair pipeline. If the LLM returns malformed JSON twice,
we fail rather than attempting partial parsing or format repair. This is a
deliberate simplicity trade-off — a production system would implement
retry → repair → retry → validator → partial parser.
"""

import json
import re
from typing import Optional

from pydantic import BaseModel, ValidationError

from backend.database.schemas import TestCaseSchema


class LLMTestCaseResponse(BaseModel):
    """Expected structure of the LLM's JSON response."""
    test_cases: list[TestCaseSchema]


def extract_json_from_response(raw: str) -> Optional[str]:
    """Try to extract JSON from LLM response, handling common issues.
    
    The LLM sometimes wraps JSON in markdown code blocks or adds
    explanatory text before/after the JSON.
    """
    # Try to find JSON in code blocks first
    code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if code_block_match:
        return code_block_match.group(1).strip()
    
    # Try to find a JSON object directly
    brace_start = raw.find('{')
    brace_end = raw.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        return raw[brace_start:brace_end + 1]
    
    return None


def validate_llm_output(raw_response: str) -> tuple[Optional[LLMTestCaseResponse], Optional[str]]:
    """Validate LLM output against expected schema.
    
    Returns:
        (parsed_response, error_message)
        - On success: (LLMTestCaseResponse, None)
        - On failure: (None, error_description)
    """
    # Step 1: Extract JSON
    json_str = extract_json_from_response(raw_response)
    if not json_str:
        return None, f"Could not extract JSON from LLM response. Raw: {raw_response[:500]}"
    
    # Step 2: Parse JSON
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}. Extracted: {json_str[:500]}"
    
    # Step 3: Validate with Pydantic
    try:
        parsed = LLMTestCaseResponse(**data)
        return parsed, None
    except ValidationError as e:
        return None, f"Schema validation failed: {e}. Data: {json.dumps(data)[:500]}"
