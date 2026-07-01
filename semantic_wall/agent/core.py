"""Single Phase-1 agent with memory injection.

Reuses conductor/tool_loop.py's provider completion loops directly (already
built and tested for the sibling Conductor app) rather than reimplementing
per-provider completion calls. No connector tools exist for this agent yet,
so an empty ConnectorRegistry is passed through — the loops simply skip
the tools kwarg and behave as a plain single completion call.
"""

from typing import Any, Dict, List, Optional

from connectors.registry import ConnectorRegistry
from conductor.tool_loop import run_anthropic_tool_loop, run_openai_tool_loop

from semantic_wall.config import settings
from semantic_wall.db.supabase_client import is_configured as memory_is_configured
from semantic_wall.memory.store import search_memories, write_memory

_NO_TOOLS_REGISTRY = ConnectorRegistry([])

AGENT_DESCRIPTIONS = {
    "strategist": "Big-picture business planning, competitive framing, go-to-market synthesis.",
    "coder": "Code generation, debugging, architecture review, PR drafting.",
}


def _provider_for_keys() -> tuple:
    """Pick (provider, model) the same way conductor/minimal.py does —
    respects settings.default_agent_model_provider first if its key is set,
    otherwise falls back to whichever provider has a key configured."""
    preferred = settings.default_agent_model_provider
    if preferred == "anthropic" and settings.anthropic_api_key:
        return "anthropic", settings.default_agent_model
    if preferred == "xai" and settings.xai_api_key:
        return "xai", settings.default_agent_model
    if preferred == "openai" and settings.openai_api_key:
        return "openai", settings.default_agent_model

    if settings.anthropic_api_key:
        return "anthropic", "claude-sonnet-5"
    if settings.xai_api_key:
        return "xai", "grok-2-latest"
    if settings.openai_api_key:
        return "openai", "gpt-4o-mini"
    return "none", "none"


class SemanticWallAgent:
    """The blueprint's Phase 1 single agent, with persistent memory."""

    def __init__(self, agent_id: str = "strategist"):
        self.agent_id = agent_id
        self.provider, self.model = _provider_for_keys()

    def _system_prompt(self, memory_context: str) -> str:
        role = AGENT_DESCRIPTIONS.get(self.agent_id, "A helpful specialist assistant.")
        base = f"You are the {self.agent_id.title()} agent for the Semantic Wall. {role}"
        if memory_context:
            return (
                f"{base}\n\nRelevant memory from this user's past interactions "
                f"(across all agents):\n{memory_context}"
            )
        return base

    def _call_anthropic(self, system_prompt: str, query: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        messages = [{"role": "user", "content": query}]
        return run_anthropic_tool_loop(
            client.messages.create, self.model, system_prompt, messages, [], _NO_TOOLS_REGISTRY, []
        )

    def _call_openai_wire(self, system_prompt: str, query: str, api_key: str, base_url: Optional[str] = None) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]
        return run_openai_tool_loop(
            client.chat.completions.create, self.model, messages, [], _NO_TOOLS_REGISTRY, []
        )

    def chat(self, user_id: str, session_id: str, query: str) -> Dict[str, Any]:
        memory_context = ""
        retrieved: List[Dict[str, Any]] = []

        if memory_is_configured():
            retrieved = search_memories(user_id, query, k=10)
            if retrieved:
                memory_context = "\n---\n".join(
                    f"[{m.get('role', '?')} @ {m.get('created_at', '?')}] {m.get('content', '')}"
                    for m in retrieved
                )

        system_prompt = self._system_prompt(memory_context)

        if self.provider == "anthropic":
            answer = self._call_anthropic(system_prompt, query)
        elif self.provider == "xai":
            answer = self._call_openai_wire(system_prompt, query, settings.xai_api_key, "https://api.x.ai/v1")
        elif self.provider == "openai":
            answer = self._call_openai_wire(system_prompt, query, settings.openai_api_key)
        else:
            answer = (
                "No model provider configured. Set ANTHROPIC_API_KEY, XAI_API_KEY, "
                "or OPENAI_API_KEY for the Semantic Wall service."
            )

        if memory_is_configured():
            write_memory(user_id, self.agent_id, session_id, "user", query)
            write_memory(user_id, self.agent_id, session_id, "assistant", answer)

        return {
            "response": answer,
            "agent_id": self.agent_id,
            "memories_used": len(retrieved),
            "model": f"{self.provider}:{self.model}",
        }
