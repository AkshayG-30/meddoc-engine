"""QA test case generation orchestrator.

Coordinates: gather text from selection → build prompt → call LLM → validate → store.

Duplicate policy: If selection_content_hash + model + prompt_version match an
existing generation, return the cached result. No regeneration.
This is defensible: same input + same model + same prompt = same output.
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.database.models import Node, Selection, SelectionItem
from backend.database.mongo_client import get_generations_collection
from backend.llm.groq_client import call_llm
from backend.llm.prompt_templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, PROMPT_VERSION
from backend.llm.validator import validate_llm_output


MODEL = "llama-3.3-70b-versatile"
MAX_RETRIES = 1  # Retry once on malformed output, then fail


def _build_section_content(db: Session, selection: Selection) -> tuple[str, dict[str, str]]:
    """Gather text from all nodes in a selection.
    
    Returns:
        section_content: Combined text for the LLM prompt
        content_hashes: {node_id: content_hash} for traceability
    """
    parts = []
    content_hashes = {}
    
    for item in selection.items:
        node = db.query(Node).filter(Node.id == item.node_id).first()
        if node:
            parts.append(f"## {node.heading}\n{node.body_text}")
            content_hashes[node.id] = node.content_hash
    
    return "\n\n".join(parts), content_hashes


def _compute_selection_content_hash(content: str, model: str, prompt_version: str) -> str:
    """Compute hash of selection content + model + prompt version.
    
    Used for duplicate detection policy.
    """
    combined = f"{content}|{model}|{prompt_version}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def generate_test_cases(
    db: Session,
    selection_id: str,
) -> dict:
    """Generate QA test cases for a selection.
    
    Flow:
    1. Gather text from selection nodes
    2. Check for duplicate (same content + model + prompt version)
    3. If duplicate found → return cached
    4. If not → call LLM → validate → store → return
    
    Error handling:
    - Malformed LLM output → retry once
    - Second failure → return error with raw response
    """
    # Get selection
    selection = db.query(Selection).filter(Selection.id == selection_id).first()
    if not selection:
        raise ValueError(f"Selection {selection_id} not found")
    
    # Build section content
    section_content, content_hashes = _build_section_content(db, selection)
    if not section_content:
        raise ValueError("No content found for selection nodes")
    
    # Check for duplicate
    selection_content_hash = _compute_selection_content_hash(section_content, MODEL, PROMPT_VERSION)
    collection = get_generations_collection()
    
    existing = collection.find_one({
        "selection_content_hash": selection_content_hash,
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
    })
    
    if existing:
        existing["_id"] = str(existing["_id"])
        return existing
    
    # Build prompt
    user_prompt = USER_PROMPT_TEMPLATE.format(section_content=section_content)
    
    # Call LLM with retry
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            raw_response = call_llm(SYSTEM_PROMPT, user_prompt, model=MODEL)
            parsed, error = validate_llm_output(raw_response)
            
            if parsed:
                # Success — store in MongoDB
                generation_doc = {
                    "selection_id": selection_id,
                    "node_ids": list(content_hashes.keys()),
                    "version_id": selection.items[0].version_id if selection.items else "",
                    "content_hashes": content_hashes,
                    "model": MODEL,
                    "prompt_version": PROMPT_VERSION,
                    "test_cases": [tc.model_dump() for tc in parsed.test_cases],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "selection_content_hash": selection_content_hash,
                    "raw_response": raw_response,
                }
                
                result = collection.insert_one(generation_doc)
                generation_doc["_id"] = str(result.inserted_id)
                return generation_doc
            else:
                last_error = error
        except Exception as e:
            last_error = str(e)
    
    # All retries exhausted — return error
    return {
        "error": True,
        "message": f"LLM output validation failed after {MAX_RETRIES + 1} attempts",
        "last_error": last_error,
        "selection_id": selection_id,
    }
