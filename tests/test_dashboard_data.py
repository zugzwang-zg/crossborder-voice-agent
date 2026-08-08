from __future__ import annotations

import unittest

from scripts.prepare_dashboard_data import compact_record


class DashboardDataTests(unittest.TestCase):
    def test_compact_record_preserves_known_product_scope(self) -> None:
        compact = compact_record(
            {
                "review_id": "review_001",
                "source": {
                    "language": "en",
                    "stars": 4,
                    "title": "Useful",
                    "body": "Easy to apply.",
                    "product_id": "P-001",
                    "product_title": "Daily Serum",
                    "product_subcategory": "serum",
                    "review_date": "2026-08-08",
                },
                "analysis": {
                    "sentiment": "positive",
                    "sentiment_intensity": 2,
                    "confidence": 0.9,
                    "aspects": [],
                    "issue_types": [],
                    "purchase_motivations": [],
                    "usage_scenarios": [],
                    "speech_acts": [],
                    "recommended_actions": [],
                },
            }
        )
        self.assertEqual(compact["productId"], "P-001")
        self.assertEqual(compact["productTitle"], "Daily Serum")
        self.assertEqual(compact["productSubcategory"], "serum")
        self.assertEqual(compact["reviewDate"], "2026-08-08")

    def test_compact_record_marks_missing_scope_as_unknown(self) -> None:
        compact = compact_record(
            {
                "review_id": "review_002",
                "source": {
                    "language": "es",
                    "stars": 3,
                    "title": "",
                    "body": "Texto.",
                },
                "analysis": {
                    "sentiment": "neutral",
                    "sentiment_intensity": 1,
                    "confidence": 0.8,
                    "aspects": [],
                    "issue_types": [],
                    "purchase_motivations": [],
                    "usage_scenarios": [],
                    "speech_acts": [],
                    "recommended_actions": [],
                },
            }
        )
        self.assertEqual(compact["productId"], "unknown")
        self.assertEqual(compact["productSubcategory"], "unknown")
        self.assertEqual(compact["reviewDate"], "unknown")


if __name__ == "__main__":
    unittest.main()
