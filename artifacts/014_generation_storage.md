# 014 — Generation Storage (MongoDB)

## What Was Built
MongoDB persistence for LLM-generated QA test cases, linked to selections and node content.

## Collection: `generations`
```json
{
  "selection_id": "uuid",
  "node_ids": ["uuid1", "uuid2"],
  "version_id": "uuid",
  "content_hashes": {"node_id": "sha256_hash"},
  "model": "llama-3.3-70b-versatile",
  "prompt_version": "v1",
  "test_cases": [{ ... }],
  "created_at": "ISO-8601",
  "selection_content_hash": "sha256_hash",
  "raw_response": "full LLM response text"
}
```

## Traceability Chain
```
generation → selection → node+version → content_hash
```
Every test case can be traced back to the exact document text it was generated from.

## Why MongoDB (not SQLite)?
- Generated output is semi-structured (variable number of test cases, variable fields)
- Document-oriented storage is a natural fit
- Assignment explicitly requires a NoSQL store for LLM output
