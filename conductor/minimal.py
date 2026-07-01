"""
Minimal, dependency-light conductor used in cloud or fallback mode.
Calls whichever LLM provider has a key set (Google/Gemini, OpenAI,
Anthropic, or xAI/Grok). No ChromaDB, no heavy local deps.
"""
import os
from typing import Any, Dict, Iterator, List

from utils.logger import logger
from connectors.registry import ConnectorRegistry
from connectors.github_connector import GitHubConnector
from conductor.tool_loop import run_anthropic_tool_loop, run_gemini_tool_loop, run_openai_tool_loop, to_gemini_tools


def _provider_for_keys() -> tuple:
    """Pick (provider, model) based on which env var is set."""
    if os.getenv("GOOGLE_API_KEY"):
        return "google", "gemini-2.5-flash"
    if os.getenv("OPENAI_API_KEY", "").startswith("sk-"):
        return "openai", "gpt-4o-mini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic", "claude-3-5-haiku-latest"
    if os.getenv("XAI_API_KEY"):
        return "xai", "grok-2-latest"
    return "none", "minimal"


class MinimalConductor:
    """Cloud-safe conductor. Calls whichever AI provider is configured."""

    def __init__(self):
        self.retriever = None
        self.current_skill = None
        self.skill_manager = None
        self.provider, self.model = _provider_for_keys()
        self.connector_registry = ConnectorRegistry([GitHubConnector()])
        logger.info(f"MinimalConductor initialized (provider={self.provider}, model={self.model})")

    def activate_skill(self, skill_name: str) -> bool:
        return False

    def _system_prompt(self) -> str:
        return "You are Conductor, a helpful voice AI assistant. Be concise and conversational."

    def _call_google(self, query: str, sources: List[Dict[str, Any]], tool_chars: List[int]) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        tool_specs = self.connector_registry.tool_specs()
        config = types.GenerateContentConfig(
            system_instruction=self._system_prompt(),
            tools=to_gemini_tools(tool_specs) if tool_specs else None,
        )
        chat = client.chats.create(model=self.model, config=config)
        return run_gemini_tool_loop(chat, query, tool_specs, self.connector_registry, sources, tool_chars)

    def _call_openai(self, query: str, sources: List[Dict[str, Any]], tool_chars: List[int]) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": query},
        ]
        return run_openai_tool_loop(
            client.chat.completions.create,
            self.model,
            messages,
            self.connector_registry.tool_specs(),
            self.connector_registry,
            sources,
            tool_chars,
        )

    def _call_anthropic(self, query: str, sources: List[Dict[str, Any]], tool_chars: List[int]) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        messages = [{"role": "user", "content": query}]
        return run_anthropic_tool_loop(
            client.messages.create,
            self.model,
            self._system_prompt(),
            messages,
            self.connector_registry.tool_specs(),
            self.connector_registry,
            sources,
            tool_chars,
        )

    def _call_xai(self, query: str, sources: List[Dict[str, Any]], tool_chars: List[int]) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["XAI_API_KEY"], base_url="https://api.x.ai/v1")
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": query},
        ]
        return run_openai_tool_loop(
            client.chat.completions.create,
            self.model,
            messages,
            self.connector_registry.tool_specs(),
            self.connector_registry,
            sources,
            tool_chars,
        )

    def chat(self, query: str, platform_filter: str = None) -> Dict[str, Any]:
        sources: List[Dict[str, Any]] = []
        tool_chars: List[int] = []

        try:
            if self.provider == "google":
                text = self._call_google(query, sources, tool_chars)
            elif self.provider == "openai":
                text = self._call_openai(query, sources, tool_chars)
            elif self.provider == "anthropic":
                text = self._call_anthropic(query, sources, tool_chars)
            elif self.provider == "xai":
                text = self._call_xai(query, sources, tool_chars)
            else:
                text = (
                    "Minimal mode: no AI provider configured. "
                    "Set OPENAI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY."
                )
        except Exception as e:
            logger.error(f"MinimalConductor provider call failed ({self.provider}): {e}")
            text = f"Sorry — the {self.provider} provider failed: {type(e).__name__}: {e}"

        return {
            "response": text,
            "sources": sources,
            "context_used": sum(tool_chars),
            "model": f"{self.provider}:{self.model}",
        }

    def stream_chat(self, query: str, platform_filter: str = None) -> Iterator[Dict[str, Any]]:
        result = self.chat(query, platform_filter=platform_filter)
        yield {"type": "sources", "data": result["sources"]}
        resp = result["response"]
        chunk_size = 120
        for i in range(0, len(resp), chunk_size):
            yield {"type": "content", "data": resp[i : i + chunk_size]}
