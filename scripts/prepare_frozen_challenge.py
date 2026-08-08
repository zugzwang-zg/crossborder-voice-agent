"""Freeze challenge inputs and a blank two-reviewer annotation sheet."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation_challenge import coverage_summary, select_challenge_rows


RAW_PATH = PROJECT_ROOT / "data" / "raw" / "amazon_reviews_raw.csv"
GOLD_PATH = PROJECT_ROOT / "data" / "annotation" / "gold_sample.csv"
DEV_PATH = PROJECT_ROOT / "data" / "development" / "dev_sample.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation"
INPUT_PATH = OUTPUT_DIR / "frozen_challenge_input_40.csv"
REVIEW_PATH = OUTPUT_DIR / "frozen_challenge_annotation_review.csv"
MANIFEST_PATH = PROJECT_ROOT / "reports" / "frozen_challenge_manifest.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def main() -> int:
    missing = [str(path) for path in (RAW_PATH, GOLD_PATH, DEV_PATH) if not path.exists()]
    if missing:
        raise RuntimeError("missing local evaluation inputs: " + ", ".join(missing))
    raw = read_csv(RAW_PATH)
    gold_ids = {row["review_id"] for row in read_csv(GOLD_PATH)}
    dev_ids = {row["review_id"] for row in read_csv(DEV_PATH)}
    selected = select_challenge_rows(raw, excluded_review_ids=gold_ids | dev_ids)
    input_fields = [
        "review_id", "language", "stars", "review_title", "review_body",
        "product_category", "challenge_category",
    ]
    write_csv(INPUT_PATH, selected, input_fields)
    review_rows = [{
        **row,
        "reviewer_a_sentiment": "",
        "reviewer_a_aspects": "",
        "reviewer_a_issues": "",
        "reviewer_b_sentiment": "",
        "reviewer_b_aspects": "",
        "reviewer_b_issues": "",
        "adjudicated_sentiment": "",
        "adjudicated_aspects": "",
        "adjudicated_issues": "",
        "adjudication_notes": "",
        "annotation_status": "pending_independent_review",
    } for row in selected]
    write_csv(REVIEW_PATH, review_rows, [*input_fields, *[field for field in review_rows[0] if field not in input_fields]])
    manifest = {
        "schema_version": "1.0",
        "status": "frozen_awaiting_independent_annotation",
        "dataset_role": "held_out_challenge_extension_not_in_headline_metrics",
        "seed": "crossborder-voice-challenge-v1",
        "selection": coverage_summary(selected),
        "excluded_existing_gold_records": len(gold_ids),
        "excluded_prompt_development_records": len(dev_ids),
        "overlap_with_existing_gold": len({row["review_id"] for row in selected} & gold_ids),
        "overlap_with_prompt_development": len({row["review_id"] for row in selected} & dev_ids),
        "target_categories_are_selection_heuristics_not_gold_labels": True,
        "headline_metrics_included": False,
        "promotion_gate": (
            "Two independent reviewers must label sentiment, aspects and issues; "
            "disagreements must be adjudicated before predictions are generated or metrics are updated."
        ),
        "sha256": {
            "frozen_input": file_sha256(INPUT_PATH),
            "blank_annotation_review": file_sha256(REVIEW_PATH),
            "existing_gold": file_sha256(GOLD_PATH),
            "development_sample": file_sha256(DEV_PATH),
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
