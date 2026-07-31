"""Create a deterministic, balanced sample for public offline smoke tests."""

from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "data" / "processed" / "reviews_cleaned.csv"
OUTPUT = PROJECT_ROOT / "data" / "sample" / "demo_reviews.csv"
FIELDS = [
    "review_id",
    "language",
    "stars",
    "review_title",
    "review_body",
    "product_category",
]


def main() -> int:
    selected: dict[tuple[str, int], dict[str, str]] = {}
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row["language"], int(row["stars"]))
            if key not in selected:
                selected[key] = {field: row[field] for field in FIELDS}
            if len(selected) == 10:
                break

    expected = {(language, stars) for language in ("en", "es") for stars in range(1, 6)}
    if set(selected) != expected:
        missing = sorted(expected - set(selected))
        raise RuntimeError(f"Could not build balanced public sample; missing {missing}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for key in sorted(selected):
            writer.writerow(selected[key])

    print(f"Wrote {len(selected)} rows to {OUTPUT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
