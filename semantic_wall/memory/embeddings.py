"""Embedding generation for the Semantic Wall memory layer.

Adapted from this repo's knowledge_base/embeddings.py, trimmed to the
OpenAI-only path (text-embedding-3-large) per the blueprint's stated
choice — the original file's Gemini-fallback branch isn't needed here.
"""

import hashlib
import json
from pathlib import Path
from typing import List, Optional

from openai import OpenAI

from semantic_wall.config import settings


class EmbeddingGenerator:
    """Generates and disk-caches embeddings via the OpenAI embeddings API."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.embedding_model
        self._client: Optional[OpenAI] = None
        self.cache_dir = Path(__file__).resolve().parent.parent / "data" / "embeddings_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _client_or_raise(self) -> OpenAI:
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required for embeddings (semantic_wall uses "
                "OpenAI text-embedding-3-large regardless of which provider "
                "answers chat)."
            )
        if self._client is None:
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    def embed(self, texts: List[str], use_cache: bool = True) -> List[List[float]]:
        """Embed a batch of texts, using the disk cache where possible."""
        embeddings: List[Optional[List[float]]] = [None] * len(texts)
        to_fetch: List[str] = []
        fetch_indices: List[int] = []

        for i, text in enumerate(texts):
            cached = self._read_cache(text) if use_cache else None
            if cached is not None:
                embeddings[i] = cached
            else:
                to_fetch.append(text)
                fetch_indices.append(i)

        if to_fetch:
            # Only acquire (and require) the client if there's actually
            # something not already covered by the cache.
            client = self._client_or_raise()
            response = client.embeddings.create(model=self.model, input=to_fetch)
            for idx, item in enumerate(response.data):
                original_idx = fetch_indices[idx]
                embeddings[original_idx] = item.embedding
                if use_cache:
                    self._write_cache(to_fetch[idx], item.embedding)

        return embeddings  # type: ignore[return-value]

    def embed_one(self, text: str, use_cache: bool = True) -> List[float]:
        return self.embed([text], use_cache=use_cache)[0]

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model}:{text}".encode()).hexdigest()

    def _read_cache(self, text: str) -> Optional[List[float]]:
        cache_file = self.cache_dir / f"{self._cache_key(text)}.json"
        if not cache_file.exists():
            return None
        try:
            with open(cache_file) as f:
                return json.load(f)["embedding"]
        except (OSError, KeyError, json.JSONDecodeError):
            return None

    def _write_cache(self, text: str, embedding: List[float]) -> None:
        cache_file = self.cache_dir / f"{self._cache_key(text)}.json"
        try:
            with open(cache_file, "w") as f:
                json.dump({"text_preview": text[:100], "embedding": embedding}, f)
        except OSError:
            pass
