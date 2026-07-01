"""Base interface for connectors that inject live context into chat()."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple


class Connector(ABC):
    """A connector fetches live context from an external service for a query."""

    name: str = "connector"

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether the credentials/settings needed to call the service are present."""

    @abstractmethod
    def should_handle(self, query: str) -> bool:
        """Whether this connector is relevant to the given query."""

    @abstractmethod
    def fetch_context(self, query: str) -> Tuple[str, Dict[str, Any]]:
        """Fetch context for the query.

        Returns:
            (context_text, source_metadata) — context_text is spliced into the
            LLM prompt the same way retrieved conversation context is;
            source_metadata is appended to the response's `sources` list.
        """
