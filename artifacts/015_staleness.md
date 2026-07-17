# 015 — Staleness Detection

## What Was Built
Impact detection system that checks whether generated test cases still reflect the current document.

## Algorithm
For each node in a generation's source:
1. Find the node in the latest version (via `matched_node_id` or similarity matching)
2. Compare `content_hash` at generation time vs current version
3. Assign status: `CURRENT`, `STALE`, or `ORPHANED`

## Statuses
| Status | Meaning |
|---|---|
| CURRENT | Content hash matches — test case reflects current document |
| STALE | Content hash differs — document changed since generation |
| ORPHANED | Source node no longer exists in the latest version |
| PARTIALLY_STALE | Mix of CURRENT and STALE nodes in a generation |

## When Staleness Is Checked
- **At retrieval time**, not at ingestion time
- Every `GET /api/generations/{id}` and `GET /api/generations?...` includes live staleness check

## Known Limitations
- Any text change = STALE, regardless of significance
- A typo fix is treated the same as a changed safety threshold
- No semantic analysis of what changed
