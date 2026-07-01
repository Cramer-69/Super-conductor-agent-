"""Tests for semantic_wall/memory/embeddings.py — mocked OpenAI client, no
live API calls, and a temp cache dir so tests don't pollute the real cache."""

from unittest.mock import MagicMock, patch

import pytest

from semantic_wall import config
from semantic_wall.memory.embeddings import EmbeddingGenerator


@pytest.fixture
def generator(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "openai_api_key", "test-key")
    gen = EmbeddingGenerator()
    gen.cache_dir = tmp_path
    return gen


def _mock_openai_client(vectors):
    client = MagicMock()
    client.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=v) for v in vectors]
    )
    return client


def test_embed_calls_openai_and_caches(generator):
    with patch.object(generator, "_client_or_raise", return_value=_mock_openai_client([[0.1, 0.2]])):
        result = generator.embed(["hello"])
    assert result == [[0.1, 0.2]]
    # Cached on disk now — a second call shouldn't need the client at all.
    with patch.object(generator, "_client_or_raise", side_effect=AssertionError("should not call API again")):
        cached_result = generator.embed(["hello"])
    assert cached_result == [[0.1, 0.2]]


def test_embed_one(generator):
    with patch.object(generator, "_client_or_raise", return_value=_mock_openai_client([[1.0, 2.0, 3.0]])):
        result = generator.embed_one("hi")
    assert result == [1.0, 2.0, 3.0]


def test_embed_without_api_key_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(config.settings, "openai_api_key", None)
    gen = EmbeddingGenerator()
    gen.cache_dir = tmp_path
    with pytest.raises(ValueError):
        gen.embed(["hello"])


def test_embed_fully_cached_does_not_require_api_key(generator, monkeypatch):
    with patch.object(generator, "_client_or_raise", return_value=_mock_openai_client([[5.0]])):
        generator.embed(["warm the cache"])

    # No API key needed now that the only text requested is fully cached.
    monkeypatch.setattr(config.settings, "openai_api_key", None)
    result = generator.embed(["warm the cache"])
    assert result == [[5.0]]


def test_embed_bypasses_cache_when_disabled(generator):
    with patch.object(generator, "_client_or_raise", return_value=_mock_openai_client([[9.0]])):
        generator.embed(["skip cache"], use_cache=False)
    # Cache should be empty since use_cache=False skips writing.
    assert list(generator.cache_dir.iterdir()) == []
