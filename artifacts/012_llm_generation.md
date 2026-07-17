# 012 — LLM Test Generation

## What Was Built
Groq-powered QA test case generation using LLaMA 3.3 70B Versatile.

## Prompt Design
- **System prompt**: Instructs the LLM to act as a medical device QA engineer
- **Output format**: Strict JSON with `{id, title, preconditions, steps[], expected_result, traceability_ref}`
- **Prompt version tracking**: `PROMPT_VERSION = "v1"` — changes trigger new generations

## Duplicate Policy
If `hash(selection_content + model + prompt_version)` matches an existing generation:
→ Return cached result, do not regenerate.

**Rationale**: Same input + same model + same prompt = same output. Regeneration wastes API calls.

## Error Handling
1. Call LLM
2. Validate JSON output with Pydantic
3. If malformed → retry once
4. If still malformed → return error with raw response attached

No repair/partial-parse pipeline. Documented as intentional simplicity trade-off.

## Known Limitations
- No streaming — full response required for validation
- Single retry — production would use exponential backoff
- No rate limiting on the API side
