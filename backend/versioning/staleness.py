"""Staleness detection — determines if generated test cases still reflect current document.

At retrieval time, compares the content hash stored at generation time against
the current version's content hash for each source node.

Statuses:
- CURRENT: Content hash matches — test case reflects current document
- STALE: Content hash differs — document text changed since generation
- ORPHANED: Source node no longer exists in the latest version

KNOWN LIMITATION: Any text change triggers STALE, regardless of significance.
A one-word wording change is treated the same as a changed pressure threshold.
"""

from sqlalchemy.orm import Session

from backend.database.models import Node, DocumentVersion
from backend.database.schemas import NodeStalenessInfo, StalenessResponse
from backend.versioning.version_manager import _title_similarity, _parent_path_similarity


def check_node_staleness(
    db: Session,
    node_id: str,
    content_hash_at_generation: str,
    document_id: str,
) -> NodeStalenessInfo:
    """Check staleness for a single node.
    
    Finds the node in the latest version and compares content hashes.
    """
    # Get the original node
    original_node = db.query(Node).filter(Node.id == node_id).first()
    if not original_node:
        return NodeStalenessInfo(
            node_id=node_id,
            heading="Unknown",
            status="ORPHANED",
            old_hash=content_hash_at_generation,
            current_hash=None,
        )
    
    # Get the latest version for this document
    latest_version = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )
    
    if not latest_version:
        return NodeStalenessInfo(
            node_id=node_id,
            heading=original_node.heading,
            status="ORPHANED",
            old_hash=content_hash_at_generation,
            current_hash=None,
        )
    
    # If the node is already from the latest version, just compare hashes
    if original_node.version_id == latest_version.id:
        status = "CURRENT" if original_node.content_hash == content_hash_at_generation else "STALE"
        return NodeStalenessInfo(
            node_id=node_id,
            heading=original_node.heading,
            status=status,
            old_hash=content_hash_at_generation,
            current_hash=original_node.content_hash,
        )
    
    # Find the corresponding node in the latest version
    # First, try matched_node_id chain
    latest_nodes = db.query(Node).filter(Node.version_id == latest_version.id).all()
    
    # Check if any latest node has matched_node_id pointing to our node
    current_node = None
    for ln in latest_nodes:
        if ln.matched_node_id == node_id:
            current_node = ln
            break
    
    # If no direct match, try to find by heading similarity
    if not current_node:
        best_score = 0.0
        for ln in latest_nodes:
            title_sim = _title_similarity(original_node.heading, ln.heading)
            path_sim = _parent_path_similarity(original_node.node_path, ln.node_path)
            score = title_sim * 0.5 + path_sim * 0.5
            if score > best_score and score >= 0.6:
                best_score = score
                current_node = ln
    
    if not current_node:
        return NodeStalenessInfo(
            node_id=node_id,
            heading=original_node.heading,
            status="ORPHANED",
            old_hash=content_hash_at_generation,
            current_hash=None,
        )
    
    status = "CURRENT" if current_node.content_hash == content_hash_at_generation else "STALE"
    return NodeStalenessInfo(
        node_id=node_id,
        heading=original_node.heading,
        status=status,
        old_hash=content_hash_at_generation,
        current_hash=current_node.content_hash,
    )


def check_generation_staleness(
    db: Session,
    generation: dict,  # MongoDB generation document
    document_id: str,
) -> StalenessResponse:
    """Check staleness for all nodes in a generation.
    
    Returns overall status:
    - CURRENT: All nodes current
    - STALE: At least one node changed
    - PARTIALLY_STALE: Some nodes current, some stale
    - ORPHANED: At least one node no longer exists
    """
    node_statuses = []
    content_hashes = generation.get("content_hashes", {})
    
    for node_id in generation.get("node_ids", []):
        hash_at_gen = content_hashes.get(node_id, "")
        status = check_node_staleness(db, node_id, hash_at_gen, document_id)
        node_statuses.append(status)
    
    # Determine overall status
    statuses = [ns.status for ns in node_statuses]
    if all(s == "CURRENT" for s in statuses):
        overall = "CURRENT"
    elif any(s == "ORPHANED" for s in statuses):
        overall = "ORPHANED"
    elif all(s == "STALE" for s in statuses):
        overall = "STALE"
    else:
        overall = "PARTIALLY_STALE"
    
    return StalenessResponse(
        generation_id=str(generation.get("_id", "")),
        overall_status=overall,
        nodes=node_statuses,
    )
