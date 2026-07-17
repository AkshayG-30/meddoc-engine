# 011 — Selection API

## What Was Built
Version-pinned selection system for grouping document nodes.

## How Version Pinning Works
When a selection is created:
1. Each item stores `node_id`, `version_id`, and `content_hash_at_selection`
2. The content hash is a snapshot of the node's text at creation time
3. Even after re-ingestion, the selection resolves to the original text

## Staleness Detection Via Selections
At retrieval time:
- Compare `content_hash_at_selection` with the node's current content hash
- If different → the underlying document changed → test cases may be stale

## Endpoints
| Method | Path | Description |
|---|---|---|
| POST | `/api/selections` | Create named selection with node+version pairs |
| GET | `/api/selections/{id}` | Retrieve selection with resolved text |
