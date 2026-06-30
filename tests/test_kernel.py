"""
Unit tests for conductor/kernel.py using fake adapters.
No real API keys required — all provider calls use MockAdapter.

Run: python -m unittest tests.test_kernel
"""
import sys
import os
import unittest
from typing import Dict, List

# Make sure the package root is on the path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conductor.kernel import (
    SoloKernel,
    PipelineKernel,
    CouncilKernel,
    build_kernel,
    clear_history,
)


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

class MockAdapter:
    """Fake provider that records calls and returns predictable text."""

    def __init__(self, name: str, reply: str = ""):
        self.name = name
        self._reply = reply or f"[{name} reply]"
        self.calls: List[List[Dict[str, str]]] = []  # history of message lists

    def complete(self, messages: List[Dict[str, str]]) -> str:
        self.calls.append(list(messages))
        return self._reply

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def last_messages(self) -> List[Dict[str, str]]:
        return self.calls[-1] if self.calls else []


def _adapters(**kwargs) -> Dict[str, MockAdapter]:
    return {name: MockAdapter(name, reply) for name, reply in kwargs.items()}


# --------------------------------------------------------------------------- #
#  SoloKernel                                                                  #
# --------------------------------------------------------------------------- #

class TestSoloKernel(unittest.TestCase):

    def test_calls_correct_adapter(self):
        google = MockAdapter("google", "gemini answer")
        kernel = SoloKernel(google, "solo-google", "gemini-1.5-flash")
        result = kernel.run("hello")
        self.assertEqual(result["response"], "gemini answer")
        self.assertEqual(google.call_count, 1)

    def test_user_message_appended(self):
        adapter = MockAdapter("openai")
        kernel = SoloKernel(adapter, "solo-openai")
        kernel.run("test query")
        msgs = adapter.last_messages()
        self.assertEqual(msgs[-1], {"role": "user", "content": "test query"})

    def test_system_prompt_prepended(self):
        adapter = MockAdapter("anthropic")
        kernel = SoloKernel(adapter, "solo-anthropic")
        kernel.run("hi", system_prompt="You are helpful.")
        msgs = adapter.last_messages()
        self.assertEqual(msgs[0], {"role": "system", "content": "You are helpful."})

    def test_result_structure(self):
        adapter = MockAdapter("xai", "grok says hi")
        kernel = SoloKernel(adapter, "solo-xai", "grok-2-latest")
        result = kernel.run("hi")
        self.assertIn("response", result)
        self.assertIn("evidence", result)
        self.assertIn("build_id", result)
        self.assertEqual(result["build_id"], "solo-xai")
        self.assertEqual(len(result["evidence"]), 1)
        self.assertEqual(result["evidence"][0]["provider"], "xai")

    def test_get_build_info(self):
        adapter = MockAdapter("google")
        kernel = SoloKernel(adapter, "solo-google", "gemini-1.5-flash")
        info = kernel.get_build_info()
        self.assertEqual(info["build_id"], "solo-google")
        self.assertEqual(info["lead_provider"], "google")
        self.assertIn("conversation", info["capabilities"])


# --------------------------------------------------------------------------- #
#  PipelineKernel                                                              #
# --------------------------------------------------------------------------- #

class TestPipelineKernel(unittest.TestCase):

    def setUp(self):
        self.grok = MockAdapter("xai", "grok draft text")
        self.claude = MockAdapter("anthropic", "claude refined text")
        self.kernel = PipelineKernel(self.grok, self.claude, "pipeline-grok-claude")

    def test_both_adapters_called(self):
        self.kernel.run("give me an idea")
        self.assertEqual(self.grok.call_count, 1)
        self.assertEqual(self.claude.call_count, 1)

    def test_response_is_refined_output(self):
        result = self.kernel.run("give me an idea")
        self.assertEqual(result["response"], "claude refined text")

    def test_claude_receives_grok_draft(self):
        self.kernel.run("some query")
        claude_msgs = self.claude.last_messages()
        # The last user message to Claude should contain the grok draft
        last_user = next(m for m in reversed(claude_msgs) if m["role"] == "user")
        self.assertIn("grok draft text", last_user["content"])

    def test_evidence_has_both_providers(self):
        result = self.kernel.run("test")
        providers = [e["provider"] for e in result["evidence"]]
        self.assertIn("xai", providers)
        self.assertIn("anthropic", providers)

    def test_build_info_shows_pipeline(self):
        info = self.kernel.get_build_info()
        self.assertEqual(info["build_id"], "pipeline-grok-claude")
        self.assertIn("pipeline", info["capabilities"])


# --------------------------------------------------------------------------- #
#  CouncilKernel                                                               #
# --------------------------------------------------------------------------- #

