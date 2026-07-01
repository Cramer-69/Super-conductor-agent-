"""Registry that gathers context from whichever connectors apply to a query."""

from typing import Any, Dict, List, Tuple

from connectors.base import Connector
from utils.logger import logger


class ConnectorRegistry:
    """Holds connectors and collects context from the ones relevant to a query."""

    def __init__(self, connectors: List[Connector]):
        self.connectors = connectors

    def gather(self, query: str) -> List[Tuple[str, Dict[str, Any]]]:
        results = []
        for connector in self.connectors:
            if not connector.is_configured() or not connector.should_handle(query):
                continue
            try:
                results.append(connector.fetch_context(query))
            except Exception as e:
                logger.exception(f"Connector '{connector.name}' raised unexpectedly: {e}")
        return results
