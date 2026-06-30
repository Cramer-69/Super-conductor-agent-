"""
Provider-agnostic routing kernel for Conductor.

Three kernel types:
  SoloKernel     — single provider
  PipelineKernel — provider A drafts, provider B refines
  CouncilKernel  — N providers fan out; lead provider synthesizes

All kernels share:
  - In-memory conversation history (keyed by conversation_id, capped at 40 msgs)
  - Evidence capture: every provider call recorded in the returned result
  - No live API calls — real adapters are injected; tests use MockAdapter
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


# --------------------------------------------------------------------------- #
#  Adapter protocol — real SDKs and MockAdapter both implement this            #
# --------------------------------------------------------------------------- #

@runtime_checkable
class ProviderAdapter(Protocol):
    """Minimal interface every provider adapter must satisfy."""

    name: str  # e.g. "google", "openai", "anthropic", "xai"

    def complete(self, messages: List[Dict[str, str]]) -> str:
        """Send messages and return the assistant's reply text."""
        ...


# --------------------------------------------------------------------------- #
#  In-memory conversation store (shared across all kernel instances)           #
# --------------------------------------------------------------------------- #

_conversations: Dict[str, List[Dict[str, str]]] = {}
_MAX_HISTORY = 40  # total messages stored per conversation_id


def _get_history(conversation_id: Optional[str]) -> List[Dict[str, str]]:
    if conversation_id is None:
        return []
    return list(_conversations.get(conversation_id, []))


def _save_turn(
    conversation_id: Optional[str],
    user_text: str,
    assistant_text: str,
) -> None:
    if conversation_id is None:
        return
    turns = _conversations.setdefault(conversation_id, [])
    turns.append({"role": "user", "content": user_text})
    turns.append({"role": "assistant", "content": assistant_text})
    if len(turns) > _MAX_HISTORY:
        _conversations[conversation_id] = turns[-_MAX_HISTORY:]


def clear_history(conversation_id: str) -> None:
    """Remove stored history for a given conversation (useful for tests)."""
    _conversations.pop(conversation_id, None)


# --------------------------------------------------------------------------- #
#  Result type                                                                 #
# --------------------------------------------------------------------------- #

def _result(
    response: str,
    evidence: List[Dict[str, str]],
    build_id: str,
    provider: str,
    model: str,
    conversation_id: Optional[str],
) -> Dict[str, Any]:
    return {
        "response": response,
        "sources": [],
        "context_used": 0,
        "evidence": evidence,
        "build_id": build_id,
        "model": f"{provider}:{model}",
        "conversation_id": conversation_id,
    }


# --------------------------------------------------------------------------- #
#  SoloKernel                                                                  #
# --------------------------------------------------------------------------- #

