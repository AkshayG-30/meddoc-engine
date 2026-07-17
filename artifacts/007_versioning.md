# 007 — Document Versioning

## What Was Built
Version management system with cross-version node matching using composite similarity scoring.

## Versioning Flow
```
Ingest v1 → Create Document + Version 1 → Parse → Store nodes
Ingest v2 (same name) → Create Version 2 → Parse → Store nodes → Match with v1 nodes
```

## Node Matching Strategy
Composite score: `title_similarity(0.4) + parent_path_similarity(0.3) + content_hash_match(0.3)`
- **Title similarity**: `difflib.SequenceMatcher` ratio on heading text (0.0–1.0)
- **Parent path similarity**: Structural position match (e.g., '2.1' vs '2.1' = 1.0)
- **Content hash match**: 1.0 if SHA-256 hashes are identical, 0.0 otherwise
- **Threshold**: Score ≥ 0.6 → same logical node

## Known Failure Mode
If a heading changes completely (e.g., "Battery Life" → "Power Duration") but the body text stays identical:
- Title similarity ≈ 0.0 (weight 0.4) → contributes 0.0
- Path similarity could be 1.0 (weight 0.3) → contributes 0.3
- Content hash = 1.0 (weight 0.3) → contributes 0.3
- Total = 0.6 — right at threshold, may or may not match

This is documented and defensible: heading identity matters for traceability.

## Design Decisions
- Greedy matching (best score wins) rather than optimal assignment — simpler, sufficient for this document
- File hash prevents duplicate ingestion of the same PDF
- Version numbers auto-increment per document
