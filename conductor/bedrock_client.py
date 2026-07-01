"""
Claude on Amazon Bedrock — shared client wrapper.

This is the flagship LLM path for the conductor: Claude, authenticated
through the standard AWS credential chain (IAM role, `aws configure`
profile, or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY env vars) instead of a
bare Anthropic API key. Used by both `ConductorAgent` (local/full mode) and
`MinimalConductor` (cloud mode) so there's one place that knows how to talk
to Bedrock.
"""

import os
from typing import Any, Dict, Iterator, List, Optional

DEFAULT_MODEL_ID = "anthropic.claude-opus-4-8"


def bedrock_credentials_available() -> bool:
    """Best-effort check: can boto3 resolve AWS credentials right now?"""
    try:
        import boto3
    except ImportError:
        return False
    try:
        return boto3.Session().get_credentials() is not None
    except Exception:
        return False


def _make_client(region: str):
    """Construct a Bedrock-backed Anthropic client.

    Prefers the newer Mantle client (Messages-API Bedrock endpoint) and
    falls back to the legacy bedrock-runtime client on older `anthropic`
    SDK versions — both take the same `aws_region` kwarg and expose the
    same `.messages.create` / `.messages.stream` surface.
    """
    try:
        from anthropic import AnthropicBedrockMantle
        return AnthropicBedrockMantle(aws_region=region)
    except ImportError:
        from anthropic import AnthropicBedrock
        return AnthropicBedrock(aws_region=region)


class BedrockClaude:
    """Thin wrapper around Claude on Amazon Bedrock."""

    def __init__(self, region: Optional[str] = None, model: Optional[str] = None):
        self.region = (
            region
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        self.model = model or os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = _make_client(self.region)
        return self._client

    def chat(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 1024,
    ) -> str:
        """Non-streaming completion. Returns the concatenated response text."""
        response = self._get_client().messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return "".join(block.text for block in response.content if hasattr(block, "text"))

    def stream(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        """Streaming completion. Yields response text chunks."""
        with self._get_client().messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            yield from stream.text_stream
