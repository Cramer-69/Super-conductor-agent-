"""Memory read/write against Supabase pgvector.

Depends on the schema in semantic_wall/db/schema.sql (the `memories` table
and the `match_memories` RPC function) already existing on the connected
Supabase project.
"""

from typing import Any, Dict, List, Optional

from semantic_wall.db.supabase_client import get_client
from semantic_wall.memory.embeddings import EmbeddingGenerator

_embedder = EmbeddingGenerator()


def write_memory(
    user_id: str,
    agent_id: str,
    session_id: str,
    role: str,
    content: str,
    topic_tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Embed and store one conversation turn. Returns the inserted row."""
    embedding = _embedder.embed_one(content)
    client = get_client()

    row = {
        "user_id": user_id,
        "agent_id": agent_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "embedding": embedding,
        "topic_tags": topic_tags or [],
    }
    response = client.table("memories").insert(row).execute()
    return response.data[0] if response.data else row


def search_memories(user_id: str, query_text: str, k: int = 10) -> List[Dict[str, Any]]:
    """Top-K cosine-similarity search over this user's memories."""
    query_embedding = _embedder.embed_one(query_text)
    client = get_client()

    response = client.rpc(
        "match_memories",
        {
            "query_embedding": query_embedding,
            "match_user_id": user_id,
            "match_count": k,
        },
    ).execute()
    return response.data or []


def mark_session_outcome(session_id: str, outcome_verified: bool, quality_score: Optional[int] = None) -> int:
    """Write the check-in's verification result back onto every memory row
    for this session. Returns the number of rows updated."""
    client = get_client()
    update: Dict[str, Any] = {"outcome_verified": outcome_verified}
    if quality_score is not None:
        update["quality_score"] = quality_score

    response = client.table("memories").update(update).eq("session_id", session_id).execute()
    return len(response.data or [])
