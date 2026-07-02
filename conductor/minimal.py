"""
Minimal, dependency-light conductor used in cloud or fallback mode.
Calls whichever LLM provider has a key set (Google/Gemini, OpenAI,
Anthropic, or xAI/Grok). No ChromaDB, no heavy local deps.
"""
import os
from typing import Dict, Any, Iterator
from utils.logger import logger


def _bedrock_creds_present() -> bool:
    """True if AWS Bedrock has usable credentials in the environment."""
    if os.getenv("AWS_BEARER_TOKEN_BEDROCK"):
        return True
    return bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))


def _provider_for_keys() -> tuple:
    """Pick (provider, model) based on which env var is set."""
    if os.getenv("GOOGLE_API_KEY"):
        return "google", "gemini-1.5-flash"
    if os.getenv("OPENAI_API_KEY", "").startswith("sk-"):
        return "openai", "gpt-4o-mini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic", "claude-3-5-haiku-latest"
    if os.getenv("XAI_API_KEY"):
        return "xai", "grok-2-latest"
    if _bedrock_creds_present():
        return "bedrock", os.getenv(
            "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0"
        )
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

    def _call_bedrock(self, query: str) -> str:
        import boto3

        client_kwargs = {"region_name": os.getenv("AWS_REGION", "us-east-1")}
        # Explicit access-key credentials override the ambient chain. A
        # Bedrock API key (AWS_BEARER_TOKEN_BEDROCK) or an instance role is
        # picked up automatically by boto3 when these are absent.
        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            client_kwargs["aws_access_key_id"] = os.environ["AWS_ACCESS_KEY_ID"]
            client_kwargs["aws_secret_access_key"] = os.environ["AWS_SECRET_ACCESS_KEY"]
            if os.getenv("AWS_SESSION_TOKEN"):
                client_kwargs["aws_session_token"] = os.environ["AWS_SESSION_TOKEN"]

        client = boto3.client("bedrock-runtime", **client_kwargs)
        # The Converse API is model-agnostic across Bedrock providers.
        resp = client.converse(
            modelId=self.model,
            system=[{"text": self._system_prompt()}],
            messages=[{"role": "user", "content": [{"text": query}]}],
            inferenceConfig={"maxTokens": 1024, "temperature": 0.7},
        )
        blocks = resp["output"]["message"]["content"]
        return "".join(b.get("text", "") for b in blocks)

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
            elif self.provider == "bedrock":
                text = self._call_bedrock(query)
            else:
                text = (
                    "Minimal mode: no AI provider configured. "
                    "Set OPENAI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY, "
                    "XAI_API_KEY, or AWS Bedrock credentials "
                    "(AWS_BEARER_TOKEN_BEDROCK or AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY)."
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
