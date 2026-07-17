"""MongoDB client for storing LLM-generated QA outputs.

Uses pymongo directly — no ODM overhead for simple document storage.
The generations collection stores test cases linked to selections
and to the exact node content they were generated from.
"""

from pymongo import MongoClient
from pymongo.collection import Collection
from backend.config import get_settings


_client = None
_db = None


def get_mongo_db():
    """Get MongoDB database instance (lazy singleton)."""
    global _client, _db
    if _db is None:
        settings = get_settings()
        _client = MongoClient(settings.MONGO_URI)
        _db = _client[settings.MONGO_DB_NAME]
    return _db


def get_generations_collection() -> Collection:
    """Get the generations collection."""
    db = get_mongo_db()
    return db["generations"]


def close_mongo():
    """Close MongoDB connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
