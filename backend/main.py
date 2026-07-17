"""FastAPI application — main entry point for the MedDoc Engine API.

Provides endpoints for:
- Document ingestion and versioning
- Tree browsing and node detail
- Search across headings and text
- Version-pinned selections
- LLM-powered QA test case generation
- Staleness detection and generation retrieval
"""

import os
import shutil
import hashlib
from typing import Optional

from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, Query
from sqlalchemy.orm import Session
from bson import ObjectId

from backend.config import get_settings
from backend.database.models import Base, Document, DocumentVersion, Node, Selection, SelectionItem
from backend.database.session import get_db, get_engine
from backend.database.schemas import (
    DocumentResponse, DocumentVersionResponse,
    NodeSummary, NodeDetail, DiffResult,
    SelectionCreate, SelectionResponse, SelectionItemResponse,
    SearchResponse, SearchResult,
    GenerationRequest, GenerationResponse, TestCaseSchema,
    StalenessResponse,
)
from backend.database.mongo_client import get_generations_collection
from backend.parser.extractor import extract_from_pdf, extract_file_hash
from backend.parser.hierarchy import build_hierarchy, flatten_tree, compute_content_hash
from backend.versioning.version_manager import get_or_create_document, create_version, match_nodes
from backend.versioning.diff_engine import compute_diff
from backend.versioning.staleness import check_generation_staleness
from backend.llm.generator import generate_test_cases


# ─── App Setup ───

app = FastAPI(
    title="MedDoc Engine",
    description="Medical document versioning, QA generation, and traceability API",
    version="1.0.0",
)


