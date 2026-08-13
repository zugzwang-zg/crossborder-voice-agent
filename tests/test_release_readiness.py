from __future__ import annotations

import json
import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseReadinessTests(unittest.TestCase):
    def test_release_candidate_has_completed_release_gate(self) -> None:
        manifest = json.loads((ROOT / "release_manifest.json").read_text(encoding="utf-8"))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_en = (ROOT / "README.en.md").read_text(encoding="utf-8")
        self.assertIn("118 Python + 4 Dashboard", readme)
        self.assertIn("118 Python + 4 dashboard tests", readme_en)
        for portfolio_document in (
            "docs/PRODUCT_BRIEF.md",
            "docs/SOLUTION_LANDSCAPE.md",
            "docs/PRODUCT_DECISIONS.md",
            "docs/RETROSPECTIVE.md",
        ):
            self.assertTrue((ROOT / portfolio_document).is_file(), portfolio_document)
        self.assertEqual(manifest["target_version"], "v0.2.0")
        self.assertEqual(manifest["candidate_version"], "v0.2.0-rc.1")
        self.assertTrue(manifest["release_created"])
        self.assertEqual(manifest["release_status"], "released_via_git_tag")
        self.assertEqual(manifest["maintainer_signoff"]["status"], "accepted")
        self.assertEqual(manifest["local_release_diff_review"]["status"], "completed")
        self.assertEqual(manifest["required_human_decisions"], [])
        self.assertEqual(manifest["pending_evaluation"], [])
        self.assertEqual(
            manifest["git_release"],
            {
                "status": "published",
                "published_at": "2026-08-13",
                "branch": "phase-7-license-and-review-plan",
                "tag": "v0.2.0",
                "tag_type": "annotated",
                "remote": "origin",
                "branch_push_performed": True,
                "tag_push_performed": True,
                "github_release_created": False,
            },
        )
        self.assertNotIn("release_claim_scope", manifest)
        self.assertEqual(
            manifest["intended_release_claim_scope"],
            "ai_pre_reviewed_prototype_no_new_human_evaluation_claims",
        )
        review_candidate = manifest["ai_pre_review_candidate"]
        self.assertEqual(review_candidate["item_count"], 15)
        self.assertEqual(
            review_candidate["frozen_input_sha256"],
            "6a14a10c77856e6878365449d7ed12421a43b3a326cc11d0a58040c0f803f7bc",
        )
        self.assertEqual(
            review_candidate["current_review_status"],
            "completed_all_15_pass_owner_signoff_accepted",
        )
        self.assertEqual(review_candidate["external_review"]["result_count"], 15)
        self.assertEqual(review_candidate["external_review"]["reused_hash_compatible_results"], 11)
        self.assertEqual(review_candidate["external_review"]["new_changed_item_results"], 4)
        self.assertEqual(review_candidate["external_review"]["discarded_stale_results"], 4)
        self.assertEqual(
            review_candidate["external_review"]["decisions"],
            {"pass": 15, "revise": 0, "block": 0},
        )
        self.assertEqual(review_candidate["openai_seed_plan"]["carried_hash_compatible_reviews"], 33)
        self.assertEqual(review_candidate["openai_seed_plan"]["skipped_hash_incompatible_reviews"], 12)
        self.assertEqual(review_candidate["openai_seed_plan"]["minimum_new_primary_calls"], 12)
        self.assertEqual(review_candidate["source_external_review"]["result_count"], 15)
        self.assertEqual(
            review_candidate["source_external_review"]["decisions"],
            {"pass": 15, "revise": 0, "block": 0},
        )
        self.assertEqual(review_candidate["source_external_review"]["low_severity_findings"], 2)
        self.assertEqual(review_candidate["source_formal_audit"]["completed_items"], 15)
        self.assertEqual(review_candidate["source_formal_audit"]["failed_items"], 0)
        self.assertEqual(
            review_candidate["source_formal_audit"]["decisions"],
            {"pass": 11, "revise": 4, "block": 0},
        )
        self.assertEqual(review_candidate["source_formal_audit"]["usage"]["api_calls"], 63)
        formal_audit = review_candidate["formal_audit"]
        self.assertEqual(
            formal_audit["run_id"],
            "20260813T075034450135Z-6a14a10c7785",
        )
        self.assertEqual(formal_audit["completed_items"], 15)
        self.assertEqual(formal_audit["failed_items"], 0)
        self.assertEqual(formal_audit["adjudication_pending_items"], 0)
        self.assertEqual(
            formal_audit["decisions"],
            {"pass": 15, "revise": 0, "block": 0},
        )
        self.assertEqual(formal_audit["new_primary_stage_results"], 12)
        self.assertEqual(formal_audit["new_necessary_adjudications"], 4)
        self.assertEqual(formal_audit["usage"]["api_calls"], 23)
        self.assertEqual(formal_audit["usage"]["tokens"], 238479)
        self.assertEqual(formal_audit["usage"]["cost_usd"], "1.4106930")
        self.assertEqual(
            formal_audit["scope_exception"]["persisted_out_of_scope_adjudications"],
            3,
        )
        self.assertTrue(
            formal_audit["scope_exception"]["out_of_scope_results_excluded_from_final_summary"]
        )
        attestation_path = ROOT / formal_audit["public_attestation_path"]
        self.assertTrue(attestation_path.is_file())
        self.assertEqual(
            hashlib.sha256(attestation_path.read_bytes()).hexdigest(),
            formal_audit["public_attestation_sha256"],
        )
        attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
        self.assertEqual(attestation["formal_audit"]["decisions"], formal_audit["decisions"])
        self.assertEqual(attestation["maintainer_signoff"]["status"], "accepted")
        self.assertFalse(
            attestation["privacy_and_evidence_boundary"]
            ["raw_inputs_and_model_outputs_published"]
        )
        self.assertEqual(review_candidate["model_api_calls_made"], 23)
        self.assertTrue(review_candidate["external_transfer_authorized"])
        self.assertFalse(review_candidate["remediation_4"]["requires_fresh_hash_bound_review"])
        self.assertTrue(review_candidate["remediation_4"]["fresh_hash_bound_review_completed"])
        self.assertEqual(review_candidate["remediation_4"]["changed_item_count"], 4)
        self.assertEqual(review_candidate["remediation_4"]["unchanged_item_count"], 11)
        self.assertTrue((ROOT / review_candidate["config"]).is_file())
        self.assertTrue((ROOT / review_candidate["review_config"]).is_file())
        self.assertIn(
            "frozen_40_review_challenge_set_requires_two_independent_annotations",
            manifest["deferred_optional_evaluation"],
        )
        self.assertTrue((ROOT / "LICENSE").is_file())
        self.assertTrue((ROOT / "NOTICE").is_file())
        self.assertTrue((ROOT / "config" / "third_party_assets.json").is_file())
        self.assertIn(
            "python tools/audit_third_party_assets.py --check-installed",
            manifest["validation_commands"],
        )

        insights = json.loads(
            (ROOT / "reports" / "consumer_insights.json").read_text(encoding="utf-8")
        )
        self.assertTrue(
            all("mean_model_confidence" not in item["data_evidence"] for item in insights["insights"])
        )
        scent = next(
            item for item in insights["insights"]
            if item["insight_id"] == "positive_aspects:product.sensory.scent"
        )
        self.assertNotIn("en_0045389", scent["data_evidence"]["source_review_ids"])

        package = json.loads((ROOT / "dashboard" / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["version"], "0.2.0")
        self.assertEqual(package["license"], "Apache-2.0")
        for document in (
            "ARCHITECTURE.md", "DEMO_SCRIPT.md", "RELEASE_READINESS.md",
            "THIRD_PARTY_ASSETS.md",
        ):
            self.assertTrue((ROOT / "docs" / document).is_file(), document)


if __name__ == "__main__":
    unittest.main()
