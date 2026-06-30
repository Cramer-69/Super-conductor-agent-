import os
import unittest
from unittest.mock import patch

from config.builds import get_active_build, get_build


class BuildManifestTests(unittest.TestCase):
    def test_all_eight_builds_validate(self):
        build_ids = (
            "solo-openai",
            "solo-claude",
            "solo-gemini",
            "solo-grok",
            "council-openai",
            "council-claude",
            "council-gemini",
            "council-grok",
        )

        builds = [get_build(build_id) for build_id in build_ids]

        self.assertEqual(len(builds), 8)
        self.assertEqual(sum(build.mode == "solo" for build in builds), 4)
        self.assertEqual(sum(build.mode == "council" for build in builds), 4)

    def test_active_build_defaults_to_openai_solo(self):
        with patch.dict(os.environ, {}, clear=True):
            build = get_active_build()

        self.assertEqual(build.build_id, "solo-openai")
        self.assertEqual(build.lead, "openai")
        self.assertEqual(build.specialists, ())

    def test_each_council_has_three_non_lead_specialists(self):
        for lead in ("openai", "anthropic", "google", "xai"):
            build = get_build(f"council-{'claude' if lead == 'anthropic' else 'gemini' if lead == 'google' else 'grok' if lead == 'xai' else 'openai'}")
            self.assertEqual(len(build.specialists), 3)
            self.assertNotIn(build.lead, build.specialists)

    def test_unknown_build_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown CONDUCTOR_BUILD_ID"):
            get_build("solo-invented")


if __name__ == "__main__":
    unittest.main()
