import unittest

from src.evaluation_challenge import CHALLENGE_CATEGORIES, coverage_summary, select_challenge_rows


class EvaluationChallengeTests(unittest.TestCase):
    def test_selection_is_deterministic_disjoint_and_balanced(self):
        rows = []
        templates = {
            "neutral": "It arrived and I used the product for a normal daily routine without another comment",
            "mixed": "I like the texture but the dispenser is difficult to use after a week",
            "long": " ".join(["Detailed experience with the product"] * 18),
            "multi": "First topic works well for the routine. Second topic needs more care during use. Third topic covers the packaging and dispenser. Fourth topic explains the price and quantity. Final note compares the overall value with another option.",
            "implicit": "After I use this at night my skin feels different during the morning routine",
        }
        for language in ("en", "es"):
            for name, text in templates.items():
                for index in range(3):
                    rows.append({
                        "review_id": f"{language}_{name}_{index}",
                        "language": language,
                        "stars": "3" if name == "neutral" else "4",
                        "review_title": name,
                        "review_body": text,
                        "product_category": "beauty",
                    })
        first = select_challenge_rows(rows, excluded_review_ids=set(), per_category_language=1)
        second = select_challenge_rows(rows, excluded_review_ids=set(), per_category_language=1)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 10)
        self.assertEqual(len({row["review_id"] for row in first}), 10)
        summary = coverage_summary(first)
        self.assertEqual(set(summary["category_counts"]), set(CHALLENGE_CATEGORIES))
        self.assertEqual(summary["language_counts"], {"en": 5, "es": 5})

    def test_excluded_ids_are_never_selected(self):
        rows = [{
            "review_id": "en_excluded",
            "language": "en",
            "stars": "3",
            "review_title": "plain",
            "review_body": "A plain product note with enough words for the neutral candidate selection",
            "product_category": "beauty",
        }]
        with self.assertRaisesRegex(ValueError, "insufficient"):
            select_challenge_rows(rows, excluded_review_ids={"en_excluded"}, per_category_language=1)


if __name__ == "__main__":
    unittest.main()
