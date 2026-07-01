"""Thin Supabase client wrapper — gates all memory-layer access behind
is_configured(), matching this repo's connectors/github_connector.py
pattern (absent credentials = gracefully unavailable, not a crash)."""

from typing import Optional

from semantic_wall.config import settings


class SupabaseNotConfigured(RuntimeError):
    """Raised when memory-layer operations are attempted without a configured Supabase project."""


_client = None


def is_configured() -> bool:
    return settings.is_memory_configured()


def get_client():
    """Lazily create and cache the Supabase client. Raises SupabaseNotConfigured
    if SUPABASE_URL/SUPABASE_KEY aren't set — callers should check
    is_configured() first to produce a friendlier error/response."""
    global _client
    if not is_configured():
        raise SupabaseNotConfigured(
            "Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY "
            "(see semantic_wall/README.md for project setup)."
        )
    if _client is None:
        from supabase import create_client

        _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client


def reset_client_for_tests() -> None:
    """Test-only: clears the cached client so tests can inject a fake."""
    global _client
    _client = None
