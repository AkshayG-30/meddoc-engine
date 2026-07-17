# 016 — Generation Retrieval API

## What Was Built
API endpoints for fetching generated test cases with live staleness checks.

## Endpoints
| Method | Path | Description |
|---|---|---|
| GET | `/api/generations?selection_id=...` | By selection |
| GET | `/api/generations?node_id=...` | By source node |
| GET | `/api/generations/{id}` | Specific generation |

## Staleness Is Visible
Every retrieval response includes:
- `staleness_status`: Overall status (CURRENT/STALE/PARTIALLY_STALE/ORPHANED)
- `stale_nodes`: Per-node breakdown with status and hash comparison

This satisfies the assignment requirement: "a correct staleness check nobody can query for is not a finished feature."
