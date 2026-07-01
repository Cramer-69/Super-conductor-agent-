"""Tests for conductor/tool_loop.py — no LLM SDKs required."""

from types import SimpleNamespace

from connectors.base import Connector
from connectors.registry import ConnectorRegistry
from conductor.tool_loop import (
    resolve_tool_call,
    run_anthropic_tool_loop,
    run_gemini_tool_loop,
    run_openai_rest_tool_loop,
    run_openai_tool_loop,
    to_anthropic_tools,
    to_gemini_tools,
    to_openai_tools,
)


class FakeConnector(Connector):
    name = "fake"

    def is_configured(self):
        return True

    def tool_specs(self):
        return [
            {
                "name": "fake_tool",
                "description": "A fake tool for testing.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            }
        ]

    def call_tool(self, name, arguments):
        return "fake result", {"platform": "fake", "title": "Fake"}


def make_registry():
    return ConnectorRegistry([FakeConnector()])


def test_to_openai_tools_shape():
    specs = [{"name": "n", "description": "d", "parameters": {"type": "object"}}]
    wrapped = to_openai_tools(specs)
    assert wrapped == [
        {"type": "function", "function": {"name": "n", "description": "d", "parameters": {"type": "object"}}}
    ]


def test_to_anthropic_tools_shape():
    specs = [{"name": "n", "description": "d", "parameters": {"type": "object"}}]
    wrapped = to_anthropic_tools(specs)
    assert wrapped == [{"name": "n", "description": "d", "input_schema": {"type": "object"}}]


def test_to_gemini_tools_shape():
    specs = [{"name": "n", "description": "d", "parameters": {"type": "object"}}]
    wrapped = to_gemini_tools(specs)
    assert wrapped == [
        {"function_declarations": [{"name": "n", "description": "d", "parameters_json_schema": {"type": "object"}}]}
    ]


def test_resolve_tool_call_appends_source_and_chars():
    registry = make_registry()
    sources = []
    tool_chars = []
    result = resolve_tool_call(registry, "fake_tool", {}, sources, tool_chars)
    assert result == "fake result"
    assert sources == [{"platform": "fake", "title": "Fake"}]
    assert tool_chars == [len("fake result")]


def _openai_tool_call(call_id="call_1", name="fake_tool", args="{}"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=args),
        model_dump=lambda: {"id": call_id, "type": "function", "function": {"name": name, "arguments": args}},
    )


def test_run_openai_tool_loop_no_tool_call():
    registry = make_registry()
    sources = []

    def create(**kwargs):
        assert "tools" in kwargs  # tools offered since connector is configured
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="direct answer", tool_calls=None))])

    answer = run_openai_tool_loop(create, "model", [{"role": "user", "content": "hi"}], registry.tool_specs(), registry, sources)
    assert answer == "direct answer"
    assert sources == []


def test_run_openai_tool_loop_with_tool_call():
    registry = make_registry()
    sources = []
    responses = [
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[_openai_tool_call()]))]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="final answer", tool_calls=None))]),
    ]

    def create(**kwargs):
        return responses.pop(0)

    answer = run_openai_tool_loop(create, "model", [{"role": "user", "content": "hi"}], registry.tool_specs(), registry, sources)
    assert answer == "final answer"
    assert sources == [{"platform": "fake", "title": "Fake"}]


def test_run_openai_tool_loop_malformed_arguments_json_does_not_crash():
    registry = make_registry()
    sources = []
    responses = [
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[_openai_tool_call(args="{not valid json")]))]
        ),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="final answer", tool_calls=None))]),
    ]

    def create(**kwargs):
        return responses.pop(0)

    answer = run_openai_tool_loop(create, "model", [{"role": "user", "content": "hi"}], registry.tool_specs(), registry, sources)
    assert answer == "final answer"
    assert sources == [{"platform": "fake", "title": "Fake"}]


def test_run_openai_tool_loop_two_tool_calls_one_turn():
    registry = make_registry()
    sources = []
    two_calls = [_openai_tool_call("call_1"), _openai_tool_call("call_2")]
    responses = [
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=two_calls))]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="final answer", tool_calls=None))]),
    ]
    seen_messages = []

    def create(**kwargs):
        seen_messages.append(kwargs["messages"])
        return responses.pop(0)

    answer = run_openai_tool_loop(create, "model", [{"role": "user", "content": "hi"}], registry.tool_specs(), registry, sources)
    assert answer == "final answer"
    assert len(sources) == 2
    tool_messages = [m for m in seen_messages[-1] if m.get("role") == "tool"]
    assert len(tool_messages) == 2
    assert {m["tool_call_id"] for m in tool_messages} == {"call_1", "call_2"}


