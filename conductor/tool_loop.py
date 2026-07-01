"""Provider-agnostic pieces of the one-round tool-calling flow.

Each provider's chat code builds its own request/response plumbing (SDK
shapes differ too much to unify the whole loop), but they all:
  1. build tool specs from ConnectorRegistry.tool_specs() via an adapter here
  2. dispatch a resolved tool call through resolve_tool_call() here
  3. append the resulting source dict to `sources`

This module has no top-level SDK imports, so it's importable/testable with
none of the optional LLM SDKs installed (run_gemini_tool_loop lazily imports
google.genai inside the function body, same pattern as conductor/minimal.py).
"""

import json
from typing import Any, Callable, Dict, List, Optional

from connectors.registry import ConnectorRegistry


def _safe_json_object(raw: Optional[str]) -> Dict[str, Any]:
    """Parse a model-provided tool-call arguments string defensively.

    The model can produce malformed JSON (or valid JSON that isn't an
    object) for `arguments` — never let that raise into the request path;
    fall back to an empty dict so it's handled via the normal tool-error
    path instead of crashing the whole chat.
    """
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def to_openai_tools(tool_specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Wrap generic tool specs in OpenAI's function-calling envelope.

    Used as-is for openai, grok, and xai (all OpenAI-wire-compatible).
    """
    return [
        {
            "type": "function",
            "function": {
                "name": spec["name"],
                "description": spec["description"],
                "parameters": spec["parameters"],
            },
        }
        for spec in tool_specs
    ]


def to_anthropic_tools(tool_specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "name": spec["name"],
            "description": spec["description"],
            "input_schema": spec["parameters"],
        }
        for spec in tool_specs
    ]


def to_gemini_tools(tool_specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Returns the `tools=[...]` value for google-genai's GenerateContentConfig.

    Plain dicts (no google.genai import needed here) — the SDK's pydantic
    models accept this shape directly. `parameters_json_schema` (not
    `parameters`) is the field that takes a raw JSON Schema dict as-is.
    """
    return [
        {
            "function_declarations": [
                {
                    "name": spec["name"],
                    "description": spec["description"],
                    "parameters_json_schema": spec["parameters"],
                }
                for spec in tool_specs
            ]
        }
    ]


def resolve_tool_call(
    registry: ConnectorRegistry,
    name: str,
    arguments: Dict[str, Any],
    sources: List[Dict[str, Any]],
    tool_chars: Optional[List[int]] = None,
) -> str:
    """Execute one tool call via the registry, record its source, return result text.

    If `tool_chars` is given, appends len(result_text) to it — used to report
    how much live tool context (as opposed to canned context) informed the
    answer, replacing the old "chars of connector context spliced in" metric.
    """
    result_text, source = registry.call_tool(name, arguments)
    sources.append(source)
    if tool_chars is not None:
        tool_chars.append(len(result_text))
    return result_text


def run_openai_tool_loop(
    create: Callable[..., Any],
    model: str,
    messages: List[Dict[str, Any]],
    tool_specs: List[Dict[str, Any]],
    registry: ConnectorRegistry,
    sources: List[Dict[str, Any]],
    tool_chars: Optional[List[int]] = None,
    **create_kwargs: Any,
) -> str:
    """One-round tool loop for any OpenAI-SDK-shaped `create` callable
    (openai.OpenAI().chat.completions.create, or the same pointed at
    xAI's base_url — both have this identical call/response shape).
    """
    kwargs: Dict[str, Any] = dict(model=model, messages=messages, **create_kwargs)
    if tool_specs:
        kwargs["tools"] = to_openai_tools(tool_specs)
        kwargs["tool_choice"] = "auto"

    response = create(**kwargs)
    message = response.choices[0].message

    if tool_specs and getattr(message, "tool_calls", None):
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [tc.model_dump() for tc in message.tool_calls],
            }
        )
        for tc in message.tool_calls:
            args = _safe_json_object(tc.function.arguments)
            result_text = resolve_tool_call(registry, tc.function.name, args, sources, tool_chars)
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": result_text}
            )
        follow_up = create(model=model, messages=messages, **create_kwargs)
        return follow_up.choices[0].message.content

    return message.content


