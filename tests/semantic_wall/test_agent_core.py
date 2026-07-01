"""Tests for semantic_wall/agent/core.py — mocked provider clients and
memory layer, no live network calls."""

from unittest.mock import MagicMock, patch

from semantic_wall import config
from semantic_wall.agent import core


def test_provider_for_keys_prefers_default_when_configured(monkeypatch):
    monkeypatch.setattr(config.settings, "default_agent_model_provider", "anthropic")
    monkeypatch.setattr(config.settings, "anthropic_api_key", "key")
    monkeypatch.setattr(config.settings, "xai_api_key", None)
    monkeypatch.setattr(config.settings, "openai_api_key", None)
    provider, model = core._provider_for_keys()
    assert provider == "anthropic"


def test_provider_for_keys_falls_back_when_default_unavailable(monkeypatch):
    monkeypatch.setattr(config.settings, "default_agent_model_provider", "anthropic")
    monkeypatch.setattr(config.settings, "anthropic_api_key", None)
    monkeypatch.setattr(config.settings, "xai_api_key", "key")
    monkeypatch.setattr(config.settings, "openai_api_key", None)
    provider, _ = core._provider_for_keys()
    assert provider == "xai"


def test_provider_for_keys_none_when_nothing_configured(monkeypatch):
    monkeypatch.setattr(config.settings, "anthropic_api_key", None)
    monkeypatch.setattr(config.settings, "xai_api_key", None)
    monkeypatch.setattr(config.settings, "openai_api_key", None)
    provider, model = core._provider_for_keys()
    assert provider == "none"


def test_chat_without_memory_configured_skips_retrieval_and_write(monkeypatch):
    monkeypatch.setattr(config.settings, "anthropic_api_key", "key")
    agent = core.SemanticWallAgent(agent_id="strategist")
    agent.provider, agent.model = "anthropic", "claude-sonnet-5"

    with patch.object(core, "memory_is_configured", return_value=False), \
         patch.object(agent, "_call_anthropic", return_value="hi there") as mock_call, \
         patch.object(core, "search_memories") as mock_search, \
         patch.object(core, "write_memory") as mock_write:
        result = agent.chat("user-1", "session-1", "hello")

    mock_search.assert_not_called()
    mock_write.assert_not_called()
    mock_call.assert_called_once()
    assert result["response"] == "hi there"
    assert result["memories_used"] == 0


def test_chat_with_memory_configured_injects_context_and_writes_turns():
    agent = core.SemanticWallAgent(agent_id="strategist")
    agent.provider, agent.model = "anthropic", "claude-sonnet-5"

    fake_memories = [{"role": "user", "created_at": "t0", "content": "past message"}]

    with patch.object(core, "memory_is_configured", return_value=True), \
         patch.object(core, "search_memories", return_value=fake_memories) as mock_search, \
         patch.object(core, "write_memory") as mock_write, \
         patch.object(agent, "_call_anthropic", return_value="answer") as mock_call:
        result = agent.chat("user-1", "session-1", "hello again")

    mock_search.assert_called_once_with("user-1", "hello again", k=10)
    assert mock_write.call_count == 2  # user turn + assistant turn
    system_prompt_arg = mock_call.call_args[0][0]
    assert "past message" in system_prompt_arg
    assert result["memories_used"] == 1


def test_chat_no_provider_configured_returns_friendly_message():
    agent = core.SemanticWallAgent(agent_id="strategist")
    agent.provider, agent.model = "none", "none"

    with patch.object(core, "memory_is_configured", return_value=False):
        result = agent.chat("user-1", "session-1", "hello")

    assert "No model provider configured" in result["response"]


def test_call_openai_wire_uses_base_url_for_xai():
    agent = core.SemanticWallAgent()
    fake_response_content = "grok answer"

    with patch("semantic_wall.agent.core.run_openai_tool_loop", return_value=fake_response_content) as mock_loop, \
         patch("openai.OpenAI") as mock_openai_cls:
        mock_openai_cls.return_value = MagicMock()
        result = agent._call_openai_wire("system", "query", "xai-key", "https://api.x.ai/v1")

    mock_openai_cls.assert_called_once_with(api_key="xai-key", base_url="https://api.x.ai/v1")
    assert result == fake_response_content
    mock_loop.assert_called_once()
