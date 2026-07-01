"""Base interface for connectors that expose LLM-callable tools."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple


class Connector(ABC):
    """A connector exposes one or more tools the LLM can choose to call."""

    name: str = "connector"

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether the credentials/settings needed to call the service are present."""

    @abstractmethod
    def tool_specs(self) -> List[Dict[str, Any]]:
        """Describe this connector's tools in a provider-agnostic shape.

        Each entry:
            {
                "name": "get_my_github_activity",
                "description": "...",
                "parameters": {   # JSON Schema, "object" type
                    "type": "object",
                    "properties": {...},
                    "required": [...],
                },
            }
        """

    @abstractmethod
    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Execute the named tool with the given arguments.

        Returns:
            (result_text, source_metadata) — result_text is fed back to the LLM
            as the tool result; source_metadata is appended to the response's
            `sources` list.
        """
