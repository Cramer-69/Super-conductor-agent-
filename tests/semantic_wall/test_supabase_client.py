"""Tests for semantic_wall/db/supabase_client.py's configuration gate."""

import pytest

from semantic_wall import config
from semantic_wall.db import supabase_client


def test_not_configured_by_default(monkeypatch):
    monkeypatch.setattr(config.settings, "supabase_url", None)
    monkeypatch.setattr(config.settings, "supabase_key", None)
    assert supabase_client.is_configured() is False


def test_get_client_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(config.settings, "supabase_url", None)
    monkeypatch.setattr(config.settings, "supabase_key", None)
    supabase_client.reset_client_for_tests()

    with pytest.raises(supabase_client.SupabaseNotConfigured):
        supabase_client.get_client()


def test_is_configured_true_when_both_set(monkeypatch):
    monkeypatch.setattr(config.settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(config.settings, "supabase_key", "test-key")
    assert supabase_client.is_configured() is True
