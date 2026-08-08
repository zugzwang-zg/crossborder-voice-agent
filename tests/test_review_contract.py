"""Tests for the canonical review source-data contract."""

from __future__ import annotations

import unittest

from src.review_contract import (
    REVIEW_CONTRACT_VERSION,
    ReviewContractError,
    normalize_review,
    normalize_reviews,
    source_record,
)


class ReviewContractTests(unittest.TestCase):
    def test_metadata_aliases_are_canonicalized_without_inference(self) -> None:
        review = normalize_review(
            {
                "review_id": "en_1",
                "language": "EN",
                "stars": "5.0",
                "review_title": "Works",
                "review_body": "Works for me.",
                "product_id": "P-001",
                "product_title": "Example serum",
                "category": "beauty",
                "subcategory": "serum",
            }
        )
        self.assertEqual(review["product_category"], "beauty")
        self.assertEqual(review["product_subcategory"], "serum")
        self.assertEqual(review["brand"], "unknown")
        self.assertEqual(review["stars"], "5")

        source = source_record(review)
        self.assertEqual(source["contract_version"], REVIEW_CONTRACT_VERSION)
        self.assertEqual(source["product_id"], "P-001")
        self.assertEqual(source["brand"], "unknown")

    def test_duplicate_review_ids_are_rejected(self) -> None:
        row = {
            "review_id": "same",
            "language": "en",
            "stars": "4",
            "review_title": "Good",
            "review_body": "Good product.",
        }
        with self.assertRaisesRegex(ReviewContractError, "Duplicate review_id"):
            normalize_reviews([row, row])

    def test_invalid_star_and_empty_text_are_rejected(self) -> None:
        base = {
            "review_id": "en_1",
            "language": "en",
            "stars": "6",
            "review_title": "",
            "review_body": "",
        }
        with self.assertRaisesRegex(ReviewContractError, "stars"):
            normalize_review(base)
        base["stars"] = "3"
        with self.assertRaisesRegex(ReviewContractError, "cannot both be empty"):
            normalize_review(base)


if __name__ == "__main__":
    unittest.main()