@app.on_event("startup")
def startup():
    """Create database tables on startup."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


# ─── Document Endpoints ───

@app.get("/api/documents", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    """List all documents."""
    docs = db.query(Document).all()
    result = []
    for doc in docs:
        result.append(DocumentResponse(
            id=doc.id,
            name=doc.name,
            created_at=doc.created_at,
            version_count=len(doc.versions),
        ))
    return result


@app.post("/api/documents/ingest")
def ingest_document(
    file: UploadFile = File(...),
    document_name: str = Form(...),
    db: Session = Depends(get_db),
):
    """Ingest a PDF document, creating or updating a versioned document.
    
    - First ingestion: Creates document + version 1
    - Subsequent ingestion with same name: Creates new version, matches nodes
    """
    # Save uploaded file temporarily
    temp_path = f"data/_temp_{file.filename}"
    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Compute file hash
        file_hash = extract_file_hash(temp_path)
        
        # Get or create document
        document = get_or_create_document(db, document_name)
        
        # Check for duplicate file hash (same exact file already ingested)
        existing_version = (
            db.query(DocumentVersion)
            .filter(
                DocumentVersion.document_id == document.id,
                DocumentVersion.file_hash == file_hash,
            )
            .first()
        )
        if existing_version:
            return {
                "message": "This exact file has already been ingested",
                "document_id": document.id,
                "version_id": existing_version.id,
                "version_number": existing_version.version_number,
                "status": "duplicate",
            }
        
        # Create new version
        version = create_version(db, document, file_hash, file.filename)
        
        # Parse PDF
        sections, title_lines = extract_from_pdf(temp_path)
        tree = build_hierarchy(sections, title_lines)
        flat_nodes = flatten_tree(tree)
        
        # Store nodes
        for tree_node in flat_nodes:
            # Find parent DB id
            parent_db_id = None
            if tree_node.parent_id:
                # The parent_id in TreeNode is the TreeNode's id, need to map
                for other in flat_nodes:
                    if other.id == tree_node.parent_id:
                        parent_db_id = other.id
                        break
            
            db_node = Node(
                id=tree_node.id,
                version_id=version.id,
                heading=tree_node.heading,
                level=tree_node.level,
                body_text=tree_node.full_text,
                content_hash=tree_node.content_hash,
                parent_id=parent_db_id,
                position=tree_node.position,
                node_path=tree_node.node_path,
            )
            db.add(db_node)
        
        db.commit()
        
        # Cross-version node matching (if there's a previous version)
        if version.version_number > 1:
            prev_version = (
                db.query(DocumentVersion)
                .filter(
                    DocumentVersion.document_id == document.id,
                    DocumentVersion.version_number == version.version_number - 1,
                )
                .first()
            )
            if prev_version:
                match_nodes(db, version.id, prev_version.id)
        
        return {
            "message": "Document ingested successfully",
            "document_id": document.id,
            "document_name": document.name,
            "version_id": version.id,
            "version_number": version.version_number,
            "nodes_created": len(flat_nodes),
            "status": "success",
        }
    
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/api/documents/{doc_id}/versions", response_model=list[DocumentVersionResponse])
def list_versions(doc_id: str, db: Session = Depends(get_db)):
    """List all versions of a document."""
    versions = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.version_number)
        .all()
    )
    return versions


# ─── Browse API ───

@app.get("/api/documents/{doc_id}/tree")
def get_document_tree(
    doc_id: str,
    version: Optional[int] = Query(None, description="Version number (default: latest)"),
    db: Session = Depends(get_db),
):
    """Get top-level sections of a document as a tree.
    
    Defaults to the latest version if no version parameter is provided.
    """
    # Get version
    if version:
        doc_version = (
            db.query(DocumentVersion)
            .filter(
                DocumentVersion.document_id == doc_id,
                DocumentVersion.version_number == version,
            )
            .first()
        )
    else:
        doc_version = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc_id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )
    
    if not doc_version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    # Get top-level nodes (no parent)
    top_nodes = (
        db.query(Node)
        .filter(Node.version_id == doc_version.id, Node.parent_id.is_(None))
        .order_by(Node.position)
        .all()
    )
    
    def node_to_dict(node: Node) -> dict:
        children = (
            db.query(Node)
            .filter(Node.parent_id == node.id)
            .order_by(Node.position)
            .all()
        )
        return {
            "id": node.id,
            "heading": node.heading,
            "level": node.level,
            "node_path": node.node_path,
            "content_hash": node.content_hash,
            "has_children": len(children) > 0,
            "children": [node_to_dict(c) for c in children],
        }
    
    return {
        "document_id": doc_id,
        "version_number": doc_version.version_number,
        "version_id": doc_version.id,
        "sections": [node_to_dict(n) for n in top_nodes],
    }


@app.get("/api/nodes/{node_id}")
def get_node_detail(node_id: str, db: Session = Depends(get_db)):
    """Get a specific node by ID, including children, full text, and content hash."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    children = (
        db.query(Node)
        .filter(Node.parent_id == node.id)
        .order_by(Node.position)
        .all()
    )
    
    children_summaries = [
        NodeSummary(
            id=c.id,
            heading=c.heading,
            level=c.level,
            node_path=c.node_path,
            has_children=db.query(Node).filter(Node.parent_id == c.id).count() > 0,
            content_hash=c.content_hash,
        )
        for c in children
    ]
    
    return NodeDetail(
        id=node.id,
        heading=node.heading,
        level=node.level,
        body_text=node.body_text,
        content_hash=node.content_hash,
        node_path=node.node_path,
        parent_id=node.parent_id,
        position=node.position,
        version_id=node.version_id,
        matched_node_id=node.matched_node_id,
        has_changed=node.has_changed,
        children=children_summaries,
    )


# ─── Diff API ───

