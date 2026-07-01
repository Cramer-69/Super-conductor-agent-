"""
Minimal, dependency-light conductor used in cloud or fallback mode.
Calls whichever LLM provider has a key set (Google/Gemini, OpenAI,
Anthropic, or xAI/Grok). No ChromaDB, no heavy local deps.
"""
import os
from typing import Dict, Any, Iterator
from utils.logger import logger


def _provider_for_keys() -> tuple:
    """Pick (provider, model) based on what's configured.

    Claude on Bedrock is checked first — it's the flagship provider for this
    app (AWS-native auth, no Anthropic API key needed). Falls through to the
    other providers in order if Bedrock isn't configured.
    """
    from conductor.bedrock_client import DEFAULT_MODEL_ID, bedrock_credentials_available

    if (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")) and bedrock_credentials_available():
        return "bedrock", os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic", "claude-opus-4-8"
    if os.getenv("GOOGLE_API_KEY"):
        return "google", "gemini-1.5-flash"
    if os.getenv("OPENAI_API_KEY", "").startswith("sk-"):
        return "openai", "gpt-4o-mini"
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
        logger.info(f"MinimalConductor initialized (provider={self.provider}, model={self.model})")

    def activate_skill(self, skill_name: str) -> bool:
        return False

    def _system_prompt(self) -> str:
        return "You are Conductor, a helpful voice AI assistant. Be concise and conversational."

    def _call_google(self, query: str) -> str:
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model = genai.GenerativeModel(self.model, system_instruction=self._system_prompt())
        resp = model.generate_content(query)
        return resp.text or ""

    def _call_openai(self, query: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
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
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self._system_prompt(),
            messages=[{"role": "user", "content": query}],
        )
        return "".join(block.text for block in resp.content if hasattr(block, "text"))

    def _call_bedrock(self, query: str) -> str:
        from conductor.bedrock_client import BedrockClaude
        client = BedrockClaude(model=self.model)
        return client.chat(
            system=self._system_prompt(),
            messages=[{"role": "user", "content": query}],
        )

    def _call_xai(self, query: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["XAI_API_KEY"], base_url="https://api.x.ai/v1")
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
            if self.provider == "bedrock":
                text = self._call_bedrock(query)
            elif self.provider == "google":
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
                    "Set AWS_REGION (for Claude on Bedrock), OPENAI_API_KEY, "
                    "GOOGLE_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY."
                )
        except Exception as e:
            logger.error(f"MinimalConductor provider call failed ({self.provider}): {e}")
            text = f"Sorry — the {self.provider} provider failed: {type(e).__name__}: {e}"

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
