from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.ai_review_workflow import (
    SCORE_DIMENSIONS,
    external_role_map,
    load_jsonl,
    sha256_json,
    validate_external_reviews,
)
from tools.merge_external_review_round import merge


ROOT = Path(__file__).resolve().parents[1]


def review(item: dict, role: dict) -> dict:
    return {
        "schema_version": "1.1",
        "item_id": item["item_id"],
        "role_id": role["role_id"],
        "model": role["model"],
        "input_sha256": sha256_json(item),
        "decision": "pass",
        "confidence": 0.8,
        "scores": {dimension: 5 for dimension in SCORE_DIMENSIONS},
        "findings": [],
        "summary": "Bounded test review.",
        "limitations": ["AI pre-review is not human evaluation."],
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


class MergeExternalReviewRoundTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config_path = ROOT / "config" / "ai_review_roles.json"
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.role = next(iter(external_role_map(self.config).values()))
        base = load_jsonl(ROOT / "data" / "sample" / "ai_review_input.demo.jsonl")[0]
        self.first = json.loads(json.dumps(base))
        self.first["item_id"] = "merge-item-1"
        self.old_second = json.loads(json.dumps(base))
        self.old_second["item_id"] = "merge-item-2"
        self.current_second = json.loads(json.dumps(self.old_second))
        self.current_second["candidate"]["revision_marker"] = "revised"

    def test_reuses_only_hash_matching_prior_result_and_validates_rerun(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".private") as directory:
            root = Path(directory)
            input_path = root / "input.jsonl"
            prior_path = root / "prior.jsonl"
            rerun_path = root / "rerun.jsonl"
            parts = root / "parts"
            parts.mkdir()
            output = root / "round2.jsonl"
            manifest_path = root / "round2.manifest.json"
            current_items = [self.first, self.current_second]
            prior = [review(self.first, self.role), review(self.old_second, self.role)]
            rerun = [review(self.current_second, self.role)]
            write_jsonl(input_path, current_items)
            write_jsonl(prior_path, prior)
            write_jsonl(rerun_path, rerun)
            (parts / "merge-item-2.result.json").write_text(
                json.dumps(rerun[0], ensure_ascii=False), encoding="utf-8"
            )

            manifest = merge(
                config_path=self.config_path,
                input_path=input_path,
                prior_path=prior_path,
                rerun_path=rerun_path,
                rerun_parts_dir=parts,
                output_path=output,
                manifest_path=manifest_path,
                expected_rerun_count=1,
            )

            merged = load_jsonl(output)
            validate_external_reviews(current_items, self.config, merged)
            self.assertEqual(manifest["reused_prior_results"], 1)
            self.assertEqual(manifest["discarded_stale_prior_results"], 1)
            self.assertEqual(manifest["rerun_results"], 1)
            self.assertEqual([row["item_id"] for row in merged], [
                "merge-item-1", "merge-item-2"
            ])

    def test_rejects_result_part_that_differs_from_rerun_jsonl(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".private") as directory:
            root = Path(directory)
            input_path = root / "input.jsonl"
            prior_path = root / "prior.jsonl"
            rerun_path = root / "rerun.jsonl"
            parts = root / "parts"
            parts.mkdir()
            rerun = review(self.current_second, self.role)
            write_jsonl(input_path, [self.current_second])
            write_jsonl(prior_path, [review(self.old_second, self.role)])
            write_jsonl(rerun_path, [rerun])
            changed = dict(rerun)
            changed["summary"] = "Different part."
            (parts / "merge-item-2.result.json").write_text(
                json.dumps(changed, ensure_ascii=False), encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "differs from rerun JSONL"):
                merge(
                    config_path=self.config_path,
                    input_path=input_path,
                    prior_path=prior_path,
                    rerun_path=rerun_path,
                    rerun_parts_dir=parts,
                    output_path=root / "round2.jsonl",
                    manifest_path=root / "round2.manifest.json",
                    expected_rerun_count=1,
                )


if __name__ == "__main__":
    unittest.main()
