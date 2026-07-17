# 006 — Parser Validation Tests

## What Was Built
6 unit tests targeting specific edge cases in the CT-200 document parser.

## Tests

| # | Test | Target Edge Case | Status |
|---|---|---|---|
| 1 | `test_duplicate_headings_produce_distinct_nodes` | "Error Codes" appears as 4.2 and 7.1 — must produce 2 distinct node IDs with correct parents | ✅ PASS |
| 2 | `test_skipped_levels_correct_parent` | 2.1.1.1 has no 2.1.1 parent — must correctly parent under 2.1 | ✅ PASS |
| 3 | `test_out_of_order_sections_preserved` | 3.4 appears before 3.3 in the PDF — must preserve document order | ✅ PASS |
| 4 | `test_content_hash_determinism` | Same content → same hash; whitespace/case normalized | ✅ PASS |
| 5 | `test_complete_tree_structure` | 8 top-level sections, 27 total nodes, all with valid hashes | ✅ PASS |
| 6 | `test_title_extraction` | Document title correctly extracted from 22pt bold text | ✅ PASS |

## Design Decisions
- Tests run against the real CT-200 PDF, not synthetic fixtures — validates actual edge cases
- Module-scoped fixture parses the PDF once — all tests share the parsed result
- Assertions include descriptive messages for clear failure diagnostics
