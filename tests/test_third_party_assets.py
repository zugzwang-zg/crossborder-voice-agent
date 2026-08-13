from __future__ import annotations

import copy
import unittest
from pathlib import Path

from tools.audit_third_party_assets import audit_manifest, load_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "config" / "third_party_assets.json"


class ThirdPartyAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest(MANIFEST_PATH)

    def test_repository_asset_and_dependency_inventory_passes(self) -> None:
        result = audit_manifest(ROOT, self.manifest)
        self.assertEqual(result["status"], "passed", result["errors"])
        self.assertGreater(result["direct_dependency_count"], 0)
        self.assertGreater(result["tracked_asset_count"], 0)

    def test_unlisted_direct_dependency_fails_closed(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["direct_dependencies"].pop(0)
        result = audit_manifest(ROOT, changed)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any(
            "dependency declaration is not inventoried" in error
            for error in result["errors"]
        ))

    def test_stale_lockfile_review_fails_closed(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["lockfiles"][0]["sha256"] = "0" * 64
        result = audit_manifest(ROOT, changed)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("lockfile hash changed" in error for error in result["errors"]))

    def test_reciprocal_binary_license_requires_distribution_condition(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["installed_node_review"]["conditional_obligations"] = []
        result = audit_manifest(ROOT, changed)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any(
            "reciprocal license lacks a distribution condition" in error
            for error in result["errors"]
        ))

    def test_notice_names_the_public_personal_holder(self) -> None:
        notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
        self.assertIn("Copyright 2026 zugzwang-zg", notice)
        self.assertNotIn("contributors", notice.lower())


if __name__ == "__main__":
    unittest.main()
