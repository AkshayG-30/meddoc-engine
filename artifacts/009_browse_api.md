# 009 — Browse API

## What Was Built
RESTful browse API for navigating the document tree.

## Endpoints
| Method | Path | Description |
|---|---|---|
| GET | `/api/documents` | List all documents |
| POST | `/api/documents/ingest` | Ingest PDF (creates/updates version) |
| GET | `/api/documents/{id}/versions` | List versions |
| GET | `/api/documents/{id}/tree?version=N` | Tree view (default: latest) |
| GET | `/api/nodes/{id}` | Node detail with children, text, hash |
| GET | `/api/nodes/{id}/diff?from_version=1&to_version=2` | Cross-version diff |

## Design Decisions
- Tree endpoint returns nested structure (not flat) for easy UI consumption
- Version parameter defaults to latest — most common use case
- Node detail includes `matched_node_id` and `has_changed` for version tracking
