import unittest

from src.insight_comparison import compare_insight_versions


class InsightComparisonTests(unittest.TestCase):
    def test_reports_added_removed_and_support_changes(self):
        diff = compare_insight_versions(
            [
                {"insight_id": "A", "title": "Alpha", "support_count": 4},
                {"insight_id": "B", "title": "Beta", "data_evidence": {"support_reviews": 7}},
            ],
            [
                {"insight_id": "B", "title": "Beta", "data_evidence": {"support_reviews": 10}},
                {"insight_id": "C", "title": "Gamma", "support_count": 2},
            ],
        )
        self.assertEqual(diff.added, ("C",))
        self.assertEqual(diff.removed, ("A",))
        self.assertEqual(diff.changed[0].delta, 3)
        self.assertEqual(diff.changed[0].title, "Beta")

    def test_rejects_duplicate_ids(self):
        with self.assertRaisesRegex(ValueError, "duplicate insight_id"):
            compare_insight_versions(
                [{"insight_id": "A"}, {"insight_id": "A"}],
                [],
            )


if __name__ == "__main__":
    unittest.main()
