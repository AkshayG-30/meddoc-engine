"""Diff engine — computes lightweight text diffs between node versions.

Uses Python's difflib for line-by-line comparison.
Returns insertions, deletions, and modified lines.

KNOWN LIMITATION: This is a purely textual diff. It does not perform
semantic analysis — a one-word wording change is treated identically
to a changed pressure threshold. Numerical requirement changes are not
specially analyzed. This is documented as an intentional trade-off.
"""

import difflib
from backend.database.schemas import DiffResult


def compute_diff(
    old_text: str,
    new_text: str,
    node_id: str = "",
    heading: str = "",
    from_version: int = 0,
    to_version: int = 0,
) -> DiffResult:
    """Compute a lightweight diff between two text versions.
    
    Returns a DiffResult with:
    - changed: whether any difference exists
    - insertions: count of added lines
    - deletions: count of removed lines
    - modified_lines: list of unified diff lines showing changes
    - summary: human-readable summary
    """
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    
    # Generate unified diff
    diff = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"v{from_version}",
        tofile=f"v{to_version}",
        lineterm="",
    ))
    
    insertions = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
    deletions = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
    
    # Filter to just the meaningful change lines
    modified_lines = [
        line for line in diff
        if line.startswith('+') or line.startswith('-')
        if not line.startswith('+++') and not line.startswith('---')
    ]
    
    changed = len(modified_lines) > 0
    
    # Build summary
    if not changed:
        summary = "No changes detected."
    else:
        parts = []
        if insertions > 0:
            parts.append(f"{insertions} line(s) added")
        if deletions > 0:
            parts.append(f"{deletions} line(s) removed")
        summary = ", ".join(parts) + "."
    
    return DiffResult(
        node_id=node_id,
        heading=heading,
        changed=changed,
        from_version=from_version,
        to_version=to_version,
        insertions=insertions,
        deletions=deletions,
        modified_lines=modified_lines[:50],  # Cap at 50 lines
        summary=summary,
    )
