"""Parser validation tests.

Tests targeting the specific edge cases in the CT-200 document:
1. Duplicate headings produce distinct node IDs with correct parents
2. Skipped heading levels maintain correct parent assignment
3. Out-of-order sections are preserved in document order
4. Content hash determinism
5. Table extraction association
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.parser.extractor import extract_from_pdf, RawSection, RawHeading
from backend.parser.hierarchy import build_hierarchy, flatten_tree, compute_content_hash, TreeNode


# ─── Fixtures ───

PDF_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "ct200_manual.pdf")


@pytest.fixture(scope="module")
def parsed_data():
    """Parse the CT-200 PDF once for all tests."""
    sections, title_lines = extract_from_pdf(PDF_PATH)
    tree = build_hierarchy(sections, title_lines)
    flat = flatten_tree(tree)
    return {
        "sections": sections,
        "title_lines": title_lines,
        "tree": tree,
        "flat": flat,
    }


# ─── Test 1: Duplicate Headings ───

def test_duplicate_headings_produce_distinct_nodes(parsed_data):
    """Test that 'Error Codes' appears twice with distinct IDs and correct parents.
    
    The document has:
    - 4.2 Error Codes (under section 4)
    - 7.1 Error Codes (under section 7)
    
    Both must exist as separate nodes with unique IDs.
    """
    flat = parsed_data["flat"]
    
    # Find all nodes with "Error Codes" in the heading
    error_code_nodes = [n for n in flat if "Error Codes" in n.heading]
    
    # Must have exactly 2
    assert len(error_code_nodes) == 2, f"Expected 2 'Error Codes' nodes, got {len(error_code_nodes)}"
    
    # Must have distinct IDs
    ids = [n.id for n in error_code_nodes]
    assert ids[0] != ids[1], "Duplicate heading nodes must have distinct IDs"
    
    # Must have different parents
    parent_ids = [n.parent_id for n in error_code_nodes]
    assert parent_ids[0] != parent_ids[1], "Duplicate heading nodes must have different parents"
    
    # Verify correct parent assignment
    node_42 = [n for n in error_code_nodes if "4.2" in n.node_path][0]
    node_71 = [n for n in error_code_nodes if "7.1" in n.node_path][0]
    
    # 4.2 should be under section 4
    parent_4 = [n for n in flat if n.node_path == "4"][0]
    assert node_42.parent_id == parent_4.id, "4.2 Error Codes should be under section 4"
    
    # 7.1 should be under section 7
    parent_7 = [n for n in flat if n.node_path == "7"][0]
    assert node_71.parent_id == parent_7.id, "7.1 Error Codes should be under section 7"


# ─── Test 2: Skipped Heading Levels ───

def test_skipped_levels_correct_parent(parsed_data):
    """Test that 2.1.1.1 (level 4) is correctly parented under 2.1 (level 2).
    
    The document jumps from 2.1 (level 2) to 2.1.1.1 (level 4) with no
    2.1.1 (level 3) in between. The parser must still correctly identify
    2.1 as the parent.
    """
    flat = parsed_data["flat"]
    
    # Find 2.1.1.1
    node_2111 = [n for n in flat if n.node_path == "2.1.1.1"]
    assert len(node_2111) == 1, "Node 2.1.1.1 must exist"
    node_2111 = node_2111[0]
    
    # Find 2.1
    node_21 = [n for n in flat if n.node_path == "2.1"]
    assert len(node_21) == 1, "Node 2.1 must exist"
    node_21 = node_21[0]
    
    # 2.1.1.1 should be a child of 2.1
    assert node_2111.parent_id == node_21.id, (
        f"Node 2.1.1.1 should be parented under 2.1, "
        f"but parent_id={node_2111.parent_id}, expected={node_21.id}"
    )
    
    # Verify level
    assert node_2111.level == 4, f"Node 2.1.1.1 should be level 4, got {node_2111.level}"


# ─── Test 3: Out-of-Order Sections ───

def test_out_of_order_sections_preserved(parsed_data):
    """Test that section 3.4 appears before 3.3 in the tree (document order).
    
    The PDF has 3.4 'Auto Shutoff' before 3.3 'Result Display'. Our parser
    preserves document order, not numerical order.
    """
    flat = parsed_data["flat"]
    tree = parsed_data["tree"]
    
    # Find section 3's children
    section_3 = [n for n in tree if n.node_path == "3"][0]
    child_paths = [c.node_path for c in section_3.children]
    
    # 3.4 should come before 3.3
    idx_34 = child_paths.index("3.4")
    idx_33 = child_paths.index("3.3")
    assert idx_34 < idx_33, (
        f"Section 3.4 should appear before 3.3 (document order). "
        f"Got 3.4 at index {idx_34}, 3.3 at index {idx_33}"
    )
    
    # Both should be children of section 3
    node_34 = [n for n in flat if n.node_path == "3.4"][0]
    node_33 = [n for n in flat if n.node_path == "3.3"][0]
    assert node_34.parent_id == section_3.id
    assert node_33.parent_id == section_3.id


# ─── Test 4: Content Hash Determinism ───

def test_content_hash_determinism():
    """Test that the same content always produces the same hash.
    
    Also tests that minor whitespace changes don't produce different hashes
    (normalization).
    """
    text1 = "The device measures blood pressure."
    text2 = "The device measures blood pressure."
    text3 = "The  device   measures blood  pressure."  # extra whitespace
    text4 = "THE DEVICE MEASURES BLOOD PRESSURE."  # different case
    
    hash1 = compute_content_hash(text1)
    hash2 = compute_content_hash(text2)
    hash3 = compute_content_hash(text3)
    hash4 = compute_content_hash(text4)
    
    # Same text → same hash
    assert hash1 == hash2, "Identical text must produce identical hashes"
    
    # Whitespace normalization → same hash
    assert hash1 == hash3, "Whitespace differences should be normalized away"
    
    # Case normalization → same hash
    assert hash1 == hash4, "Case differences should be normalized away"
    
    # Different text → different hash
    different_hash = compute_content_hash("A completely different sentence.")
    assert hash1 != different_hash, "Different text must produce different hashes"


# ─── Test 5: Complete Tree Structure ───

def test_complete_tree_structure(parsed_data):
    """Test that the full tree has the expected structure."""
    tree = parsed_data["tree"]
    flat = parsed_data["flat"]
    
    # Should have 8 top-level sections
    assert len(tree) == 8, f"Expected 8 top-level sections, got {len(tree)}"
    
    # Should have 27 total nodes
    assert len(flat) == 27, f"Expected 27 total nodes, got {len(flat)}"
    
    # Top-level sections should be numbered 1-8
    top_paths = [n.node_path for n in tree]
    assert top_paths == ["1", "2", "3", "4", "5", "6", "7", "8"], (
        f"Expected sections 1-8, got {top_paths}"
    )
    
    # Every node should have a non-empty content hash
    for node in flat:
        assert node.content_hash, f"Node {node.node_path} has empty content hash"
        assert len(node.content_hash) == 64, f"Content hash should be SHA-256 (64 chars)"


# ─── Test 6: Title Extraction ───

def test_title_extraction(parsed_data):
    """Test that the document title is correctly extracted."""
    title = " ".join(parsed_data["title_lines"])
    assert "CardioTrack" in title, "Title should contain 'CardioTrack'"
    assert "CT-200" in title, "Title should contain 'CT-200'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
