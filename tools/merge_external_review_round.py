"""Merge unchanged and rerun external reviews without weakening hash binding.

The script is offline. It reuses a prior result only when its item hash still
matches the current frozen input, validates every rerun result against that
input, verifies result-part parity, and writes a new auditable JSONL artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ai_review_workflow import (  # noqa: E402
    _atomic_write_json,
    _atomic_write_text,
    canonical_json,
    load_json,
    load_jsonl,
    sha256_json,
    validate_config,
    validate_external_reviews,
    validate_items,
)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique_by_item(
    rows: list[dict[str, Any]], *, source_name: str
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        item_id = row.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError(f"{source_name} contains a result without item_id")
        if item_id in indexed:
            raise ValueError(f"{source_name} contains duplicate item_id {item_id}")
        indexed[item_id] = row
    return indexed


def _validate_result_parts(
    parts_dir: Path, rerun_by_item: dict[str, dict[str, Any]]
) -> None:
    expected = {
        parts_dir / f"{item_id}.result.json" for item_id in rerun_by_item
    }
    actual = set(parts_dir.glob("*.result.json"))
    if actual != expected:
        missing = sorted(path.name for path in expected - actual)
        stale = sorted(path.name for path in actual - expected)
        raise ValueError(
            f"rerun result parts mismatch; missing={missing}, stale={stale}"
        )
    for item_id, result in rerun_by_item.items():
        path = parts_dir / f"{item_id}.result.json"
        part = load_json(path)
        if sha256_json(part) != sha256_json(result):
            raise ValueError(f"result part differs from rerun JSONL for {item_id}")


def merge(
    *,
    config_path: Path,
    input_path: Path,
    prior_path: Path,
    rerun_path: Path,
    rerun_parts_dir: Path,
    output_path: Path,
    manifest_path: Path,
    expected_rerun_count: int,
) -> dict[str, Any]:
    resolved_output = output_path.resolve()
    if ".private" not in resolved_output.parts:
        raise ValueError("merged external reviews must be written under .private")
    if resolved_output in {prior_path.resolve(), rerun_path.resolve()}:
        raise ValueError("merged output must not overwrite either source result file")
    if expected_rerun_count < 1:
        raise ValueError("expected rerun count must be positive")

    config = load_json(config_path)
    validate_config(config)
    items = load_jsonl(input_path)
    validate_items(items, config["project"])
    item_by_id = {item["item_id"]: item for item in items}

    prior_rows = load_jsonl(prior_path)
    rerun_rows = load_jsonl(rerun_path)
    prior_by_item = _unique_by_item(prior_rows, source_name="prior results")
    rerun_by_item = _unique_by_item(rerun_rows, source_name="rerun results")
    if len(rerun_by_item) != expected_rerun_count:
        raise ValueError(
            f"expected {expected_rerun_count} rerun results, found {len(rerun_by_item)}"
        )
    unknown_reruns = sorted(set(rerun_by_item) - set(item_by_id))
    if unknown_reruns:
        raise ValueError(f"rerun results contain unknown items: {unknown_reruns}")

    _validate_result_parts(rerun_parts_dir, rerun_by_item)
    validate_external_reviews(items, config, rerun_rows)

    reusable_prior: dict[str, dict[str, Any]] = {}
    for item_id, item in item_by_id.items():
        result = prior_by_item.get(item_id)
        if result is not None and result.get("input_sha256") == sha256_json(item):
            reusable_prior[item_id] = result
    overlap = sorted(set(reusable_prior) & set(rerun_by_item))
    if overlap:
        raise ValueError(
            "rerun results overlap unchanged reusable results: " + ", ".join(overlap)
        )
    validate_external_reviews(
        items, config, list(reusable_prior.values())
    )

    merged: list[dict[str, Any]] = []
    for item in items:
        item_id = item["item_id"]
        result = rerun_by_item.get(item_id) or reusable_prior.get(item_id)
        if result is None:
            raise ValueError(f"no current external review is available for {item_id}")
        merged.append(result)
    validate_external_reviews(items, config, merged)

    output_text = "".join(canonical_json(row) + "\n" for row in merged)
    _atomic_write_text(output_path, output_text)
    decisions = Counter(row["decision"] for row in merged)
    severities = Counter(
        finding["severity"]
        for row in merged
        for finding in row.get("findings", [])
    )
    manifest = {
        "schema_version": "1.0",
        "status": "merged_and_validated_without_api_calls",
        "project": config["project"],
        "model_api_calls_made": 0,
        "current_input_sha256": sha256_json(items),
        "current_item_count": len(items),
        "prior_result_count": len(prior_rows),
        "reused_prior_results": len(reusable_prior),
        "discarded_stale_prior_results": len(prior_rows) - len(reusable_prior),
        "rerun_results": len(rerun_rows),
        "merged_results": len(merged),
        "decisions": dict(sorted(decisions.items())),
        "findings": dict(sorted(severities.items())),
        "source_files": {
            "input": {
                "path": str(input_path.resolve()),
                "file_sha256": _file_sha256(input_path),
            },
            "prior_results": {
                "path": str(prior_path.resolve()),
                "file_sha256": _file_sha256(prior_path),
            },
            "rerun_results": {
                "path": str(rerun_path.resolve()),
                "file_sha256": _file_sha256(rerun_path),
            },
        },
        "output": {
            "path": str(output_path.resolve()),
            "file_sha256": _file_sha256(output_path),
            "results_sha256": sha256_json(merged),
        },
    }
    _atomic_write_json(manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge hash-matching prior reviews with validated rerun reviews"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--prior-results", type=Path, required=True)
    parser.add_argument("--rerun-results", type=Path, required=True)
    parser.add_argument("--rerun-parts-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-rerun-count", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = merge(
        config_path=args.config,
        input_path=args.input,
        prior_path=args.prior_results,
        rerun_path=args.rerun_results,
        rerun_parts_dir=args.rerun_parts_dir,
        output_path=args.output,
        manifest_path=args.manifest,
        expected_rerun_count=args.expected_rerun_count,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
