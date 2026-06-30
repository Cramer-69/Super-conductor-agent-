"""
Build-registry tests for conductor/kernel.py.
Validates every named build profile via build_kernel() using MockAdapter.
No real API keys required.

Run: python -m unittest tests.test_builds tests.test_kernel
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conductor.kernel import (
    SoloKernel,
    PipelineKernel,
    CouncilKernel,
    build_kernel,
    clear_history,
)


class MockAdapter:
    def __init__(self, name: str, reply: str = ""):
        self.name = name
        self._reply = reply or f"[{name}]"
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        return self._reply

    @property
    def call_count(self):
        return len(self.calls)


def _all():
    return {n: MockAdapter(n) for n in ("google", "openai", "anthropic", "xai")}


class TestSoloBuilds(unittest.TestCase):
    """Each solo-* build_id should produce a SoloKernel with the right adapter."""

    SOLO_CASES = [
        ("solo-google",    "google"),
        ("solo-openai",    "openai"),
        ("solo-anthropic", "anthropic"),
        ("solo-xai",       "xai"),
    ]

    def test_kernel_type_is_solo(self):
        for build_id, _ in self.SOLO_CASES:
            with self.subTest(build_id=build_id):
                k = build_kernel(build_id, _all())
                self.assertIsInstance(k, SoloKernel)

    def test_correct_adapter_wired(self):
        for build_id, expected_provider in self.SOLO_CASES:
            with self.subTest(build_id=build_id):
                k = build_kernel(build_id, _all())
                self.assertEqual(k.adapter.name, expected_provider)

    def test_build_id_stored(self):
        for build_id, _ in self.SOLO_CASES:
            with self.subTest(build_id=build_id):
                k = build_kernel(build_id, _all())
                self.assertEqual(k.build_id, build_id)

    def test_run_calls_adapter_once(self):
        for build_id, provider in self.SOLO_CASES:
            with self.subTest(build_id=build_id):
                adapters = _all()
                k = build_kernel(build_id, adapters)
                k.run("hello")
                self.assertEqual(adapters[provider].call_count, 1)

    def test_run_returns_response(self):
        adapters = _all()
        adapters["google"] = MockAdapter("google", "gemini says hi")
        k = build_kernel("solo-google", adapters)
        result = k.run("hi")
        self.assertEqual(result["response"], "gemini says hi")

    def test_missing_adapter_raises(self):
        for build_id, provider in self.SOLO_CASES:
            with self.subTest(build_id=build_id):
                incomplete = {k: MockAdapter(k) for k in ("google", "openai", "anthropic", "xai") if k != provider}
                with self.assertRaises(ValueError):
                    build_kernel(build_id, incomplete)


class TestPipelineBuild(unittest.TestCase):
    """pipeline-grok-claude: xai drafts first, anthropic refines second."""

    def setUp(self):
        self.adapters = _all()
        self.adapters["xai"] = MockAdapter("xai", "grok draft")
        self.adapters["anthropic"] = MockAdapter("anthropic", "claude refined")
        self.kernel = build_kernel("pipeline-grok-claude", self.adapters)

    def test_kernel_type(self):
        self.assertIsInstance(self.kernel, PipelineKernel)

    def test_draft_adapter_is_xai(self):
        self.assertEqual(self.kernel.draft_adapter.name, "xai")

    def test_refine_adapter_is_anthropic(self):
        self.assertEqual(self.kernel.refine_adapter.name, "anthropic")

    def test_xai_called_first(self):
        self.kernel.run("test")
        self.assertEqual(self.adapters["xai"].call_count, 1)
        self.assertEqual(self.adapters["anthropic"].call_count, 1)

    def test_response_is_claude_output(self):
        result = self.kernel.run("test")
        self.assertEqual(result["response"], "claude refined")

    def test_claude_receives_grok_draft(self):
        self.kernel.run("test")
        claude_msgs = self.adapters["anthropic"].calls[-1]
        last_user = next(m for m in reversed(claude_msgs) if m["role"] == "user")
        self.assertIn("grok draft", last_user["content"])

    def test_evidence_has_both_providers(self):
        result = self.kernel.run("test")
        providers = [e["provider"] for e in result["evidence"]]
        self.assertIn("xai", providers)
        self.assertIn("anthropic", providers)

    def test_missing_xai_raises(self):
        without_xai = {k: v for k, v in self.adapters.items() if k != "xai"}
        with self.assertRaises(ValueError):
            build_kernel("pipeline-grok-claude", without_xai)

    def test_missing_anthropic_raises(self):
        without_claude = {k: v for k, v in self.adapters.items() if k != "anthropic"}
        with self.assertRaises(ValueError):
            build_kernel("pipeline-grok-claude", without_claude)


class TestCouncilBuild(unittest.TestCase):
    """council-grok-claude-gemini: 3 members fan out, xai (grok) leads synthesis."""

    def setUp(self):
        self.adapters = {
            "xai":       MockAdapter("xai",       "grok vote"),
            "anthropic": MockAdapter("anthropic",  "claude vote"),
            "google":    MockAdapter("google",     "gemini vote"),
            "openai":    MockAdapter("openai"),
        }
        self.kernel = build_kernel("council-grok-claude-gemini", self.adapters)

    def test_kernel_type(self):
        self.assertIsInstance(self.kernel, CouncilKernel)

    def test_three_member_adapters(self):
        self.assertEqual(len(self.kernel.adapters), 3)

    def test_lead_is_xai(self):
        self.assertEqual(self.kernel.lead_adapter.name, "xai")

    def test_all_members_called(self):
        self.kernel.run("council question")
        # xai is both a member and the lead synthesizer → called twice
        self.assertEqual(self.adapters["xai"].call_count, 2)
        self.assertEqual(self.adapters["anthropic"].call_count, 1)
        self.assertEqual(self.adapters["google"].call_count, 1)

    def test_openai_not_called(self):
        self.kernel.run("council question")
        self.assertEqual(self.adapters["openai"].call_count, 0)

    def test_synthesis_prompt_has_all_votes(self):
        self.kernel.run("council question")
        synth_msgs = self.adapters["xai"].calls[-1]
        last_user = next(m for m in reversed(synth_msgs) if m["role"] == "user")
        content = last_user["content"]
        self.assertIn("grok vote", content)
        self.assertIn("claude vote", content)
        self.assertIn("gemini vote", content)

    def test_evidence_four_entries(self):
        # 3 member votes + 1 synthesis entry
        result = self.kernel.run("council question")
        self.assertEqual(len(result["evidence"]), 4)

    def test_build_info_capabilities(self):
        info = self.kernel.get_build_info()
        self.assertIn("council", info["capabilities"])
        self.assertEqual(info["build_id"], "council-grok-claude-gemini")


class TestAutoMode(unittest.TestCase):
    """auto mode: picks first available adapter in priority order."""

    def test_auto_prefers_google(self):
        k = build_kernel("auto", _all())
        self.assertIsInstance(k, SoloKernel)
        self.assertEqual(k.adapter.name, "google")

    def test_auto_falls_back_to_openai(self):
        k = build_kernel("auto", {"openai": MockAdapter("openai"), "xai": MockAdapter("xai")})
        self.assertEqual(k.adapter.name, "openai")

    def test_auto_falls_back_to_anthropic(self):
        k = build_kernel("auto", {"anthropic": MockAdapter("anthropic")})
        self.assertEqual(k.adapter.name, "anthropic")

    def test_auto_falls_back_to_xai(self):
        k = build_kernel("auto", {"xai": MockAdapter("xai")})
        self.assertEqual(k.adapter.name, "xai")

    def test_auto_with_no_adapters_raises(self):
        with self.assertRaises(ValueError):
            build_kernel("auto", {})

    def test_auto_build_id_in_result(self):
        k = build_kernel("auto", {"openai": MockAdapter("openai")})
        result = k.run("hi")
        self.assertEqual(result["build_id"], "auto")


class TestBuildHealthInfo(unittest.TestCase):
    """get_build_info() returns the right metadata for each build."""

    def test_solo_info(self):
        k = build_kernel("solo-anthropic", _all())
        info = k.get_build_info()
        self.assertEqual(info["build_id"], "solo-anthropic")
        self.assertEqual(info["lead_provider"], "anthropic")
        self.assertIn("conversation", info["capabilities"])

    def test_pipeline_info(self):
        k = build_kernel("pipeline-grok-claude", _all())
        info = k.get_build_info()
        self.assertIn("pipeline", info["capabilities"])

    def test_council_info(self):
        k = build_kernel("council-grok-claude-gemini", _all())
        info = k.get_build_info()
        self.assertIn("council", info["capabilities"])
        self.assertEqual(info["lead_provider"], "xai")


if __name__ == "__main__":
    unittest.main()
