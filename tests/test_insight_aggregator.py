"""Tests for deterministic aggregation and traceability."""

from __future__ import annotations

import unittest

from src.insight_aggregator import (
    aggregate_records,
    validate_report_traceability,
)


def record(
    review_id: str,
    *,
    language: str,
    stars: int,
    aspect: str,
    polarity: str,
    evidence: str,
    issue: str | None = None,
    product_id: str = "unknown",
    product_subcategory: str = "unknown",
) -> dict:
    return {
        "review_id": review_id,
        "source": {
            "language": language,
            "stars": stars,
            "title": "",
            "body": evidence,
            "product_id": product_id,
            "product_subcategory": product_subcategory,
        },
        "analysis": {
            "confidence": 0.95,
            "aspects": [
                {
                    "aspect": aspect,
                    "polarity": polarity,
                    "opinion": evidence,
                    "evidence": [evidence],
                }
            ],
            "issue_types": (
                [{"issue": issue, "evidence": evidence}] if issue else []
            ),
            "purchase_motivations": [],
            "usage_scenarios": [],
            "speech_acts": [],
            "expectation_gap": {
                "present": False,
                "type": "none",
                "evidence": [],
            },
        },
    }


class AggregatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            record(
                "en_1",
                language="en",
                stars=1,
                aspect="product.usability.ease_of_use",
                polarity="negative",
                evidence="Hard to apply",
                issue="difficult_to_use",
            ),
            record(
                "es_1",
                language="es",
                stars=2,
                aspect="product.usability.ease_of_use",
                polarity="negative",
                evidence="Difícil de aplicar",
                issue="difficult_to_use",
            ),
        ]

    def test_counts_distinct_reviews_and_languages(self) -> None:
        report = aggregate_records(
            self.records,
            min_support=2,
            max_insights=15,
        )
        pain = report["tables"]["low_star_pain_points"][0]
        self.assertEqual(pain["support_reviews"], 2)
        self.assertEqual(pain["en_reviews"], 1)
        self.assertEqual(pain["es_reviews"], 1)

    def test_aspect_polarity_counts_are_language_specific(self) -> None:
        records = [
            record(
                "en_positive",
                language="en",
                stars=5,
                aspect="product.usability.ease_of_use",
                polarity="positive",
                evidence="Easy to apply",
            ),
            record(
                "es_negative",
                language="es",
                stars=1,
                aspect="product.usability.ease_of_use",
                polarity="negative",
                evidence="Difícil de aplicar",
            ),
        ]
        report = aggregate_records(records, min_support=2, max_insights=15)
        rows = report["tables"]["aspect_by_language"]
        english = next(row for row in rows if row["language"] == "en")
        spanish = next(row for row in rows if row["language"] == "es")
        self.assertEqual(english["positive_mentions"], 1)
        self.assertEqual(english["negative_mentions"], 0)
        self.assertEqual(english["positive_rate"], 1.0)
        self.assertEqual(spanish["positive_mentions"], 0)
        self.assertEqual(spanish["negative_mentions"], 1)
        self.assertEqual(spanish["negative_rate"], 1.0)

    def test_insight_has_two_traceable_quotes(self) -> None:
        report = aggregate_records(
            self.records,
            min_support=2,
            max_insights=15,
        )
        matching = [
            item
            for item in report["insights"]
            if item["insight_id"] == "low_star_issues:difficult_to_use"
        ]
        self.assertEqual(len(matching), 1)
        item = matching[0]
        self.assertEqual(
            item["data_evidence"]["source_review_ids"],
            ["en_1", "es_1"],
        )
        self.assertEqual(len(item["representative_quotes"]), 2)
        self.assertEqual(
            {quote["quote"] for quote in item["representative_quotes"]},
            {"Hard to apply", "Difícil de aplicar"},
        )

    def test_small_input_is_not_marked_ready(self) -> None:
        report = aggregate_records(
            self.records,
            min_support=2,
            max_insights=15,
        )
        self.assertEqual(
            report["summary"]["insight_readiness"],
            "insufficient_data",
        )
        self.assertTrue(report["sampling"]["is_small_sample"])
        self.assertFalse(report["sampling"]["is_weighted"])
        self.assertFalse(
            report["sampling"]["population_prevalence_supported"]
        )
        self.assertIn("exploratory", report["sampling"]["warning"])
        self.assertIsNone(report["scope"]["known_scope_records"])
        self.assertEqual(
            report["scope"]["scope_metadata_status"],
            "not_applicable_for_global_scope",
        )

    def test_product_scope_excludes_other_products_and_annotates_tables(self) -> None:
        records = [
            record(
                "p1_en",
                language="en",
                stars=1,
                aspect="product.usability.ease_of_use",
                polarity="negative",
                evidence="Hard to use",
                issue="difficult_to_use",
                product_id="P1",
                product_subcategory="serum",
            ),
            record(
                "p1_es",
                language="es",
                stars=2,
                aspect="product.usability.ease_of_use",
                polarity="negative",
                evidence="Difícil de usar",
                issue="difficult_to_use",
                product_id="P1",
                product_subcategory="serum",
            ),
            record(
                "p2_en",
                language="en",
                stars=1,
                aspect="product.sensory.scent",
                polarity="negative",
                evidence="Bad smell",
                issue="scent_problem",
                product_id="P2",
                product_subcategory="cleanser",
            ),
        ]
        report = aggregate_records(
            records,
            min_support=2,
            scope_field="product_id",
            scope_value="P1",
        )
        self.assertEqual(report["summary"]["records"], 2)
        self.assertEqual(report["scope"]["value"], "P1")
        self.assertEqual(report["scope"]["selected_records"], 2)
        pain = report["tables"]["low_star_pain_points"][0]
        self.assertEqual(pain["issue_code"], "difficult_to_use")
        self.assertEqual(pain["sample_size"], 2)
        self.assertEqual(pain["scope_value"], "P1")
        self.assertTrue(pain["small_sample_warning"])
        self.assertEqual(report["insights"][0]["analysis_scope"]["value"], "P1")
        insight = report["insights"][0]
        self.assertEqual(insight["scope"]["value"], "P1")
        self.assertEqual(insight["support_count"], 2)
        self.assertEqual(insight["support_rate"], 1.0)
        self.assertEqual(insight["action_type"], "product")
        self.assertTrue(insight["recommended_action"])
        self.assertEqual(
            insight["representative_review_ids"],
            insight["data_evidence"]["source_review_ids"],
        )
        self.assertTrue(insight["limitations"])

    def test_unknown_scope_cannot_be_presented_as_product_analysis(self) -> None:
        with self.assertRaisesRegex(ValueError, "known source value"):
            aggregate_records(
                self.records,
                min_support=2,
                scope_field="product_id",
                scope_value="unknown",
            )

    def test_traceability_validator_rejects_changed_quote(self) -> None:
        report = aggregate_records(
            self.records,
            min_support=2,
            max_insights=15,
        )
        report["insights"][0]["representative_quotes"][0]["quote"] = (
            "not in source"
        )
        failures = validate_report_traceability(report, self.records)
        self.assertTrue(any("not exact source text" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
