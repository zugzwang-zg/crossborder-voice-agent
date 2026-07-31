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
) -> dict:
    return {
        "review_id": review_id,
        "source": {
            "language": language,
            "stars": stars,
            "title": "",
            "body": evidence,
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
