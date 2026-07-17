# 017 — End-to-End Tests

## What Was Built
14 integration tests covering the full application flow.

## Test Classes and Results

### TestDocumentIngestion (4 tests)
| Test | Description | Status |
|---|---|---|
| `test_health_check` | Health endpoint returns 200 | ✅ |
| `test_ingest_v1` | Ingest CT-200 v1 → 27 nodes created | ✅ |
| `test_ingest_v2` | Ingest v2 → version 2 created, node matching runs | ✅ |
| `test_list_versions` | Both v1 and v2 exist | ✅ |
| `test_duplicate_ingestion_blocked` | Same file re-ingested → duplicate status | ✅ |

### TestBrowseAPI (4 tests)
| Test | Description | Status |
|---|---|---|
| `test_get_tree_v1` | Tree for v1 has 8 sections | ✅ |
| `test_get_tree_latest` | Default version is latest (v2) | ✅ |
| `test_get_node_detail` | Node returns heading, hash, children | ✅ |
| `test_node_not_found` | Invalid ID returns 404 | ✅ |

### TestSearchAPI (3 tests)
| Test | Description | Status |
|---|---|---|
| `test_search_by_heading` | "Overpressure" finds results | ✅ |
| `test_search_by_body_text` | "oscillometric" finds results | ✅ |
| `test_search_no_results` | Nonsense query returns 0 results | ✅ |

### TestSelectionAPI (2 tests)
| Test | Description | Status |
|---|---|---|
| `test_create_selection` | Create version-pinned selection | ✅ |
| `test_get_selection` | Retrieve selection with resolved text | ✅ |

## All 14 tests pass in ~1.4 seconds.
