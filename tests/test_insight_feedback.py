import json
import tempfile
import unittest
from pathlib import Path

from src.insight_feedback import FeedbackStore, create_feedback_event


class InsightFeedbackTests(unittest.TestCase):
    def test_store_appends_history_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feedback" / "events.jsonl"
            store = FeedbackStore(path)
            first = create_feedback_event(
                "INS-001",
                event_type="decision_update",
                actor="reviewer@example.com",
                status="needs_validation",
                owner="product-ops",
                priority="high",
                due_date="2026-08-18",
                note="复核包装失败路径",
                event_id="event-1",
                created_at="2026-08-08T01:00:00+00:00",
            )
            second = create_feedback_event(
                "INS-001",
                event_type="quality_flag",
                actor="reviewer@example.com",
                status="needs_validation",
                priority="high",
                flag_type="insufficient_evidence",
                note="需要补充同一商品样本",
                event_id="event-2",
                created_at="2026-08-08T02:00:00+00:00",
            )

            store.append(first)
            original_line = path.read_text(encoding="utf-8").splitlines()[0]
            store.append(second)

            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0], original_line)
            self.assertEqual(json.loads(lines[1])["flag_type"], "insufficient_evidence")
            self.assertEqual(list(store.for_insight("INS-001")), [first, second])
            self.assertEqual(store.latest_by_insight()["INS-001"], second)

    def test_rejects_invalid_workflow_values(self):
        with self.assertRaisesRegex(ValueError, "unsupported status"):
            create_feedback_event(
                "INS-001", event_type="decision_update", actor="reviewer", status="done"
            )
        with self.assertRaisesRegex(ValueError, "flag_type"):
            create_feedback_event(
                "INS-001", event_type="quality_flag", actor="reviewer", flag_type=""
            )
        with self.assertRaises(ValueError):
            create_feedback_event(
                "INS-001",
                event_type="decision_update",
                actor="reviewer",
                due_date="08/18/2026",
            )


if __name__ == "__main__":
    unittest.main()