def test_run_openai_rest_tool_loop_with_tool_call():
    registry = make_registry()
    sources = []
    responses = [
        {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_1", "function": {"name": "fake_tool", "arguments": "{}"}}
        ]}}]},
        {"choices": [{"message": {"role": "assistant", "content": "final answer"}}]},
    ]

    class FakeResp:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

    def post(url, json):
        return FakeResp(responses.pop(0))

    answer = run_openai_rest_tool_loop(post, "model", [{"role": "user", "content": "hi"}], registry.tool_specs(), registry, sources)
    assert answer == "final answer"
    assert sources == [{"platform": "fake", "title": "Fake"}]


def test_run_openai_rest_tool_loop_malformed_arguments_json_does_not_crash():
    registry = make_registry()
    sources = []
    responses = [
        {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_1", "function": {"name": "fake_tool", "arguments": "{not valid json"}}
        ]}}]},
        {"choices": [{"message": {"role": "assistant", "content": "final answer"}}]},
    ]

    class FakeResp:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

    def post(url, json):
        return FakeResp(responses.pop(0))

    answer = run_openai_rest_tool_loop(post, "model", [{"role": "user", "content": "hi"}], registry.tool_specs(), registry, sources)
    assert answer == "final answer"
    assert sources == [{"platform": "fake", "title": "Fake"}]


def _anthropic_tool_use_block(block_id="tu_1", name="fake_tool", tool_input=None):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input or {})


def test_run_anthropic_tool_loop_with_tool_use():
    registry = make_registry()
    sources = []
    responses = [
        SimpleNamespace(content=[_anthropic_tool_use_block()]),
        SimpleNamespace(content=[SimpleNamespace(type="text", text="final answer")]),
    ]
    seen_messages = []

    def create(**kwargs):
        seen_messages.append(kwargs["messages"])
        return responses.pop(0)

    answer = run_anthropic_tool_loop(
        create, "model", "system prompt", [{"role": "user", "content": "hi"}], registry.tool_specs(), registry, sources
    )
    assert answer == "final answer"
    assert sources == [{"platform": "fake", "title": "Fake"}]
    # The tool_result must be bundled into a single user message.
    last_call_messages = seen_messages[-1]
    tool_result_messages = [m for m in last_call_messages if m.get("role") == "user" and isinstance(m.get("content"), list)]
    assert len(tool_result_messages) == 1
    assert len(tool_result_messages[0]["content"]) == 1


def test_run_anthropic_tool_loop_no_tool_use():
    registry = make_registry()
    sources = []

    def create(**kwargs):
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="direct answer")])

    answer = run_anthropic_tool_loop(
        create, "model", "system prompt", [{"role": "user", "content": "hi"}], registry.tool_specs(), registry, sources
    )
    assert answer == "direct answer"
    assert sources == []


def _gemini_function_call(name="fake_tool", args=None):
    return SimpleNamespace(name=name, args=args if args is not None else {})


class FakeGeminiChat:
    def __init__(self, responses):
        self._responses = list(responses)
        self.sent = []

    def send_message(self, message):
        self.sent.append(message)
        return self._responses.pop(0)


def test_run_gemini_tool_loop_with_function_call():
    registry = make_registry()
    sources = []
    chat = FakeGeminiChat(
        [
            SimpleNamespace(function_calls=[_gemini_function_call()], text=None),
            SimpleNamespace(function_calls=None, text="final answer"),
        ]
    )

    answer = run_gemini_tool_loop(chat, "hello", registry.tool_specs(), registry, sources)
    assert answer == "final answer"
    assert sources == [{"platform": "fake", "title": "Fake"}]
    assert len(chat.sent) == 2


def test_run_gemini_tool_loop_no_function_call():
    registry = make_registry()
    sources = []
    chat = FakeGeminiChat([SimpleNamespace(function_calls=None, text="direct answer")])

    answer = run_gemini_tool_loop(chat, "hello", registry.tool_specs(), registry, sources)
    assert answer == "direct answer"
    assert sources == []
    assert len(chat.sent) == 1
