"""Registry that aggregates tool specs and dispatches tool calls to connectors."""

import logging
from typing import Any, Dict, List, Tuple

from connectors.base import Connector

# Plain stdlib logging (not utils.logger) — this package is reused by
# semantic_wall/ (see agent/core.py), which doesn't want the sibling app's
# rich/config.settings dependency chain just to use ConnectorRegistry.
logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """Holds connectors, exposes their tools, and dispatches tool calls."""

    def __init__(self, connectors: List[Connector]):
        self.connectors = connectors

    def active_connectors(self) -> List[Connector]:
        return [c for c in self.connectors if c.is_configured()]

    def tool_specs(self) -> List[Dict[str, Any]]:
        """All tool specs from configured connectors, flattened."""
        specs = []
        for connector in self.active_connectors():
            specs.extend(connector.tool_specs())
        return specs

    def has_tools(self) -> bool:
        return bool(self.tool_specs())

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Find the connector owning `name` and execute it."""
        for connector in self.active_connectors():
            spec_names = {spec["name"] for spec in connector.tool_specs()}
            if name in spec_names:
                try:
                    return connector.call_tool(name, arguments)
                except Exception as e:
                    logger.exception(f"Connector '{connector.name}' tool '{name}' raised: {e}")
                    return (
                        f"Tool '{name}' failed: {e}",
                        {"platform": connector.name, "title": f"{connector.name} (error)"},
                    )
        logger.warning(f"No connector owns tool '{name}'")
        return (f"Tool '{name}' is not available.", {"platform": "unknown", "title": "Unknown tool"})
