from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.ai_review_workflow import load_jsonl, validate_items
from tools.prepare_release_candidate_review import DEFAULT_CONFIG, build_items, freeze


ROOT = Path(__file__).resolve().parents[1]


class ReleaseCandidateReviewPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))

    def test_builds_all_real_release_insights_and_validates_contract(self) -> None:
        items, _ = build_items(self.config)
        self.assertEqual(len(items), 15)
        self.assertEqual(len({item["item_id"] for item in items}), 15)
        self.assertTrue(all(not item["metadata"].get("synthetic_demo", False) for item in items))
        validate_items(items, "crossborder-voice")

    def test_stale_release_insight_is_rejected(self) -> None:
        report_path = ROOT / self.config["sources"]["candidate_insights"]
        original = json.loads(report_path.read_text(encoding="utf-8"))
        original["insights"][0]["support_count"] += 1
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "changed.json"
            changed.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            config = json.loads(json.dumps(self.config))
            config["sources"]["candidate_insights"] = str(changed)
            with self.assertRaisesRegex(ValueError, "stale or inconsistent support_count"):
                build_items(config)

    def test_aggregation_audit_makes_support_volume_tier_reproducible(self) -> None:
        items, _ = build_items(self.config)
        candidate = items[0]["candidate"]
        audit_reference = next(
            reference for reference in items[0]["references"]
            if reference["reference_id"] == "aggregation_audit"
        )
        audit = json.loads(audit_reference["content"])
        self.assertEqual(audit["configured_min_support"], 5)
        self.assertEqual(audit["support_volume_thresholds"], {"medium": 10, "high": 20})
        self.assertEqual(audit["support_volume_tier"], candidate["support_volume_tier"])
        self.assertEqual(audit["support_rate"], candidate["support_rate"])
        self.assertEqual(audit["selected_records_denominator"], 1000)
        self.assertEqual(
            audit["selected_records_denominator_semantics"],
            "selected unique review records",
        )
        self.assertEqual(len(audit["selected_review_ids_sha256"]), 64)
        self.assertEqual(
            candidate["confidence_or_evidence_grade"],
            f"{candidate['support_volume_tier']}_support_volume",
        )

    def test_freeze_is_deterministic_and_records_no_model_calls(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".private") as first_directory, tempfile.TemporaryDirectory(
            dir=ROOT / ".private"
        ) as second_directory:
            first = freeze(DEFAULT_CONFIG, Path(first_directory))
            second = freeze(DEFAULT_CONFIG, Path(second_directory))
            self.assertEqual(first, second)
            self.assertEqual(first["status"], "prepared_without_model_calls")
            self.assertEqual(first["model_api_calls_made"], 0)
            self.assertFalse(first["external_transfer_authorized"])
            self.assertEqual(
                (Path(first_directory) / "input.jsonl").read_bytes(),
                (Path(second_directory) / "input.jsonl").read_bytes(),
            )
            items = load_jsonl(Path(first_directory) / "input.jsonl")
            self.assertEqual(len(items), first["item_count"])


if __name__ == "__main__":
    unittest.main()
