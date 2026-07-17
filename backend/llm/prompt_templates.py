"""Versioned prompt templates for QA test case generation.

Prompt version is tracked so that if the prompt changes, we know which
prompt version generated which test cases. This is important for
the duplicate selection policy.
"""

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You are a QA engineer specializing in medical device testing. 
You generate precise, actionable test cases from technical documentation.

IMPORTANT: You MUST respond with ONLY valid JSON. No markdown, no explanations, no code blocks.
Return a JSON object with this exact structure:

{
  "test_cases": [
    {
      "id": "TC-001",
      "title": "Brief descriptive title",
      "preconditions": "What must be true before the test",
      "steps": ["Step 1", "Step 2", "Step 3"],
      "expected_result": "What should happen",
      "traceability_ref": "Section reference from the source document"
    }
  ]
}

Generate 3-5 test cases that:
- Are concrete and executable by a tester
- Cover both normal operation and edge cases
- Reference specific values, thresholds, or behaviors from the document
- Include the source section number in traceability_ref
"""

USER_PROMPT_TEMPLATE = """Based on the following document sections, generate QA test cases.

{section_content}

Generate 3-5 test cases as specified. Return ONLY valid JSON."""
