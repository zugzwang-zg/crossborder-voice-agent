"""Freeze a held-out challenge-input extension without inventing gold labels."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Iterable


CHALLENGE_CATEGORIES = (
    "neutral_candidate",
    "mixed_candidate",
    "long_review",
    "multi_topic",
    "implicit_attribute",
)
LANGUAGES = ("en", "es")
_CONTRAST = re.compile(r"\b(but|however|although|though|yet|pero|aunque|sin embargo)\b", re.I)
_SCENARIO = re.compile(r"\b(after|before|during|when|while|despu[eé]s|antes|durante|cuando|al usar|me deja|feels?)\b", re.I)


def _words(row: dict[str, str]) -> list[str]:
    return re.findall(r"\b[\wáéíóúüñ]+\b", f"{row.get('review_title', '')} {row.get('review_body', '')}", re.I)


def _eligible(row: dict[str, str], category: str) -> bool:
    text = f"{row.get('review_title', '')} {row.get('review_body', '')}".strip()
    word_count = len(_words(row))
    if category == "neutral_candidate":
        return row.get("stars") == "3" and 8 <= word_count <= 60 and "!" not in text and not _CONTRAST.search(text)
    if category == "mixed_candidate":
        return word_count >= 14 and bool(_CONTRAST.search(text))
    if category == "long_review":
        return word_count >= 70
    if category == "multi_topic":
        sentence_marks = sum(text.count(mark) for mark in ".;!?。；！？")
        return word_count >= 35 and (sentence_marks >= 3 or text.count(",") >= 4)
    if category == "implicit_attribute":
        return word_count >= 12 and bool(_SCENARIO.search(text))
    raise ValueError(f"unknown challenge category: {category}")


def _rank(seed: str, category: str, row: dict[str, str]) -> str:
    value = f"{seed}\0{category}\0{row['review_id']}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def select_challenge_rows(
    rows: Iterable[dict[str, str]],
    *,
    excluded_review_ids: set[str],
    per_category_language: int = 4,
    seed: str = "crossborder-voice-challenge-v1",
) -> list[dict[str, str]]:
    """Select a deterministic, disjoint 5-category × 2-language challenge set."""
    source = [
        dict(row) for row in rows
        if row.get("review_id") not in excluded_review_ids and row.get("language") in LANGUAGES
    ]
    selected: list[dict[str, str]] = []
    used: set[str] = set()
    for category in CHALLENGE_CATEGORIES:
        for language in LANGUAGES:
            pool = sorted(
                (
                    row for row in source
                    if row["language"] == language
                    and row["review_id"] not in used
                    and _eligible(row, category)
                ),
                key=lambda row: _rank(seed, category, row),
            )
            if len(pool) < per_category_language:
                raise ValueError(
                    f"insufficient {category}/{language} candidates: "
                    f"need {per_category_language}, found {len(pool)}"
                )
            for row in pool[:per_category_language]:
                used.add(row["review_id"])
                selected.append({**row, "challenge_category": category})
    return selected


def coverage_summary(rows: Iterable[dict[str, str]]) -> dict[str, object]:
    items = list(rows)
    return {
        "records": len(items),
        "unique_review_ids": len({row["review_id"] for row in items}),
        "language_counts": dict(sorted(Counter(row["language"] for row in items).items())),
        "category_counts": dict(sorted(Counter(row["challenge_category"] for row in items).items())),
    }
