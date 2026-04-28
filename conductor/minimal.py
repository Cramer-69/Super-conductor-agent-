"""
Minimal, dependency-light conductor fallback used in cloud or when no
AI provider is configured. Calls whichever LLM provider has a key set
(Google/Gemini, OpenAI, Anthropic, or xAI/Grok), without ChromaDB.
"""
import os
from pathlib import Path
from typing import Dict, Any, Iterator
from utils.logger import logger

# ---------------------------------------------------------------------------
# Optional SDK imports - use whichever is installed
# ---------------------------------------------------------------------------
try:
    from openai import OpenAI as _OpenAI
    _OPENAI_SDK = True
except ImportError:
    _OPENAI_SDK = False

try:
        import google.generativeai as _genai
    _GOOGLE_SDK = True
except (ImportError, Exception):
    _GOOGLE_SDK = False


class MinimalConductor:
    """Small conductor that calls whichever LLM provider is configured."""

    def __init__(self):
        skills_path = Path(__file__).resolve().parent.parent / "skills"
        try:
            self.skill_manager = SkillManager(skills_path)
        except Exception:
            self.skill_manager = None

        self.retriever = None
        self.current_skill = None

        s = settings.settings if hasattr(settings, "settings") else settings
        self.provider, self.model = self._select_provider(s)
        self._settings = s

        logger.info(f"Initialized MinimalConductor (provider={self.provider}, model={self.model})")

    @staticmethod
    def _select_provider(s):
        if getattr(s, "google_api_key", None):
            return "google", "gemini-1.5-flash"
        if getattr(s, "openai_api_key", None):
            return "openai", "gpt-4o-mini"
        if getattr(s, "anthropic_api_key", None):
            return "anthropic", "claude-3-5-haiku-latest"
        if getattr(s, "xai_api_key", None):
            return "xai", "grok-2-latest"
        return "none", "minimal"

    def activate_skill(self, skill_name: str) -> bool:
        if not self.skill_manager:
            return False
        skill = self.skill_manager.get_skill(skill_name)
        if skill:
            self.current_skill = skill
            logger.info(f"Activated skill (minimal): {skill.name}")
            return True
        return False

    def _system_prompt(self) -> str:
        base = "You are Conductor, a helpful voice AI assistant. Be concise and conversational."
        if self.current_skill:
            try:
                return f"{base}\n\nActive skill: {self.current_skill.name} - {self.current_skill.description}"
            except Exception:
                pass
        return base

    def _call_google(self, query: str) -> str:
        import google.generativeai as genai
        genai.configure(api_key=self._settings.google_api_key)
        model = genai.GenerativeModel(self.model, system_instruction=self._system_prompt())
        resp = model.generate_content(query)
        return resp.text or ""

    def _call_openai(self, query: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self._settings.openai_api_key)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": query},
            ],
        )
        return resp.choices[0].message.content or ""

    def _call_anthropic(self, query: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        resp = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self._system_prompt(),
            messages=[{"role": "user", "content": query}],
        )
        return "".join(block.text for block in resp.content if hasattr(block, "text"))

    def _call_xai(self, query: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self._settings.xai_api_key, base_url="https://api.x.ai/v1")
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": query},
            ],
        )
        return resp.choices[0].message.content or ""

    def chat(self, query: str, platform_filter: str = None) -> Dict[str, Any]:
        try:
            if self.provider == "google":
                text = self._call_google(query)
            elif self.provider == "openai":
                text = self._call_openai(query)
            elif self.provider == "anthropic":
                text = self._call_anthropic(query)
            elif self.provider == "xai":
                text = self._call_xai(query)
            else:
                text = (
                    "Minimal mode: no AI provider configured. "
                    "Set OPENAI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY."
                )
        except Exception as e:
            logger.error(f"MinimalConductor provider call failed ({self.provider}): {e}")
            text = f"Sorry — the {self.provider} provider failed. Check the API key. ({type(e).__name__})"

        return {
            "response": text,
            "sources": [],
            "context_used": 0,
            "model": f"{self.provider}:{self.model}",
        }

    def stream_chat(self, query: str, platform_filter: str = None) -> Iterator[Dict[str, Any]]:
        yield {"type": "sources", "data": []}
        resp = self.chat(query, platform_filter=platform_filter)["response"]
        chunk_size = 120
        for i in range(0, len(resp), chunk_size):
            yield {"type": "content", "data": resp[i : i + chunk_size]}
