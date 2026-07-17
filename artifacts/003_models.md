# 003 — ORM Models

## What Was Built
SQLAlchemy ORM models with Pydantic schemas for API validation.

## Models Implemented
- `Document` — logical document entity
- `DocumentVersion` — version snapshot with file hash
- `Node` — hierarchy tree node with content hashing
- `Selection` / `SelectionItem` — version-pinned node selections

## Pydantic Schemas
- Request/response models for all API endpoints
- `TestCaseSchema` — structured LLM output format
- `StalenessResponse` — per-node staleness reporting

## Design Decisions
- Used `from_attributes = True` for seamless ORM → Pydantic conversion
- `Node.compute_content_hash()` normalizes text before hashing (lowercase + whitespace collapse)
- Session factory pattern with FastAPI `Depends()` injection

## Known Limitations
- No async session support (synchronous SQLite is sufficient for this scale)
- No Alembic migrations — schema changes require table recreation
