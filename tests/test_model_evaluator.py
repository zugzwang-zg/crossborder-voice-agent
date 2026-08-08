"""Tests for frozen-set model evaluation metrics."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.model_evaluator import (
    confidence_calibration_metrics,
    evidence_substring_metrics,
    failure_cases,
    multilabel_metrics,
    sentiment_metrics,
    version_metrics,
    write_comparison_svg,
)


def gold_rows() -> list[dict[str, str]]:
    return [
        {
            "review_id": "en_1",
            "language": "en",
            "stars": "5",
            "review_title": "Great value",
            "review_body": "Works well.",
            "gold_sentiment": "positive",
            "gold_aspects": "value.price_value|product.efficacy.general_effect",
            "gold_issue": "",
        },
        {
            "review_id": "es_1",
            "language": "es",
            "stars": "1",
            "review_title": "Malo",
            "review_body": "No funciona.",
            "gold_sentiment": "negative",
            "gold_aspects": "product.efficacy.general_effect",
            "gold_issue": "no_effect",
        },
    ]


def predictions() -> list[dict]:
    return [
        {
            "review_id": "en_1",
            "analysis": {
                "sentiment": "positive",
                "sentiment_evidence": ["Great value"],
                "aspects": [
                    {
                        "aspect": "value.price_value",
                        "polarity": "positive",
                        "evidence": ["Great value"],
                    }
                ],
                "issue_types": [],
                "purchase_motivations": [],
                "usage_scenarios": [],
                "speech_acts": [],
                "recommended_actions": [],
                "expectation_gap": {"type": "none", "evidence": []},
            },
        },
        {
            "review_id": "es_1",
            "analysis": {
                "sentiment": "positive",
                "sentiment_evidence": ["not in source"],
                "aspects": [],
                "issue_types": [],
                "purchase_motivations": [],
                "usage_scenarios": [],
                "speech_acts": [],
                "recommended_actions": [],
                "expectation_gap": {"type": "none", "evidence": []},
            },
        },
    ]


class ModelEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gold = gold_rows()
        self.records = predictions()
        self.by_id = {item["review_id"]: item for item in self.records}

    def test_sentiment_accuracy_and_macro_f1(self) -> None:
        metrics = sentiment_metrics(self.gold, self.by_id)
        self.assertEqual(metrics["accuracy"], 0.5)
        self.assertEqual(metrics["macro_f1"], 0.3333)
        self.assertEqual(metrics["confusion_matrix"]["negative"]["positive"], 1)

    def test_multilabel_micro_metrics_count_false_negatives(self) -> None:
        metrics = multilabel_metrics(
            self.gold,
            self.by_id,
            gold_field="gold_aspects",
            prediction_field="aspects",
            label_key="aspect",
        )
        self.assertEqual(metrics["true_positives"], 1)
        self.assertEqual(metrics["false_positives"], 0)
        self.assertEqual(metrics["false_negatives"], 2)
        self.assertEqual(metrics["precision"], 1.0)
        self.assertEqual(metrics["recall"], 0.3333)
        self.assertEqual(metrics["f1"], 0.5)
        self.assertIn("value.price_value", metrics["per_label"])
        self.assertEqual(metrics["macro_f1"], 0.5)

    def test_confidence_is_reported_as_uncalibrated_self_report(self) -> None:
        for record in self.records:
            record["analysis"]["confidence"] = 0.95
        metrics = confidence_calibration_metrics(self.gold, self.by_id)
        self.assertEqual(metrics["coverage"], 1.0)
        self.assertEqual(metrics["expected_calibration_error"], 0.45)
        self.assertEqual(metrics["status"], "uncalibrated")
        self.assertEqual(
            metrics["display_policy"], "treat_as_model_self_report_not_probability"
        )

    def test_evidence_substring_validity_is_measured(self) -> None:
        metrics = evidence_substring_metrics(self.gold, self.by_id)
        self.assertEqual(metrics["total_claims"], 3)
        self.assertEqual(metrics["valid_claims"], 2)
        self.assertEqual(metrics["validity"], 0.6667)

    def test_language_metrics_and_json_rate(self) -> None:
        metrics = version_metrics(self.gold, self.records)
        self.assertEqual(metrics["json_parse_success_rate"], 1.0)
        self.assertEqual(
            metrics["by_language"]["en"]["sentiment"]["accuracy"], 1.0
        )
        self.assertEqual(
            metrics["by_language"]["es"]["sentiment"]["accuracy"], 0.0
        )

    def test_failure_cases_include_human_label_differences(self) -> None:
        failures = failure_cases(
            self.gold, {"baseline": self.records}, limit=5
        )
        self.assertTrue(failures)
        self.assertIn("sentiment_mismatch", failures[0]["failure_types"])

    def test_comparison_svg_is_created(self) -> None:
        metrics = version_metrics(self.gold, self.records)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "comparison.svg"
            write_comparison_svg(
                path, {"baseline": metrics, "improved": metrics}
            )
            content = path.read_text(encoding="utf-8")
        self.assertIn("<svg", content)
        self.assertIn("Baseline", content)
        self.assertIn("Improved", content)


if __name__ == "__main__":
    unittest.main()