@app.get("/api/nodes/{node_id}/diff")
def get_node_diff(
    node_id: str,
    from_version: int = Query(..., description="Source version number"),
    to_version: int = Query(..., description="Target version number"),
    db: Session = Depends(get_db),
):
    """Compare a node across two versions.
    
    Returns whether the node changed, and a lightweight diff summary.
    """
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # Get the document
    version = db.query(DocumentVersion).filter(DocumentVersion.id == node.version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    # Find matched node in the other version
    if node.matched_node_id:
        other_node = db.query(Node).filter(Node.id == node.matched_node_id).first()
    else:
        # Try reverse match
        other_node = db.query(Node).filter(Node.matched_node_id == node_id).first()
    
    if not other_node:
        return DiffResult(
            node_id=node_id,
            heading=node.heading,
            changed=True,
            from_version=from_version,
            to_version=to_version,
            summary="Node does not exist in the other version.",
        )
    
    # Determine which is old and which is new
    node_version = db.query(DocumentVersion).filter(DocumentVersion.id == node.version_id).first()
    other_version = db.query(DocumentVersion).filter(DocumentVersion.id == other_node.version_id).first()
    
    if node_version.version_number <= other_version.version_number:
        old_text, new_text = node.body_text, other_node.body_text
    else:
        old_text, new_text = other_node.body_text, node.body_text
    
    return compute_diff(
        old_text=old_text,
        new_text=new_text,
        node_id=node_id,
        heading=node.heading,
        from_version=from_version,
        to_version=to_version,
    )


# ─── Search API ───

@app.get("/api/search", response_model=SearchResponse)
def search_nodes(
    q: str = Query(..., description="Search query"),
    version: Optional[int] = Query(None, description="Version number (default: latest)"),
    doc_id: Optional[str] = Query(None, description="Document ID to search within"),
    db: Session = Depends(get_db),
):
    """Search across node headings and text using SQLite LIKE.
    
    KNOWN LIMITATION: Simple LIKE search — no ranking, no BM25,
    no embeddings, no vector search. Acceptable for this scope.
    """
    query = db.query(Node).join(DocumentVersion)
    
    if doc_id:
        query = query.filter(DocumentVersion.document_id == doc_id)
    
    if version:
        query = query.filter(DocumentVersion.version_number == version)
    else:
        # Default to latest version per document
        # Get latest version IDs
        from sqlalchemy import func
        latest_subq = (
            db.query(
                DocumentVersion.document_id,
                func.max(DocumentVersion.version_number).label("max_ver"),
            )
            .group_by(DocumentVersion.document_id)
            .subquery()
        )
        latest_versions = (
            db.query(DocumentVersion.id)
            .join(
                latest_subq,
                (DocumentVersion.document_id == latest_subq.c.document_id)
                & (DocumentVersion.version_number == latest_subq.c.max_ver),
            )
            .all()
        )
        version_ids = [v[0] for v in latest_versions]
        query = query.filter(Node.version_id.in_(version_ids))
    
    # Search in heading and body text
    search_term = f"%{q}%"
    results = (
        query.filter(
            (Node.heading.like(search_term)) | (Node.body_text.like(search_term))
        )
        .limit(50)
        .all()
    )
    
    search_results = []
    for node in results:
        # Create snippet
        if q.lower() in node.body_text.lower():
            idx = node.body_text.lower().index(q.lower())
            start = max(0, idx - 50)
            end = min(len(node.body_text), idx + len(q) + 50)
            snippet = "..." + node.body_text[start:end] + "..."
        else:
            snippet = node.body_text[:100] + "..." if len(node.body_text) > 100 else node.body_text
        
        search_results.append(SearchResult(
            node_id=node.id,
            heading=node.heading,
            node_path=node.node_path,
            level=node.level,
            snippet=snippet,
            version_id=node.version_id,
        ))
    
    return SearchResponse(
        query=q,
        version=version,
        results=search_results,
        total=len(search_results),
    )


# ─── Selection API ───

@app.post("/api/selections", response_model=SelectionResponse)
def create_selection(payload: SelectionCreate, db: Session = Depends(get_db)):
    """Create a named selection of nodes, version-pinned.
    
    Selections reference specific node+version pairs. The content hash
    at selection time is stored, so old selections resolve to the exact
    text they were created against, even after re-ingestion.
    """
    selection = Selection(name=payload.name)
    db.add(selection)
    db.flush()
    
    items = []
    for item_data in payload.items:
        node = db.query(Node).filter(Node.id == item_data.node_id).first()
        if not node:
            raise HTTPException(status_code=404, detail=f"Node {item_data.node_id} not found")
        
        sel_item = SelectionItem(
            selection_id=selection.id,
            node_id=item_data.node_id,
            version_id=item_data.version_id,
            content_hash_at_selection=node.content_hash,
        )
        db.add(sel_item)
        items.append(sel_item)
    
    db.commit()
    db.refresh(selection)
    
    # Build response with node details
    response_items = []
    for item in selection.items:
        node = db.query(Node).filter(Node.id == item.node_id).first()
        response_items.append(SelectionItemResponse(
            id=item.id,
            node_id=item.node_id,
            version_id=item.version_id,
            content_hash_at_selection=item.content_hash_at_selection,
            heading=node.heading if node else None,
            body_text=node.body_text if node else None,
        ))
    
    return SelectionResponse(
        id=selection.id,
        name=selection.name,
        created_at=selection.created_at,
        items=response_items,
    )


@app.get("/api/selections/{selection_id}", response_model=SelectionResponse)
def get_selection(selection_id: str, db: Session = Depends(get_db)):
    """Retrieve a selection with resolved text."""
    selection = db.query(Selection).filter(Selection.id == selection_id).first()
    if not selection:
        raise HTTPException(status_code=404, detail="Selection not found")
    
    response_items = []
    for item in selection.items:
        node = db.query(Node).filter(Node.id == item.node_id).first()
        response_items.append(SelectionItemResponse(
            id=item.id,
            node_id=item.node_id,
            version_id=item.version_id,
            content_hash_at_selection=item.content_hash_at_selection,
            heading=node.heading if node else None,
            body_text=node.body_text if node else None,
        ))
    
    return SelectionResponse(
        id=selection.id,
        name=selection.name,
        created_at=selection.created_at,
        items=response_items,
    )


# ─── Generation API ───

@app.post("/api/generations")
def create_generation(payload: GenerationRequest, db: Session = Depends(get_db)):
    """Generate QA test cases for a selection using LLM.
    
    Duplicate policy: If the same selection content + model + prompt version
    has already been generated, returns the cached result.
    """
    try:
        result = generate_test_cases(db, payload.selection_id)
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/generations")
def list_generations(
    selection_id: Optional[str] = Query(None),
    node_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Fetch generations by selection ID or node ID.
    
    Includes staleness check at retrieval time.
    """
    collection = get_generations_collection()
    query = {}
    
    if selection_id:
        query["selection_id"] = selection_id
    if node_id:
        query["node_ids"] = node_id
    
    generations = list(collection.find(query))
    
    results = []
    for gen in generations:
        gen["_id"] = str(gen["_id"])
        
        # Perform staleness check
        if gen.get("node_ids"):
            # Get document_id from the first node
            first_node = db.query(Node).filter(Node.id == gen["node_ids"][0]).first()
            if first_node:
                version = db.query(DocumentVersion).filter(
                    DocumentVersion.id == first_node.version_id
                ).first()
                if version:
                    staleness = check_generation_staleness(db, gen, version.document_id)
                    gen["staleness_status"] = staleness.overall_status
                    gen["stale_nodes"] = [
                        {"node_id": ns.node_id, "heading": ns.heading, "status": ns.status}
                        for ns in staleness.nodes
                    ]
        
        results.append(gen)
    
    return results


@app.get("/api/generations/{generation_id}")
def get_generation(generation_id: str, db: Session = Depends(get_db)):
    """Get a specific generation with staleness check."""
    collection = get_generations_collection()
    
    try:
        gen = collection.find_one({"_id": ObjectId(generation_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid generation ID format")
    
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found")
    
    gen["_id"] = str(gen["_id"])
    
    # Staleness check
    if gen.get("node_ids"):
        first_node = db.query(Node).filter(Node.id == gen["node_ids"][0]).first()
        if first_node:
            version = db.query(DocumentVersion).filter(
                DocumentVersion.id == first_node.version_id
            ).first()
            if version:
                staleness = check_generation_staleness(db, gen, version.document_id)
                gen["staleness_status"] = staleness.overall_status
                gen["stale_nodes"] = [
                    {"node_id": ns.node_id, "heading": ns.heading, "status": ns.status}
                    for ns in staleness.nodes
                ]
    
    return gen


# ─── Health Check ───

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "meddoc-engine"}