class TestCouncilKernel(unittest.TestCase):

    def setUp(self):
        self.grok = MockAdapter("xai", "grok vote")
        self.claude = MockAdapter("anthropic", "claude vote")
        self.gemini = MockAdapter("google", "gemini vote")
        self.kernel = CouncilKernel(
            [self.grok, self.claude, self.gemini],
            lead_adapter=self.grok,
            build_id="council-grok-claude-gemini",
        )

    def test_all_adapters_called(self):
        self.kernel.run("council question")
        self.assertEqual(self.grok.call_count, 2)   # member + lead synthesis
        self.assertEqual(self.claude.call_count, 1)
        self.assertEqual(self.gemini.call_count, 1)

    def test_synthesis_prompt_contains_all_votes(self):
        self.kernel.run("council question")
        # The last Grok call is the synthesis prompt
        synth_msgs = self.grok.last_messages()
        last_user = next(m for m in reversed(synth_msgs) if m["role"] == "user")
        self.assertIn("grok vote", last_user["content"])
        self.assertIn("claude vote", last_user["content"])
        self.assertIn("gemini vote", last_user["content"])

    def test_response_is_lead_synthesis(self):
        result = self.kernel.run("council question")
        # Grok is lead; its second call returns "grok vote" again
        self.assertEqual(result["response"], "grok vote")

    def test_evidence_includes_all_providers_plus_synthesis(self):
        result = self.kernel.run("council question")
        providers = [e["provider"] for e in result["evidence"]]
        self.assertIn("xai", providers)
        self.assertIn("anthropic", providers)
        self.assertIn("google", providers)
        # synthesis entry should also be present
        self.assertTrue(any("synthesis" in p for p in providers))

    def test_build_info_shows_council(self):
        info = self.kernel.get_build_info()
        self.assertIn("council", info["capabilities"])


# --------------------------------------------------------------------------- #
#  Conversation memory                                                         #
# --------------------------------------------------------------------------- #

class TestConversationMemory(unittest.TestCase):

    def setUp(self):
        self.conv_id = "test-conv-123"
        clear_history(self.conv_id)

    def tearDown(self):
        clear_history(self.conv_id)

    def test_second_turn_receives_history(self):
        adapter = MockAdapter("openai", "first answer")
        kernel = SoloKernel(adapter, "solo-openai")
        kernel.run("turn one", conversation_id=self.conv_id)

        adapter2 = MockAdapter("openai", "second answer")
        kernel2 = SoloKernel(adapter2, "solo-openai")
        kernel2.run("turn two", conversation_id=self.conv_id)

        msgs = adapter2.last_messages()
        roles = [m["role"] for m in msgs]
        # History from turn 1 should appear before the new user message
        self.assertIn("assistant", roles)
        contents = [m["content"] for m in msgs if m["role"] == "assistant"]
        self.assertIn("first answer", contents)

    def test_no_history_without_conversation_id(self):
        adapter = MockAdapter("openai", "stateless answer")
        kernel = SoloKernel(adapter, "solo-openai")
        kernel.run("turn one")  # no conversation_id
        kernel.run("turn two")  # no conversation_id
        # Second call should have no history (just user message, possibly system)
        msgs = adapter.last_messages()
        non_user = [m for m in msgs if m["role"] != "user" and m["role"] != "system"]
        self.assertEqual(len(non_user), 0)

    def test_conversation_id_in_result(self):
        adapter = MockAdapter("xai")
        kernel = SoloKernel(adapter, "solo-xai")
        result = kernel.run("hello", conversation_id=self.conv_id)
        self.assertEqual(result["conversation_id"], self.conv_id)

    def test_null_conversation_id_when_not_set(self):
        adapter = MockAdapter("xai")
        kernel = SoloKernel(adapter, "solo-xai")
        result = kernel.run("hello")
        self.assertIsNone(result["conversation_id"])


# --------------------------------------------------------------------------- #
#  build_kernel factory                                                        #
# --------------------------------------------------------------------------- #

class TestBuildKernelFactory(unittest.TestCase):

    def _all_adapters(self):
        return {
            "google":    MockAdapter("google"),
            "openai":    MockAdapter("openai"),
            "anthropic": MockAdapter("anthropic"),
            "xai":       MockAdapter("xai"),
        }

    def test_solo_builds_return_solo_kernel(self):
        for build_id, expected_provider in [
            ("solo-google", "google"),
            ("solo-openai", "openai"),
            ("solo-anthropic", "anthropic"),
            ("solo-xai", "xai"),
        ]:
            kernel = build_kernel(build_id, self._all_adapters())
            self.assertIsInstance(kernel, SoloKernel, f"Expected SoloKernel for {build_id}")
            self.assertEqual(kernel.adapter.name, expected_provider)

    def test_pipeline_build_returns_pipeline_kernel(self):
        kernel = build_kernel("pipeline-grok-claude", self._all_adapters())
        self.assertIsInstance(kernel, PipelineKernel)
        self.assertEqual(kernel.draft_adapter.name, "xai")
        self.assertEqual(kernel.refine_adapter.name, "anthropic")

    def test_council_build_returns_council_kernel(self):
        kernel = build_kernel("council-grok-claude-gemini", self._all_adapters())
        self.assertIsInstance(kernel, CouncilKernel)
        self.assertEqual(len(kernel.adapters), 3)

    def test_auto_picks_first_available(self):
        # Only anthropic available
        kernel = build_kernel("auto", {"anthropic": MockAdapter("anthropic")})
        self.assertIsInstance(kernel, SoloKernel)
        self.assertEqual(kernel.adapter.name, "anthropic")

    def test_missing_required_adapter_raises(self):
        with self.assertRaises(ValueError):
            build_kernel("pipeline-grok-claude", {"google": MockAdapter("google")})

    def test_auto_with_no_adapters_raises(self):
        with self.assertRaises(ValueError):
            build_kernel("auto", {})


if __name__ == "__main__":
    unittest.main()
