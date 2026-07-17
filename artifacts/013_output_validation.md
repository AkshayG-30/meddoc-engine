# 013 — Output Validation

## What Was Built
Pydantic-based LLM output validator with JSON extraction from potentially messy responses.

## Validation Pipeline
1. **Extract JSON**: Handle markdown code blocks, raw JSON, explanatory text
2. **Parse JSON**: `json.loads()` with clear error messages
3. **Pydantic validation**: Strict schema check against `LLMTestCaseResponse`

## JSON Extraction Strategy
LLMs sometimes return:
- JSON wrapped in ` ```json ... ``` ` code blocks
- JSON with preamble text
- Pure JSON

The extractor handles all three patterns via regex + brace matching.

## Known Limitations
- No partial parsing — if one test case is malformed, all are rejected
- No format repair (e.g., fixing missing quotes, trailing commas)
- Production would implement: retry → repair → retry → validator → partial parser