def run_openai_rest_tool_loop(
    post: Callable[..., Any],
    model: str,
    messages: List[Dict[str, Any]],
    tool_specs: List[Dict[str, Any]],
    registry: ConnectorRegistry,
    sources: List[Dict[str, Any]],
    tool_chars: Optional[List[int]] = None,
    **payload_kwargs: Any,
) -> str:
    """One-round tool loop for raw-REST OpenAI-wire-compatible APIs (grok's
    httpx.Client.post), where responses are plain dicts, not SDK objects.
    """
    payload: Dict[str, Any] = dict(model=model, messages=messages, **payload_kwargs)
    if tool_specs:
        payload["tools"] = to_openai_tools(tool_specs)
        payload["tool_choice"] = "auto"

    response = post("/chat/completions", json=payload).json()
    message = response["choices"][0]["message"]
    tool_calls = message.get("tool_calls")

    if tool_specs and tool_calls:
        # Build the assistant turn explicitly rather than re-appending the
        # raw response message — not every OpenAI-wire-compatible provider
        # is guaranteed to include `role` on the message or `type:
        # "function"` on each tool call the way OpenAI's own API does, and
        # a missing field here would make the follow-up request invalid.
        normalized_tool_calls = [
            {
                "id": tc["id"],
                "type": tc.get("type", "function"),
                "function": tc["function"],
            }
            for tc in tool_calls
        ]
        messages.append(
            {
                "role": "assistant",
                "content": message.get("content"),
                "tool_calls": normalized_tool_calls,
            }
        )
        for tc in tool_calls:
            args = _safe_json_object(tc["function"]["arguments"])
            result_text = resolve_tool_call(registry, tc["function"]["name"], args, sources, tool_chars)
            messages.append(
                {"role": "tool", "tool_call_id": tc["id"], "content": result_text}
            )
        follow_up = post(
            "/chat/completions",
            json=dict(model=model, messages=messages, **payload_kwargs),
        ).json()
        return follow_up["choices"][0]["message"]["content"]

    return message["content"]


def run_anthropic_tool_loop(
    create: Callable[..., Any],
    model: str,
    system: str,
    messages: List[Dict[str, Any]],
    tool_specs: List[Dict[str, Any]],
    registry: ConnectorRegistry,
    sources: List[Dict[str, Any]],
    tool_chars: Optional[List[int]] = None,
    max_tokens: int = 1024,
) -> str:
    """One-round tool loop for anthropic.Anthropic().messages.create."""
    kwargs: Dict[str, Any] = dict(model=model, max_tokens=max_tokens, system=system, messages=messages)
    if tool_specs:
        kwargs["tools"] = to_anthropic_tools(tool_specs)

    response = create(**kwargs)
    tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

    if tool_specs and tool_use_blocks:
        messages.append({"role": "assistant", "content": response.content})

        tool_result_blocks = []
        for block in tool_use_blocks:
            result_text = resolve_tool_call(registry, block.name, block.input, sources, tool_chars)
            tool_result_blocks.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result_text}
            )
        # All tool_result blocks for this turn go in a single user message.
        messages.append({"role": "user", "content": tool_result_blocks})

        follow_up = create(model=model, max_tokens=max_tokens, system=system, messages=messages)
        return "".join(b.text for b in follow_up.content if hasattr(b, "text"))

    return "".join(b.text for b in response.content if hasattr(b, "text"))


def run_gemini_tool_loop(
    chat: Any,
    message: Any,
    tool_specs: List[Dict[str, Any]],
    registry: ConnectorRegistry,
    sources: List[Dict[str, Any]],
    tool_chars: Optional[List[int]] = None,
) -> str:
    """One-round tool loop for a google-genai `chat` session (client.chats.create(...)).

    `chat` must already be configured with `tools=to_gemini_tools(...)` on its
    GenerateContentConfig — this function only drives the send/inspect/
    respond cycle. Lazily imports google.genai so this module stays
    importable with no LLM SDKs installed.
    """
    from google.genai import types

    response = chat.send_message(message)
    function_calls = response.function_calls  # None or list[FunctionCall]

    if tool_specs and function_calls:
        response_parts = []
        for fc in function_calls:
            result_text = resolve_tool_call(registry, fc.name, fc.args or {}, sources, tool_chars)
            response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name, response={"result": result_text}
                    )
                )
            )
        follow_up = chat.send_message(response_parts)
        return follow_up.text or ""

    return response.text or ""
