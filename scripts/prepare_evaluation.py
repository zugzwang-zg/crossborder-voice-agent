"""Prepare frozen evaluation inputs without exposing gold labels."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = PROJECT_ROOT / "data" / "annotation" / "gold_sample.csv"
FORMAL_PREDICTIONS_PATH = (
    PROJECT_ROOT / "data" / "processed" / "review_analysis_v11.jsonl"
)
OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation"
INPUT_PATH = OUTPUT_DIR / "gold_input_100.csv"
IMPROVED_PATH = OUTPUT_DIR / "improved_predictions.jsonl"
MANIFEST_PATH = OUTPUT_DIR / "evaluation_manifest.json"
BASELINE_PROMPT = PROJECT_ROOT / "prompts" / "v1_basic_prompt.md"
IMPROVED_PROMPT = (
    PROJECT_ROOT / "prompts" / "v9_consistency_guard_prompt.md"
)

INPUT_FIELDS = [
    "review_id",
    "language",
    "stars",
    "review_title",
    "review_body",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    f"Invalid JSONL at {path}:{line_number}: {error}"
                ) from error
    return records


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    gold = read_csv(GOLD_PATH)
    if len(gold) != 100:
        raise RuntimeError(f"Expected 100 gold rows, found {len(gold)}")
    gold_ids = [row["review_id"] for row in gold]
    if len(set(gold_ids)) != 100:
        raise RuntimeError("Gold evaluation set contains duplicate review IDs")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with INPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INPUT_FIELDS)
        writer.writeheader()
        for row in gold:
            writer.writerow({field: row[field] for field in INPUT_FIELDS})

    formal = read_jsonl(FORMAL_PREDICTIONS_PATH)
    formal_by_id = {record["review_id"]: record for record in formal}
    missing_improved = [
        review_id for review_id in gold_ids if review_id not in formal_by_id
    ]
    if missing_improved:
        raise RuntimeError(
            "Formal predictions are missing frozen evaluation IDs: "
            + ", ".join(missing_improved)
        )
    with IMPROVED_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for review_id in gold_ids:
            handle.write(
                json.dumps(formal_by_id[review_id], ensure_ascii=False) + "\n"
            )

    manifest = {
        "status": "ready_for_baseline",
        "dataset_role": "frozen_held_out_final_evaluation",
        "gold_records": len(gold),
        "gold_unique_review_ids": len(set(gold_ids)),
        "language_counts": {
            language: sum(row["language"] == language for row in gold)
            for language in ("en", "es")
        },
        "labels_removed_from_model_input": True,
        "model_input_fields": INPUT_FIELDS,
        "improved_predictions_reused_from_formal_run": len(gold_ids),
        "additional_improved_api_calls": 0,
        "comparison": {
            "model": "gpt-5.6-luna",
            "baseline_prompt": "v1_basic",
            "improved_prompt": "v9_consistency_guard",
            "shared_structured_output_schema": "1.7.0",
            "shared_schema_note": (
                "The strict output schema is held constant so the comparison "
                "isolates prompt guidance, taxonomy rules, evidence rules, "
                "consistency guards, and examples."
            ),
        },
        "files": {
            "gold": str(GOLD_PATH),
            "model_input": str(INPUT_PATH),
            "improved_predictions": str(IMPROVED_PATH),
        },
        "sha256": {
            "gold": sha256_file(GOLD_PATH),
            "model_input": sha256_file(INPUT_PATH),
            "improved_predictions": sha256_file(IMPROVED_PATH),
            "baseline_prompt": sha256_file(BASELINE_PROMPT),
            "improved_prompt": sha256_file(IMPROVED_PROMPT),
        },
    }
    write_json(MANIFEST_PATH, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
