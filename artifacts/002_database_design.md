# 002 — Database Design

## What Was Built
Complete database schema using SQLAlchemy ORM with SQLite backend.

## Schema

### Entity Relationship
```
Document (1) ──→ (N) DocumentVersion (1) ──→ (N) Node
                                                   ↑
Selection (1) ──→ (N) SelectionItem ──────────────┘
```

### Tables

#### `documents`
| Column | Type | Notes |
|---|---|---|
| id | UUID (string) | Primary key |
| name | string | Unique — used for version matching |
| created_at | datetime | UTC |

#### `document_versions`
| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| document_id | FK → documents | |
| version_number | int | Auto-incremented per document |
| file_hash | string | SHA-256 of PDF file — prevents duplicate ingestion |
| filename | string | Original filename |
| ingested_at | datetime | UTC |

#### `nodes`
| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key — distinct even for duplicate headings |
| version_id | FK → document_versions | |
| heading | string | Section title |
| level | int | 0=root, 1=top-section, 2=subsection, etc. |
| body_text | text | Full text content of the node |
| content_hash | string | SHA-256 of normalized body text |
| parent_id | FK → nodes (self) | NULL for top-level nodes |
| position | int | Ordering within siblings |
| node_path | string | e.g., '1.2.3' for hierarchy queries |
| matched_node_id | string (nullable) | Cross-version node matching |
| has_changed | bool | True if content differs from matched node |

#### `selections` + `selection_items`
Version-pinned references to specific node content.

## Design Decisions

### Why UUID for node IDs?
- Duplicate headings MUST produce distinct node IDs (assignment requirement)
- Auto-increment integers would work but UUIDs are more robust for cross-version references

### Why SHA-256 for content hashing?
- Deterministic: same content always produces same hash
- Collision-resistant: effectively zero false matches
- Normalized before hashing (lowercase, collapsed whitespace) to avoid false staleness from formatting changes

### Why `node_path` column?
- Enables efficient hierarchy queries without recursive joins
- Pattern matching: `WHERE node_path LIKE '1.2.%'` gets all descendants of section 1.2
- Reconstructable from the tree but stored for query performance

### Why `content_hash_at_selection` in SelectionItem?
- This is the staleness detection anchor
- At retrieval time: compare stored hash vs current node's hash
- If different → content changed since test cases were generated → STALE

## Known Limitations
- SQLite doesn't support true UUID type — stored as strings
- No database migrations (would use Alembic in production)
- Self-referential FK on nodes requires careful deletion order