class SoloKernel:
    """Routes every query to one ProviderAdapter."""

    def __init__(self, adapter: ProviderAdapter, build_id: str, model: str = ""):
        self.adapter = adapter
        self.build_id = build_id
        self.model = model or adapter.name

    def run(
        self,
        query: str,
        system_prompt: str = "",
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        history = _get_history(conversation_id)
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": query})

        text = self.adapter.complete(messages)
        evidence = [{"provider": self.adapter.name, "text": text}]
        _save_turn(conversation_id, query, text)
        return _result(text, evidence, self.build_id, self.adapter.name, self.model, conversation_id)

    def get_build_info(self) -> Dict[str, Any]:
        return {
            "build_id": self.build_id,
            "lead_provider": self.adapter.name,
            "active_provider": self.adapter.name,
            "model": self.model,
            "capabilities": ["conversation"],
        }


# --------------------------------------------------------------------------- #
#  PipelineKernel                                                              #
# --------------------------------------------------------------------------- #

class PipelineKernel:
    """Calls draft_adapter, then passes the draft to refine_adapter."""

    def __init__(
        self,
        draft_adapter: ProviderAdapter,
        refine_adapter: ProviderAdapter,
        build_id: str = "pipeline",
        model: str = "",
    ):
        self.draft_adapter = draft_adapter
        self.refine_adapter = refine_adapter
        self.build_id = build_id
        self.model = model or f"{draft_adapter.name}→{refine_adapter.name}"

    def run(
        self,
        query: str,
        system_prompt: str = "",
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        history = _get_history(conversation_id)
        base: List[Dict[str, str]] = []
        if system_prompt:
            base.append({"role": "system", "content": system_prompt})
        base.extend(history)

        # Step 1: draft
        draft_messages = base + [{"role": "user", "content": query}]
        draft = self.draft_adapter.complete(draft_messages)

        # Step 2: refine
        refine_prompt = (
            f"The user asked: {query}\n\n"
            f"Here is a draft response:\n{draft}\n\n"
            "Please refine this into a polished, strategically-reasoned reply. "
            "Be concise and conversational."
        )
        refine_messages = base + [{"role": "user", "content": refine_prompt}]
        refined = self.refine_adapter.complete(refine_messages)

        evidence = [
            {"provider": self.draft_adapter.name, "text": draft},
            {"provider": self.refine_adapter.name, "text": refined},
        ]
        _save_turn(conversation_id, query, refined)
        return _result(
            refined, evidence, self.build_id,
            self.refine_adapter.name, self.model, conversation_id,
        )

    def get_build_info(self) -> Dict[str, Any]:
        return {
            "build_id": self.build_id,
            "lead_provider": self.draft_adapter.name,
            "active_provider": f"{self.draft_adapter.name}+{self.refine_adapter.name}",
            "model": self.model,
            "capabilities": ["pipeline", "conversation"],
        }


# --------------------------------------------------------------------------- #
#  CouncilKernel                                                               #
# --------------------------------------------------------------------------- #

class CouncilKernel:
    """Fans out to N adapters; lead adapter synthesizes all responses."""

    def __init__(
        self,
        adapters: List[ProviderAdapter],
        lead_adapter: ProviderAdapter,
        build_id: str = "council",
        model: str = "",
    ):
        self.adapters = adapters
        self.lead_adapter = lead_adapter
        self.build_id = build_id
        self.model = model or f"council/{lead_adapter.name}"

    def run(
        self,
        query: str,
        system_prompt: str = "",
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        history = _get_history(conversation_id)
        base: List[Dict[str, str]] = []
        if system_prompt:
            base.append({"role": "system", "content": system_prompt})
        base.extend(history)
        user_msg = {"role": "user", "content": query}

        # Fan-out: collect each adapter's response
        votes: List[Dict[str, str]] = []
        evidence: List[Dict[str, str]] = []
        for adapter in self.adapters:
            text = adapter.complete(base + [user_msg])
            votes.append({"provider": adapter.name, "text": text})
            evidence.append({"provider": adapter.name, "text": text})

        # Synthesis: lead adapter reads all votes and produces final answer
        vote_block = "\n\n".join(
            f"[{v['provider']}]: {v['text']}" for v in votes
        )
        synth_prompt = (
            f"The user asked: {query}\n\n"
            f"Council responses:\n{vote_block}\n\n"
            "Synthesize these into a single, authoritative, concise reply."
        )
        synth_messages = base + [{"role": "user", "content": synth_prompt}]
        final = self.lead_adapter.complete(synth_messages)
        evidence.append({"provider": f"{self.lead_adapter.name}(synthesis)", "text": final})

        _save_turn(conversation_id, query, final)
        return _result(
            final, evidence, self.build_id,
            self.lead_adapter.name, self.model, conversation_id,
        )

    def get_build_info(self) -> Dict[str, Any]:
        member_names = [a.name for a in self.adapters]
        return {
            "build_id": self.build_id,
            "lead_provider": self.lead_adapter.name,
            "active_provider": "+".join(member_names),
            "model": self.model,
            "capabilities": ["council", "conversation"],
        }


# --------------------------------------------------------------------------- #
#  Factory                                                                     #
# --------------------------------------------------------------------------- #

def build_kernel(
    build_id: str,
    adapters: Dict[str, ProviderAdapter],
) -> "SoloKernel | PipelineKernel | CouncilKernel":
    """
    Return the kernel for build_id, wired to the provided adapters dict.
    Keys: "google", "openai", "anthropic", "xai", or any custom name.
    """
    def _require(key: str) -> ProviderAdapter:
        if key not in adapters:
            raise ValueError(f"build '{build_id}' requires adapter '{key}' but it was not supplied")
        return adapters[key]

    if build_id == "solo-google":
        return SoloKernel(_require("google"), build_id, "gemini-1.5-flash")

    if build_id == "solo-openai":
        return SoloKernel(_require("openai"), build_id, "gpt-4o-mini")

    if build_id == "solo-anthropic":
        return SoloKernel(_require("anthropic"), build_id, "claude-3-5-haiku-latest")

    if build_id == "solo-xai":
        return SoloKernel(_require("xai"), build_id, "grok-2-latest")

    if build_id == "pipeline-grok-claude":
        return PipelineKernel(_require("xai"), _require("anthropic"), build_id, "grok→claude")

    if build_id == "council-grok-claude-gemini":
        members = [_require("xai"), _require("anthropic"), _require("google")]
        return CouncilKernel(members, _require("xai"), build_id, "council/grok")

    # auto or unknown — use first available adapter as solo
    for name in ("google", "openai", "anthropic", "xai"):
        if name in adapters:
            return SoloKernel(adapters[name], "auto")

    raise ValueError("No adapters supplied and build_id is 'auto' — cannot select a provider")
