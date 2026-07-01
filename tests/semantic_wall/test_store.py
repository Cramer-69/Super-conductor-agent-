"""Tests for semantic_wall/memory/store.py — mocked Supabase client and
embedder, no live network calls."""

from unittest.mock import MagicMock, patch

from semantic_wall.memory import store


def test_write_memory_inserts_row_with_embedding():
    fake_client = MagicMock()
    fake_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "row-1", "content": "hello"}]
    )

    with patch.object(store, "get_client", return_value=fake_client), \
         patch.object(store._embedder, "embed_one", return_value=[0.1, 0.2]):
        result = store.write_memory("user-1", "strategist", "session-1", "user", "hello")

    assert result == {"id": "row-1", "content": "hello"}
    inserted_row = fake_client.table.return_value.insert.call_args[0][0]
    assert inserted_row["embedding"] == [0.1, 0.2]
    assert inserted_row["user_id"] == "user-1"
    assert inserted_row["session_id"] == "session-1"


def test_search_memories_calls_match_memories_rpc():
    fake_client = MagicMock()
    fake_client.rpc.return_value.execute.return_value = MagicMock(
        data=[{"id": "row-1", "similarity": 0.9}]
    )

    with patch.object(store, "get_client", return_value=fake_client), \
         patch.object(store._embedder, "embed_one", return_value=[0.3, 0.4]):
        results = store.search_memories("user-1", "what did we discuss?", k=5)

    assert results == [{"id": "row-1", "similarity": 0.9}]
    fake_client.rpc.assert_called_once_with(
        "match_memories",
        {"query_embedding": [0.3, 0.4], "match_user_id": "user-1", "match_count": 5},
    )


def test_search_memories_returns_empty_list_when_no_data():
    fake_client = MagicMock()
    fake_client.rpc.return_value.execute.return_value = MagicMock(data=None)

    with patch.object(store, "get_client", return_value=fake_client), \
         patch.object(store._embedder, "embed_one", return_value=[0.0]):
        results = store.search_memories("user-1", "anything")

    assert results == []


def test_mark_session_outcome_updates_rows():
    fake_client = MagicMock()
    fake_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "row-1"}, {"id": "row-2"}]
    )

    with patch.object(store, "get_client", return_value=fake_client):
        updated_count = store.mark_session_outcome("session-1", outcome_verified=True, quality_score=4)

    assert updated_count == 2
    update_payload = fake_client.table.return_value.update.call_args[0][0]
    assert update_payload == {"outcome_verified": True, "quality_score": 4}
    fake_client.table.return_value.update.return_value.eq.assert_called_once_with("session_id", "session-1")
