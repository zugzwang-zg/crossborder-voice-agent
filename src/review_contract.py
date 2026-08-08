"""Canonical input contract for traceable review records.

The model output schema intentionally contains analysis fields only. Product
metadata is validated before inference and copied into each output record's
``source`` object so downstream aggregation can scope findings without asking
the model to repeat or infer identifiers.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


REVIEW_CONTRACT_VERSION = "1.0.0"
UNKNOWN_VALUE = "unknown"

REQUIRED_INPUT_FIELDS = {
    "review_id",
    "language",
    "stars",
    "review_title",
    "review_body",
}

METADATA_ALIASES: dict[str, tuple[str, ...]] = {
    "product_id": ("product_id",),
    "product_title": ("product_title",),
    "brand": ("brand",),
    "product_category": ("product_category", "category"),
    "product_subcategory": ("product_subcategory", "subcategory"),
    "review_date": ("review_date",),
    "locale_or_market_proxy": (
        "locale_or_market_proxy",
        "locale",
        "market_proxy",
    ),
}


class ReviewContractError(ValueError):
    """Raised when an input review violates the source-data contract."""


def validate_input_columns(fieldnames: Iterable[str] | None) -> None:
    columns = set(fieldnames or [])
    missing = REQUIRED_INPUT_FIELDS - columns
    if missing:
        raise ReviewContractError(
            f"Input CSV missing columns: {sorted(missing)}"
        )


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _metadata_value(row: Mapping[str, Any], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        value = _clean(row.get(alias))
        if value:
            return value
    return UNKNOWN_VALUE


def normalize_review(
    row: Mapping[str, Any],
    *,
    row_number: int | None = None,
) -> dict[str, str]:
    """Validate one CSV row and return only canonical, non-inferred fields."""

    location = f" at row {row_number}" if row_number is not None else ""
    review_id = _clean(row.get("review_id"))
    if not review_id:
        raise ReviewContractError(f"review_id must be non-empty{location}")

    language = _clean(row.get("language")).lower()
    if language not in {"en", "es"}:
        raise ReviewContractError(
            f"language must be 'en' or 'es'{location}: {language!r}"
        )

    raw_stars = _clean(row.get("stars"))
    try:
        numeric_stars = float(raw_stars)
    except ValueError as error:
        raise ReviewContractError(
            f"stars must be numeric{location}: {raw_stars!r}"
        ) from error
    if not numeric_stars.is_integer() or not 1 <= numeric_stars <= 5:
        raise ReviewContractError(
            f"stars must be an integer from 1 to 5{location}: {raw_stars!r}"
        )

    title = _clean(row.get("review_title"))
    body = _clean(row.get("review_body"))
    if not title and not body:
        raise ReviewContractError(
            f"review_title and review_body cannot both be empty{location}"
        )

    normalized = {
        "review_id": review_id,
        "language": language,
        "stars": str(int(numeric_stars)),
        "review_title": title,
        "review_body": body,
    }
    normalized.update(
        {
            field: _metadata_value(row, aliases)
            for field, aliases in METADATA_ALIASES.items()
        }
    )
    return normalized


def normalize_reviews(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        item = normalize_review(row, row_number=row_number)
        review_id = item["review_id"]
        if review_id in seen_ids:
            raise ReviewContractError(
                f"Duplicate review_id at row {row_number}: {review_id}"
            )
        seen_ids.add(review_id)
        normalized.append(item)
    return normalized


def source_record(review: Mapping[str, str]) -> dict[str, Any]:
    """Build the canonical traceability object stored beside model output."""

    return {
        "contract_version": REVIEW_CONTRACT_VERSION,
        "language": review["language"],
        "stars": int(review["stars"]),
        "title": review.get("review_title", ""),
        "body": review.get("review_body", ""),
        **{
            field: review.get(field, UNKNOWN_VALUE) or UNKNOWN_VALUE
            for field in METADATA_ALIASES
        },
    }


__all__ = [
    "METADATA_ALIASES",
    "REVIEW_CONTRACT_VERSION",
    "ReviewContractError",
    "normalize_review",
    "normalize_reviews",
    "source_record",
    "validate_input_columns",
]
