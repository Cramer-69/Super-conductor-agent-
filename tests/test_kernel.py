import unittest

from config.builds import get_build
from conductor.kernel import (
    ConductorKernel,
    InMemoryConversationStore,
    ProviderResult,
)


class FakeAdapter:
    def __init__(self, name: str, fail: bool = False):
        self.name = name
        self.fail = fail
        self.calls = []

    def complete(self, messages, *, purpose="answer"):
        self.calls.append((list(messages), purpose))
        if self.fail:
            raise RuntimeError(f"{self.name} failed")
        previous = next(
            (
                message.content
                for message in reversed(messages)
                if message.role == "assistant"
            ),
            "none",
        )
        return ProviderResult(
            provider=self.name,
            model=f"{self.name}-test",
            text=f"{self.name}:{purpose}:previous={previous}",
            sources=(
                {"url": "https://example.com/shared"},
                {"url": f"https://example.com/{self.name}"},
            ),
        )


class ConductorKernelTests(unittest.TestCase):
    def test_solo_uses_lead_and_persists_history(self):
        adapter = FakeAdapter("openai")
        store = InMemoryConversationStore()
        kernel = ConductorKernel(
            get_build("solo-openai"),
            {"openai": adapter},
            store,
            "system",
        )

        first = kernel.run("remember this", "conversation-1")
        second = kernel.run("what did I say?", "conversation-1")

        self.assertEqual(first.provider, "openai")
        self.assertIn("previous=openai:answer", second.text)
        self.assertEqual(len(store.load("owner:conversation-1")), 4)

    def test_council_fans_out_then_lead_synthesizes(self):
        adapters = {
            provider: FakeAdapter(provider)
            for provider in ("openai", "anthropic", "google", "xai")
        }
        kernel = ConductorKernel(
            get_build("council-openai"),
            adapters,
            InMemoryConversationStore(),
            "system",
        )

        result = kernel.run("decide", "conversation-2")

        self.assertEqual(
            [item.provider for item in result.council_results],
            ["anthropic", "google", "xai"],
        )
        self.assertEqual(adapters["openai"].calls[0][1], "lead_synthesis")
        synthesis = adapters["openai"].calls[0][0][-1].content
        self.assertIn("[anthropic status=completed]", synthesis)
        self.assertIn("[google status=completed]", synthesis)
        self.assertIn("[xai status=completed]", synthesis)
        self.assertEqual(len(result.sources), 5)

    def test_conversations_are_isolated_by_principal(self):
        adapter = FakeAdapter("openai")
        store = InMemoryConversationStore()
        kernel = ConductorKernel(
            get_build("solo-openai"),
            {"openai": adapter},
            store,
            "system",
        )

        kernel.run("alpha", "same-id", principal_id="john")
        result = kernel.run("beta", "same-id", principal_id="other")

        self.assertIn("previous=none", result.text)

    def test_failed_specialist_is_reported_and_lead_still_runs(self):
        adapters = {
            provider: FakeAdapter(provider, fail=provider == "google")
            for provider in ("openai", "anthropic", "google", "xai")
        }
        kernel = ConductorKernel(
            get_build("council-openai"),
            adapters,
            InMemoryConversationStore(),
            "system",
        )

        result = kernel.run("decide", "conversation-failure")

        google = next(
            item for item in result.council_results
            if item.provider == "google"
        )
        self.assertIn("RuntimeError", google.error)
        self.assertIn(
            "[google status=failed]",
            adapters["openai"].calls[0][0][-1].content,
        )
        self.assertEqual(result.provider, "openai")

    def test_sensitive_action_is_blocked_without_approval(self):
        adapter = FakeAdapter("openai")
        kernel = ConductorKernel(
            get_build("solo-openai"),
            {"openai": adapter},
            InMemoryConversationStore(),
            "system",
        )

        result = kernel.run(
            "delete it",
            "conversation-3",
            proposed_action="delete",
        )

        self.assertTrue(result.approval_required)
        self.assertEqual(result.approval_action, "delete")
        self.assertEqual(adapter.calls, [])

    def test_sensitive_action_runs_after_explicit_approval(self):
        adapter = FakeAdapter("openai")
        kernel = ConductorKernel(
            get_build("solo-openai"),
            {"openai": adapter},
            InMemoryConversationStore(),
            "system",
        )

        result = kernel.run(
            "publish it",
            "conversation-4",
            proposed_action="publish",
            approved=True,
        )

        self.assertFalse(result.approval_required)
        self.assertEqual(len(adapter.calls), 1)

    def test_missing_adapter_fails_before_execution(self):
        with self.assertRaisesRegex(ValueError, "anthropic, google, xai"):
            ConductorKernel(
                get_build("council-openai"),
                {"openai": FakeAdapter("openai")},
                InMemoryConversationStore(),
                "system",
            )


if __name__ == "__main__":
    unittest.main()
