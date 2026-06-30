"""
Minimal, dependency-light conductor used in cloud or fallback mode.
Instantiates the real SDK adapters and delegates all routing to conductor.kernel.
No ChromaDB, no heavy local deps.
"""
import os
from typing import Dict, Any, Iterator, Optional

from utils.logger import logger
from conductor.kernel import build_kernel, ProviderAdapter


# --------------------------------------------------------------------------- #
#  Real SDK adapters                                                           #
# --------------------------------------------------------------------------- #

class _GoogleAdapter:
    name = "google"

    def complete(self, messages):
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        # Extract system prompt if present
        system = next((m["content"] for m in messages if m["role"] == "system"), None)
        user_turns = [m for m in messages if m["role"] != "system"]
        # Combine history + current query into a single string for Gemini
        text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in user_turns)
        model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system)
        resp = model.generate_content(text)
        return resp.text or ""


class _OpenAIAdapter:
    name = "openai"
    _model = "gpt-4o-mini"

    def complete(self, messages):
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = client.chat.completions.create(model=self._model, messages=messages)
        return resp.choices[0].message.content or ""


class _AnthropicAdapter:
    name = "anthropic"
    _model = "claude-3-5-haiku-latest"

    def complete(self, messages):
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        system = next((m["content"] for m in messages if m["role"] == "system"), None)
        non_system = [m for m in messages if m["role"] != "system"]
        kwargs = dict(
            model=self._model,
            max_tokens=1024,
            messages=non_system,
        )
        if system:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
        return "".join(b.text for b in resp.content if hasattr(b, "text"))


class _XAIAdapter:
    name = "xai"
    _model = "grok-2-latest"

    def complete(self, messages):
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["XAI_API_KEY"], base_url="https://api.x.ai/v1")
        resp = client.chat.completions.create(model=self._model, messages=messages)
        return resp.choices[0].message.content or ""


# --------------------------------------------------------------------------- #
#  Adapter registry                                                            #
# --------------------------------------------------------------------------- #

_ADAPTER_CLASSES = {
    "google":    _GoogleAdapter,
    "openai":    _OpenAIAdapter,
    "anthropic": _AnthropicAdapter,
    "xai":       _XAIAdapter,
}

_KEY_ENV_VARS = {
    "google":    "GOOGLE_API_KEY",
    "openai":    "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "xai":       "XAI_API_KEY",
}


def _build_available_adapters() -> Dict[str, ProviderAdapter]:
    """Return adapters for every provider that has a key set."""
    result = {}
    for name, env_var in _KEY_ENV_VARS.items():
        val = os.getenv(env_var, "")
        if val and not val.startswith("your_"):
            result[name] = _ADAPTER_CLASSES[name]()
    return result


# --------------------------------------------------------------------------- #
#  MinimalConductor                                                            #
# --------------------------------------------------------------------------- #

_SYSTEM_PROMPT = "You are Conductor, a helpful voice AI assistant. Be concise and conversational."


class MinimalConductor:
    """Cloud-safe conductor. Delegates routing to the kernel layer."""

    def __init__(self):
        self.retriever = None
        self.current_skill = None
        self.skill_manager = None

        build_id = os.getenv("CONDUCTOR_BUILD_ID", "auto").strip().lower()
        adapters = _build_available_adapters()

        if not adapters:
            self._kernel = None
            logger.warning("MinimalConductor: no API keys found — responses will be stub text")
        else:
            try:
                self._kernel = build_kernel(build_id, adapters)
                info = self._kernel.get_build_info()
                logger.info(
                    f"MinimalConductor initialized via kernel "
                    f"(build={info['build_id']}, lead={info['lead_provider']}, "
                    f"model={info['model']})"
                )
            except ValueError as exc:
                logger.error(f"MinimalConductor: kernel setup failed — {exc}")
                self._kernel = None

    def activate_skill(self, skill_name: str) -> bool:
        return False

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def chat(
        self,
        query: str,
        platform_filter: str = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._kernel is None:
            return {
                "response": (
                    "Minimal mode: no AI provider configured. "
                    "Set OPENAI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY, or XAI_API_KEY."
                ),
                "sources": [],
                "context_used": 0,
                "model": "none:minimal",
                "build_id": "none",
                "conversation_id": conversation_id,
            }

        try:
            result = self._kernel.run(
                query,
                system_prompt=_SYSTEM_PROMPT,
                conversation_id=conversation_id,
            )
        except Exception as exc:
            logger.error(f"MinimalConductor kernel.run failed: {exc}")
            result = {
                "response": f"Sorry, an error occurred: {type(exc).__name__}: {exc}",
                "sources": [],
                "context_used": 0,
                "evidence": [],
                "build_id": "error",
                "model": "none:error",
                "conversation_id": conversation_id,
            }

        result.setdefault("sources", [])
        result.setdefault("context_used", 0)
        return result

    def stream_chat(
        self,
        query: str,
        platform_filter: str = None,
        conversation_id: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        yield {"type": "sources", "data": []}
        result = self.chat(query, platform_filter=platform_filter, conversation_id=conversation_id)
        resp = result["response"]
        chunk_size = 120
        for i in range(0, len(resp), chunk_size):
            yield {"type": "content", "data": resp[i : i + chunk_size]}

    # ------------------------------------------------------------------ #
    #  Introspection (used by /health)                                     #
    # ------------------------------------------------------------------ #

    def get_build_info(self) -> Dict[str, Any]:
        if self._kernel is None:
            return {
                "build_id": "none",
                "lead_provider": "none",
                "active_provider": "none",
                "model": "none",
                "capabilities": [],
            }
        return self._kernel.get_build_info()
