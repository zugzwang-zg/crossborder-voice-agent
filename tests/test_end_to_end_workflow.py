"""Regression coverage for the review-to-insight human feedback workflow."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.prepare_dashboard_data import compact_record
from src.insight_aggregator import aggregate_records, validate_report_traceability
from src.insight_feedback import FeedbackStore, create_feedback_event
from src.model_evaluator import version_metrics
from src.review_contract import normalize_reviews, source_record


class EndToEndWorkflowTests(unittest.TestCase):
    def test_review_contract_evaluation_insight_dashboard_and_feedback(self) -> None:
        rows = [
            {
                "review_id": "en-e2e-1",
                "language": "en",
                "stars": "1",
                "review_title": "Hard to use",
                "review_body": "The applicator is hard to use.",
                "product_id": "P-E2E",
                "product_title": "Test serum",
                "category": "beauty",
                "subcategory": "serum",
            },
            {
                "review_id": "es-e2e-1",
                "language": "es",
                "stars": "2",
                "review_title": "Difícil",
                "review_body": "El aplicador es difícil de usar.",
                "product_id": "P-E2E",
                "product_title": "Test serum",
                "category": "beauty",
                "subcategory": "serum",
            },
        ]
        normalized = normalize_reviews(rows)
        records = []
        for review in normalized:
            body = review["review_body"]
            records.append(
                {
                    "review_id": review["review_id"],
                    "source": source_record(review),
                    "analysis": {
                        "sentiment": "negative",
                        "sentiment_intensity": 0.9,
                        "sentiment_evidence": [body],
                        "confidence": 0.92,
                        "aspects": [
                            {
                                "aspect": "product.usability.ease_of_use",
                                "polarity": "negative",
                                "opinion": body,
                                "evidence": [body],
                            }
                        ],
                        "issue_types": [
                            {"issue": "difficult_to_use", "evidence": body}
                        ],
                        "purchase_motivations": [],
                        "usage_scenarios": [],
                        "speech_acts": [],
                        "recommended_actions": [],
                        "expectation_gap": {
                            "present": False,
                            "type": "none",
                            "evidence": [],
                        },
                    },
                }
            )

        gold = [
            {
                "review_id": row["review_id"],
                "language": row["language"],
                "gold_sentiment": "negative",
                "gold_aspects": "product.usability.ease_of_use",
                "gold_issue": "difficult_to_use",
                "review_body": row["review_body"],
                "review_title": row["review_title"],
            }
            for row in rows
        ]
        metrics = version_metrics(gold, records)
        self.assertEqual(metrics["sentiment"]["macro_f1"], 1.0)
        self.assertEqual(metrics["aspects"]["f1"], 1.0)
        self.assertEqual(metrics["issues"]["macro_f1"], 1.0)

        report = aggregate_records(
            records,
            min_support=2,
            scope_field="product_id",
            scope_value="P-E2E",
        )
        self.assertEqual(validate_report_traceability(report, records), [])
        compact = [compact_record(record) for record in records]
        evidence_ids = set(report["insights"][0]["data_evidence"]["source_review_ids"])
        self.assertTrue(evidence_ids.issubset({item["id"] for item in compact}))

        with tempfile.TemporaryDirectory() as directory:
            store = FeedbackStore(Path(directory) / "events.jsonl")
            store.append(
                create_feedback_event(
                    report["insights"][0]["insight_id"],
                    event_type="decision_update",
                    actor="reviewer@example.com",
                    status="accepted",
                    note="Evidence checked against both source reviews.",
                    event_id="feedback-e2e-001",
                    created_at="2026-08-08T08:00:00+00:00",
                )
            )
            latest = store.latest_by_insight()[report["insights"][0]["insight_id"]]
            self.assertEqual(latest.status, "accepted")
            self.assertEqual(latest.event_id, "feedback-e2e-001")


if __name__ == "__main__":
    unittest.main()
