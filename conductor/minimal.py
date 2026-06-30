"""
Minimal, dependency-light conductor used in cloud or fallback mode.
Calls whichever LLM provider has a key set (OpenAI, Google/Gemini,
Anthropic, or xAI/Grok). No ChromaDB or heavy local dependencies.

OpenAI is the default cloud provider because its Responses API gives this
lightweight deployment durable conversation state and live web search without
requiring an in-container database.
"""
import os
from typing import Dict, Any, Iterator, Optional
from utils.logger import logger


def _provider_for_keys() -> tuple:
    """Pick (provider, model) based on which env var is set."""
    if os.getenv("OPENAI_API_KEY", "").startswith("sk-"):
        return "openai", os.getenv("OPENAI_MODEL", "gpt-5.5")
    if os.getenv("GOOGLE_API_KEY"):
        return "google", os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
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
        logger.info(f"MinimalConductor initialized (provider={self.provider}, model={self.model})")

    def activate_skill(self, skill_name: str) -> bool:
        return False

    def _system_prompt(self) -> str:
        return """
You are Conductor, John Cramer's direct, capable GM partner and voice assistant.
Be concise, conversational, and useful. Do not repeat pleasantries or mirror the
user's words without adding value.

You have live web search and durable conversation context when running through
OpenAI. Search when the user asks for current facts, weather, news, live account
or product information, or anything you cannot verify from conversation
context. Never claim a search occurred unless the tool actually ran.

Be honest about your current boundaries:
- You can hear through the app's speech transcription and speak through TTS.
- You can use live web search and remember this conversation.
- You are not yet connected to John's private Conductor database, email,
  calendar, GitHub actions, Twilio, LiveKit actions, or local files unless a
  tool for that system is explicitly present.
- You cannot inspect your own deployment configuration unless it is included
  in the conversation or exposed through a tool.

When asked what is connected, give a precise capability report instead of a
generic AI disclaimer. Never invent completed actions.
""".strip()

    def _call_google(self, query: str) -> str:
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model = genai.GenerativeModel(self.model, system_instruction=self._system_prompt())
        resp = model.generate_content(query)
        return resp.text or ""

    @staticmethod
    def _openai_sources(response: Any) -> list:
        """Extract URL citations from a Responses API result."""
        sources = []
        seen = set()
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "message":
                continue
            for content in getattr(item, "content", []) or []:
                for annotation in getattr(content, "annotations", []) or []:
                    if getattr(annotation, "type", None) != "url_citation":
                        continue
                    url = getattr(annotation, "url", None)
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    sources.append({
                        "platform": "web",
                        "title": getattr(annotation, "title", None) or url,
                        "url": url,
                    })
        return sources

    def _call_openai(
        self,
        query: str,
        conversation_id: Optional[str] = None,
    ) -> tuple[str, str, list]:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        if not conversation_id:
            conversation_id = client.conversations.create().id

        resp = client.responses.create(
            model=self.model,
            instructions=self._system_prompt(),
            input=query,
            conversation=conversation_id,
            reasoning={"effort": "low"},
            text={"verbosity": "low"},
            tools=[{
                "type": "web_search",
                "search_context_size": "low",
            }],
            tool_choice="auto",
        )
        return (
            resp.output_text or "",
            conversation_id,
            self._openai_sources(resp),
        )

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

    def chat(
        self,
        query: str,
        platform_filter: str = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sources = []
        try:
            if self.provider == "google":
                text = self._call_google(query)
            elif self.provider == "openai":
                text, conversation_id, sources = self._call_openai(
                    query,
                    conversation_id=conversation_id,
                )
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
            text = f"Sorry — the {self.provider} provider failed: {type(e).__name__}: {e}"

        return {
            "response": text,
            "sources": sources,
            "context_used": 0,
            "model": f"{self.provider}:{self.model}",
            "conversation_id": conversation_id,
        }

    def stream_chat(self, query: str, platform_filter: str = None) -> Iterator[Dict[str, Any]]:
        yield {"type": "sources", "data": []}
        resp = self.chat(query, platform_filter=platform_filter)["response"]
        chunk_size = 120
        for i in range(0, len(resp), chunk_size):
            yield {"type": "content", "data": resp[i : i + chunk_size]}
