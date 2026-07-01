"""Tests for connectors/registry.py."""

from connectors.base import Connector
from connectors.registry import ConnectorRegistry


class FakeConnectorA(Connector):
    name = "a"

    def __init__(self, configured=True):
        self._configured = configured

    def is_configured(self):
        return self._configured

    def tool_specs(self):
        return [{"name": "tool_a", "description": "d", "parameters": {"type": "object", "properties": {}}}]

    def call_tool(self, name, arguments):
        return "result from a", {"platform": "a", "title": "A"}


class FakeConnectorB(Connector):
    name = "b"

    def is_configured(self):
        return True

    def tool_specs(self):
        return [{"name": "tool_b", "description": "d", "parameters": {"type": "object", "properties": {}}}]

    def call_tool(self, name, arguments):
        raise RuntimeError("boom")


def test_tool_specs_aggregates_only_configured_connectors():
    registry = ConnectorRegistry([FakeConnectorA(configured=False), FakeConnectorB()])
    specs = registry.tool_specs()
    assert [s["name"] for s in specs] == ["tool_b"]
    assert registry.has_tools() is True


def test_has_tools_false_when_nothing_configured():
    registry = ConnectorRegistry([FakeConnectorA(configured=False)])
    assert registry.has_tools() is False
    assert registry.tool_specs() == []


def test_call_tool_dispatches_to_owning_connector():
    registry = ConnectorRegistry([FakeConnectorA(), FakeConnectorB()])
    text, source = registry.call_tool("tool_a", {})
    assert text == "result from a"
    assert source == {"platform": "a", "title": "A"}


def test_call_tool_unknown_name_returns_graceful_message():
    registry = ConnectorRegistry([FakeConnectorA()])
    text, source = registry.call_tool("nonexistent", {})
    assert "not available" in text
    assert source["platform"] == "unknown"


def test_call_tool_swallows_connector_exception():
    registry = ConnectorRegistry([FakeConnectorB()])
    text, source = registry.call_tool("tool_b", {})
    assert "failed" in text
    assert source["title"] == "b (error)"
