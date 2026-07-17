"""Hierarchy reconstruction — builds a proper document tree from flat sections.

Handles edge cases:
- Duplicate headings (same title, different numbers) → distinct nodes
- Skipped levels (e.g., 2.1 → 2.1.1.1, no 2.1.1) → creates with correct parent
- Out-of-order sections (e.g., 3.4 before 3.3) → preserves document order, not numerical order
- Unnumbered headings → attached to nearest parent
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Optional

from backend.parser.extractor import RawSection, RawHeading


@dataclass
class TreeNode:
    """A node in the document hierarchy tree."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    heading: str = ""
    number: str = ""        # e.g., '2.1.1.1'
    level: int = 0          # depth in hierarchy
    body_text: str = ""
    content_hash: str = ""
    node_path: str = ""     # e.g., '2.1.1.1'
    parent_id: Optional[str] = None
    position: int = 0       # order among siblings
    children: list["TreeNode"] = field(default_factory=list)
    tables_text: str = ""   # Serialized table content

    @property
    def full_text(self) -> str:
        """Body text + table text combined."""
        parts = [self.body_text]
        if self.tables_text:
            parts.append(self.tables_text)
        return "\n".join(p for p in parts if p)


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of normalized text.
    
    Normalization:
    - Lowercase
    - Collapse whitespace
    - Strip leading/trailing whitespace
    
    This prevents false staleness from formatting-only changes.
    """
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_hierarchy(sections: list[RawSection], title_lines: list[str] = None) -> list[TreeNode]:
    """Build a hierarchical tree from flat sections.
    
    Algorithm:
    1. Create a virtual root node (level 0) to hold top-level sections
    2. Process sections in document order (NOT numerical order)
    3. For each section, find its parent using a stack-based approach:
       - The parent is the most recent ancestor with a lower level
    4. Handle skipped levels by finding the closest valid parent
    
    Returns: List of top-level TreeNode objects (children of the virtual root)
    
    Edge cases handled:
    - Duplicate headings: Each gets a unique UUID, distinct position
    - Skipped levels (2.1 → 2.1.1.1): Parent is 2.1 (closest lower level)
    - Out-of-order (3.4 before 3.3): Preserved in document order
    """
    if not sections:
        return []
    
    # Stack tracks the current path in the tree: [(level, TreeNode), ...]
    # This enables O(1) parent lookup for properly nested sections
    top_level_nodes = []
    
    # Stack: list of (level, node) tuples representing current ancestry path
    stack: list[tuple[int, TreeNode]] = []
    
    # Track sibling positions per parent
    sibling_counts: dict[Optional[str], int] = {}  # parent_id → count
    
    for section in sections:
        heading = section.heading
        
        # Build body text including tables
        body_parts = [section.body_text]
        for table in section.tables:
            table_text = table.to_text()
            if table_text:
                body_parts.append(f"\n[TABLE]\n{table_text}\n[/TABLE]")
        
        full_body = "\n".join(p for p in body_parts if p)
        content_hash = compute_content_hash(full_body)
        
        node = TreeNode(
            heading=f"{heading.number}. {heading.title}" if heading.number else heading.title,
            number=heading.number,
            level=heading.level,
            body_text=section.body_text,
            content_hash=content_hash,
            node_path=heading.number,
            tables_text="\n".join(t.to_text() for t in section.tables),
        )
        
        # Find parent: pop stack until we find a node with lower level
        while stack and stack[-1][0] >= heading.level:
            stack.pop()
        
        if stack:
            # Parent is the top of the stack
            parent_level, parent_node = stack[-1]
            node.parent_id = parent_node.id
            
            # Set position among siblings
            parent_key = parent_node.id
            sibling_counts[parent_key] = sibling_counts.get(parent_key, 0) + 1
            node.position = sibling_counts[parent_key] - 1
            
            parent_node.children.append(node)
        else:
            # Top-level node (level 1)
            node.parent_id = None
            top_key = None
            sibling_counts[top_key] = sibling_counts.get(top_key, 0) + 1
            node.position = sibling_counts[top_key] - 1
            top_level_nodes.append(node)
        
        # Push this node onto the stack
        stack.append((heading.level, node))
    
    return top_level_nodes


def flatten_tree(nodes: list[TreeNode]) -> list[TreeNode]:
    """Flatten a tree into a list (pre-order traversal).
    
    Useful for database insertion and iteration.
    """
    result = []
    
    def _traverse(node_list: list[TreeNode]):
        for node in node_list:
            result.append(node)
            if node.children:
                _traverse(node.children)
    
    _traverse(nodes)
    return result


def print_tree(nodes: list[TreeNode], indent: int = 0):
    """Debug utility — print tree structure."""
    for node in nodes:
        prefix = "  " * indent
        print(f"{prefix}[{node.node_path}] {node.heading} (hash={node.content_hash[:8]}..., children={len(node.children)})")
        if node.children:
            print_tree(node.children, indent + 1)
