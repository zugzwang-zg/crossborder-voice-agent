from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseReadinessTests(unittest.TestCase):
    def test_release_candidate_is_documented_but_not_claimed_as_released(self) -> None:
        manifest = json.loads((ROOT / "release_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["target_version"], "v0.2.0")
        self.assertEqual(manifest["candidate_version"], "v0.2.0-rc.1")
        self.assertFalse(manifest["release_created"])
        self.assertIn("select_and_add_repository_license", manifest["required_human_decisions"])

        package = json.loads((ROOT / "dashboard" / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["version"], "0.2.0-rc.1")
        for document in ("ARCHITECTURE.md", "DEMO_SCRIPT.md", "RELEASE_READINESS.md"):
            self.assertTrue((ROOT / "docs" / document).is_file(), document)


if __name__ == "__main__":
    unittest.main()
