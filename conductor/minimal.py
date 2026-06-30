"""
Minimal, dependency-light conductor used in cloud or fallback mode.
Supports multiple build profiles selected via CONDUCTOR_BUILD_ID env var.
Builds: auto, solo-google, solo-openai, solo-anthropic, solo-xai,
        pipeline-grok-claude (Grok drafts → Claude refines).
No ChromaDB, no heavy local deps.
"""
import os
from typing import Dict, Any, Iterator, List, Optional
from utils.logger import logger


BUILDS: Dict[str, tuple] = {
    "solo-google":          ("google",    "gemini-1.5-flash"),
    "solo-openai":          ("openai",    "gpt-4o-mini"),
    "solo-anthropic":       ("anthropic", "claude-3-5-haiku-latest"),
    "solo-xai":             ("xai",       "grok-2-latest"),
    "pipeline-grok-claude": ("pipeline",  "grok→claude"),
}

# In-memory conversation store: conversation_id → list of {role, content} dicts
_conversations: Dict[str, List[Dict[str, str]]] = {}


def _provider_for_keys() -> tuple:
    """Pick (provider, model) from CONDUCTOR_BUILD_ID or by key auto-detection."""
    build_id = os.getenv("CONDUCTOR_BUILD_ID", "auto").strip().lower()
    if build_id in BUILDS:
        provider, model = BUILDS[build_id]
        # Validate that required keys exist for the chosen build
        _check_keys_for_build(build_id)
        return provider, model

    # auto-detect from environment
    if os.getenv("GOOGLE_API_KEY"):
        return "google", "gemini-1.5-flash"
    if os.getenv("OPENAI_API_KEY", "").startswith("sk-"):
        return "openai", "gpt-4o-mini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic", "claude-3-5-haiku-latest"
    if os.getenv("XAI_API_KEY"):
        return "xai", "grok-2-latest"
    return "none", "minimal"


def _check_keys_for_build(build_id: str) -> None:
    """Log a warning if a chosen build is missing its required API key(s)."""
    required: Dict[str, List[str]] = {
        "solo-google":          ["GOOGLE_API_KEY"],
        "solo-openai":          ["OPENAI_API_KEY"],
        "solo-anthropic":       ["ANTHROPIC_API_KEY"],
        "solo-xai":             ["XAI_API_KEY"],
        "pipeline-grok-claude": ["XAI_API_KEY", "ANTHROPIC_API_KEY"],
    }
    missing = [k for k in required.get(build_id, []) if not os.getenv(k)]
    if missing:
        logger.warning(f"Build '{build_id}' is missing env vars: {missing}")


def _build_id_from_provider(provider: str) -> str:
    """Reverse-lookup: provider → canonical build ID (for /health reporting)."""
    for bid, (p, _) in BUILDS.items():
        if p == provider:
            return bid
    return "auto"


class MinimalConductor:
    """Cloud-safe conductor. Routes to the configured AI build."""

    def __init__(self):
        self.retriever = None
        self.current_skill = None
        self.skill_manager = None
        self.provider, self.model = _provider_for_keys()
        self.build_id = os.getenv("CONDUCTOR_BUILD_ID", "auto").strip().lower()
        if self.build_id not in BUILDS and self.build_id != "auto":
            self.build_id = "auto"
        logger.info(
            f"MinimalConductor initialized "
            f"(build={self.build_id}, provider={self.provider}, model={self.model})"
        )

    def activate_skill(self, skill_name: str) -> bool:
        return False

    def _system_prompt(self) -> str:
        return "You are Conductor, a helpful voice AI assistant. Be concise and conversational."

    # ------------------------------------------------------------------ #
    #  Provider call helpers                                               #
    # ------------------------------------------------------------------ #

    def _call_google(self, query: str, history: Optional[List] = None) -> str:
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model = genai.GenerativeModel(self.model, system_instruction=self._system_prompt())
        # Gemini doesn't support arbitrary history in the same way; send full query
        resp = model.generate_content(query)
        return resp.text or ""

    def _call_openai(self, query: str, history: Optional[List] = None) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        messages = [{"role": "system", "content": self._system_prompt()}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": query})
        resp = client.chat.completions.create(model=self.model, messages=messages)
        return resp.choices[0].message.content or ""

    def _call_anthropic(self, query: str, history: Optional[List] = None) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        messages = list(history) if history else []
        messages.append({"role": "user", "content": query})
        resp = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=1024,
            system=self._system_prompt(),
            messages=messages,
        )
        return "".join(block.text for block in resp.content if hasattr(block, "text"))

    def _call_xai(self, query: str, history: Optional[List] = None) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["XAI_API_KEY"], base_url="https://api.x.ai/v1")
        messages = [{"role": "system", "content": self._system_prompt()}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": query})
        resp = client.chat.completions.create(model="grok-2-latest", messages=messages)
        return resp.choices[0].message.content or ""

    def _call_pipeline_grok_claude(self, query: str, history: Optional[List] = None) -> str:
        """Grok drafts a raw response; Claude refines it with strategic thinking."""
        grok_draft = self._call_xai(query, history)
        logger.info("Pipeline: Grok draft complete, handing to Claude")
        claude_prompt = (
            f"Here is a draft response to the user's question:\n\n"
            f"User asked: {query}\n\n"
            f"Draft: {grok_draft}\n\n"
            "Please refine this into a polished, strategically-reasoned response. "
            "Keep it concise and conversational."
        )
        return self._call_anthropic(claude_prompt)

    # ------------------------------------------------------------------ #
    #  Routing                                                             #
    # ------------------------------------------------------------------ #

    def _dispatch(self, query: str, history: Optional[List] = None) -> str:
        if self.provider == "google":
            return self._call_google(query, history)
        if self.provider == "openai":
            return self._call_openai(query, history)
        if self.provider == "anthropic":
            return self._call_anthropic(query, history)
        if self.provider == "xai":
            return self._call_xai(query, history)
        if self.provider == "pipeline":
            return self._call_pipeline_grok_claude(query, history)
        return (
            "Minimal mode: no AI provider configured. "
            "Set OPENAI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY, or XAI_API_KEY."
        )

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def chat(
        self,
        query: str,
        platform_filter: str = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        history = _conversations.get(conversation_id) if conversation_id else None

        try:
            text = self._dispatch(query, history)
        except Exception as e:
            logger.error(f"MinimalConductor provider call failed ({self.provider}): {e}")
            text = f"Sorry — the {self.provider} provider failed: {type(e).__name__}: {e}"

        # Persist conversation turn
        if conversation_id is not None:
            turns = _conversations.setdefault(conversation_id, [])
            turns.append({"role": "user", "content": query})
            turns.append({"role": "assistant", "content": text})
            # Cap history at 20 turns to avoid unbounded growth
            if len(turns) > 40:
                _conversations[conversation_id] = turns[-40:]

        return {
            "response": text,
            "sources": [],
            "context_used": 0,
            "model": f"{self.provider}:{self.model}",
            "build_id": self.build_id,
            "conversation_id": conversation_id,
        }

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
        capabilities = ["conversation"]
        if self.provider == "pipeline":
            capabilities.append("pipeline")
        lead = "xai" if self.provider == "pipeline" else self.provider
        return {
            "build_id": self.build_id,
            "lead_provider": lead,
            "active_provider": self.provider,
            "model": self.model,
            "capabilities": capabilities,
        }
