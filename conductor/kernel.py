"""Provider-neutral execution kernel for solo and Council Conductors."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import RLock
from typing import Protocol, Sequence

from config.builds import BuildConfig


APPROVAL_REQUIRED = {
    "spend",
    "delete",
    "publish",
    "credentials",
    "permissions",
    "account_change",
    "irreversible_external_action",
}


@dataclass(frozen=True)
class Message:
    role: str
    content: str


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    model: str
    text: str
    sources: tuple[dict, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    text: str
    provider: str
    model: str
    sources: tuple[dict, ...]
    council_results: tuple[ProviderResult, ...] = ()
    approval_required: bool = False
    approval_action: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class ProviderAdapter(Protocol):
    name: str

    def complete(
        self,
        messages: Sequence[Message],
        *,
        purpose: str = "answer",
    ) -> ProviderResult: ...


class ConversationStore(Protocol):
    def load(self, conversation_id: str) -> list[Message]: ...

    def append(self, conversation_id: str, *messages: Message) -> None: ...


@dataclass
class InMemoryConversationStore:
    """Deterministic development store; production can supply Firestore/SQL."""

    conversations: dict[str, list[Message]] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def load(self, conversation_id: str) -> list[Message]:
        with self._lock:
            return list(self.conversations.get(conversation_id, ()))

    def append(self, conversation_id: str, *messages: Message) -> None:
        with self._lock:
            self.conversations.setdefault(conversation_id, []).extend(messages)


class ConductorKernel:
    def __init__(
        self,
        build: BuildConfig,
        adapters: dict[str, ProviderAdapter],
        store: ConversationStore,
        system_prompt: str,
    ):
        self.build = build
        self.adapters = adapters
        self.store = store
        self.system_prompt = system_prompt
        required = {build.lead, *build.specialists}
        missing = sorted(required.difference(adapters))
        if missing:
            raise ValueError(f"Missing provider adapters: {', '.join(missing)}")

    def run(
        self,
        query: str,
        conversation_id: str,
        *,
        principal_id: str = "owner",
        proposed_action: str | None = None,
        approved: bool = False,
    ) -> ExecutionResult:
        if proposed_action in APPROVAL_REQUIRED and not approved:
            return ExecutionResult(
                text=(
                    f"Approval required before `{proposed_action}`. "
                    "No external action was taken."
                ),
                provider=self.build.lead,
                model="approval-gate",
                sources=(),
                approval_required=True,
                approval_action=proposed_action,
            )

        state_key = f"{principal_id}:{conversation_id}"
        history = self.store.load(state_key)
        user_message = Message("user", query)
        messages = [Message("system", self.system_prompt), *history, user_message]

        if self.build.mode == "solo":
            final = self.adapters[self.build.lead].complete(messages)
            council_results: tuple[ProviderResult, ...] = ()
        else:
            with ThreadPoolExecutor(
                max_workers=len(self.build.specialists)
            ) as executor:
                futures = {
                    provider: executor.submit(
                        self._specialist_review,
                        provider,
                        messages,
                    )
                    for provider in self.build.specialists
                }
                council_results = tuple(
                    futures[provider].result()
                    for provider in self.build.specialists
                )
            synthesis = self._synthesis_message(query, council_results)
            final = self.adapters[self.build.lead].complete(
                [*messages, Message("user", synthesis)],
                purpose="lead_synthesis",
            )

        self.store.append(
            state_key,
            user_message,
            Message("assistant", final.text),
        )
        sources = self._dedupe_sources([*council_results, final])
        return ExecutionResult(
            text=final.text,
            provider=final.provider,
            model=final.model,
            sources=sources,
            council_results=council_results,
            input_tokens=sum(
                item.input_tokens for item in (*council_results, final)
            ),
            output_tokens=sum(
                item.output_tokens for item in (*council_results, final)
            ),
        )

    def _specialist_review(
        self,
        provider: str,
        messages: Sequence[Message],
    ) -> ProviderResult:
        try:
            return self.adapters[provider].complete(
                messages,
                purpose=f"specialist_review:{provider}",
            )
        except Exception as exc:
            return ProviderResult(
                provider=provider,
                model="unavailable",
                text=f"Specialist unavailable: {type(exc).__name__}",
                error=f"{type(exc).__name__}: {exc}",
            )

    @staticmethod
    def _synthesis_message(
        query: str,
        results: Sequence[ProviderResult],
    ) -> str:
        reviews = "\n\n".join(
            (
                f"[{result.provider} status="
                f"{'failed' if result.error else 'completed'}]\n{result.text}"
            )
            for result in results
        )
        return (
            "You are the lead GM. Produce the final answer to the original "
            "request using the specialist reviews below. Resolve disagreement, "
            "do not invent consensus, and distinguish verified facts from "
            f"unknowns.\n\nOriginal request:\n{query}\n\nReviews:\n{reviews}"
        )

    @staticmethod
    def _dedupe_sources(
        results: Sequence[ProviderResult],
    ) -> tuple[dict, ...]:
        sources: list[dict] = []
        seen: set[str] = set()
        for result in results:
            for source in result.sources:
                key = str(source.get("url") or source)
                if key in seen:
                    continue
                seen.add(key)
                sources.append(source)
        return tuple(sources)
