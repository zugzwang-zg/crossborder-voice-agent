"""Freeze the real v0.2 release-candidate insights for AI pre-review.

This tool is deliberately offline. It verifies the public insight artifact
against the review-level aggregation inputs, then writes deterministic private
input and provenance files. It never calls or authorizes a model provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.insight_aggregator import _selected_evidence, build_groups  # noqa: E402
from tools.ai_review_workflow import sha256_json, validate_items  # noqa: E402


DEFAULT_CONFIG = ROOT / "config" / "ai_review_release_candidate.json"
DEFAULT_OUTPUT = ROOT / ".private" / "ai_review" / "release-candidate" / "v0.2.0-rc.1"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(value)
    return rows


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_id(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value).strip("-")


def _resolve_sources(config: dict[str, Any]) -> dict[str, Path]:
    sources = config.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("release-candidate config requires sources")
    resolved: dict[str, Path] = {}
    for name, relative in sources.items():
        if not isinstance(relative, str) or not relative:
            raise ValueError(f"source {name} must be a non-empty path")
        path = (ROOT / relative).resolve()
        if not path.is_file():
            raise ValueError(f"source {name} does not exist: {relative}")
        resolved[name] = path
    return resolved


def _verify_insight(insight: dict[str, Any], groups: dict[str, Any]) -> tuple[Any, list[dict[str, Any]]]:
    insight_id = insight.get("insight_id")
    if not isinstance(insight_id, str) or ":" not in insight_id:
        raise ValueError("every release insight requires a family:code insight_id")
    family, code = insight_id.split(":", 1)
    try:
        bucket = groups[family][code]
    except KeyError as exc:
        raise ValueError(f"insight {insight_id} does not resolve in aggregation inputs") from exc

    expected_evidence = _selected_evidence(bucket, family=family, code=code)
    checks = {
        "support_count": (insight.get("support_count"), bucket.support_count),
        "data_evidence.support_reviews": (
            insight.get("data_evidence", {}).get("support_reviews"), bucket.support_count
        ),
        "representative_review_ids": (
            insight.get("representative_review_ids"), sorted(bucket.review_ids)
        ),
        "data_evidence.source_review_ids": (
            insight.get("data_evidence", {}).get("source_review_ids"), sorted(bucket.review_ids)
        ),
        "affected_audience.languages": (
            insight.get("affected_audience", {}).get("languages"), dict(bucket.languages)
        ),
        "affected_audience.star_distribution": (
            insight.get("affected_audience", {}).get("star_distribution"),
            {str(star): bucket.stars[star] for star in range(1, 6)},
        ),
        "representative_quotes": (insight.get("representative_quotes"), expected_evidence),
    }
    for field, (actual, expected) in checks.items():
        if actual != expected:
            raise ValueError(f"insight {insight_id} has stale or inconsistent {field}")
    return bucket, expected_evidence


def build_items(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    sources = _resolve_sources(config)
    release = _load_json(sources["release_manifest"])
    if release.get("candidate_version") != config.get("candidate_version"):
        raise ValueError("configured candidate_version does not match release_manifest.json")
    report = _load_json(sources["candidate_insights"])
    records = _load_jsonl(sources["review_analyses"])
    if report.get("summary", {}).get("records") != len(records):
        raise ValueError("consumer insight record count does not match review analyses")
    groups = build_groups(records)
    selected_review_ids = sorted(record["review_id"] for record in records)
    min_support = int(report.get("summary", {}).get("min_support", 0))
    if min_support <= 0:
        raise ValueError("candidate insight report requires a positive min_support")
    methodology = sources["methodology"].read_text(encoding="utf-8")
    operations_methodology = sources["operations_methodology"].read_text(
        encoding="utf-8"
    )
    data_boundary = sources["data_boundary"].read_text(encoding="utf-8")
    insights = report.get("insights")
    if not isinstance(insights, list):
        raise ValueError("candidate insight report requires insights")
    expected_count = config.get("expected_item_count")
    if len(insights) != expected_count:
        raise ValueError(f"expected {expected_count} release insights, found {len(insights)}")

    items: list[dict[str, Any]] = []
    for index, insight in enumerate(insights, 1):
        if not isinstance(insight, dict):
            raise ValueError("release insights must be objects")
        bucket, evidence = _verify_insight(insight, groups)
        source_ids = sorted(bucket.review_ids)
        aggregate_audit = {
            "calculation_source": "data/processed/review_analysis_v11.jsonl",
            "support_count": bucket.support_count,
            "support_rate": insight.get("support_rate"),
            "support_rate_calculation": "support_count / selected_records",
            "selected_records_denominator": len(records),
            "selected_records_denominator_semantics": "selected unique review records",
            "selected_review_ids_sha256": sha256_json(selected_review_ids),
            "configured_min_support": min_support,
            "support_volume_tier": insight.get("support_volume_tier"),
            "support_volume_thresholds": {
                "medium": max(8, min_support * 2),
                "high": max(20, min_support * 4),
            },
            "language_counts": dict(bucket.languages),
            "star_counts": {str(star): bucket.stars[star] for star in range(1, 6)},
            "source_review_ids_sha256": sha256_json(source_ids),
        }
        references = [
            {
                "reference_id": "representative_evidence",
                "content": _canonical_json({"evidence": evidence}),
            },
            {
                "reference_id": "aggregation_audit",
                "content": _canonical_json(aggregate_audit),
            },
            {"reference_id": "methodology", "content": methodology},
            {"reference_id": "data_boundary", "content": data_boundary},
        ]
        if insight.get("category") in {
            "packaging_improvement",
            "fulfillment_improvement",
        }:
            references.append({
                "reference_id": "operational_action_routing",
                "content": operations_methodology,
            })
        items.append({
            "item_id": f"rc1-insight-{index:02d}-{_safe_id(insight['insight_id'])}",
            "project": "crossborder-voice",
            "task_type": "release_insight_review",
            "candidate": insight,
            "references": references,
            "rubric": [
                "Verify that every conclusion and recommendation stays within the supplied evidence.",
                "Reject causal, prevalence, cultural, current-market or product-specific claims that the sample cannot support.",
                "Check support counts, language/rating breakdowns and representative quotes against the supplied audit references.",
                "Keep product, packaging, fulfillment, listing and customer-service implications distinct.",
                "Treat recommendations as hypotheses requiring validation, not established business outcomes.",
                "Flag wording that conflicts with the public-data and 2015–2019 source-period boundaries.",
            ],
            "metadata": {
                "candidate_version": config["candidate_version"],
                "freeze_date": config["freeze_date"],
                "source_artifact": "reports/consumer_insights.json",
                "source_index": index - 1,
                "data_classification": config["data_classification"],
            },
        })
    validate_items(items, "crossborder-voice")
    return items, sources


def _require_private_output(output_dir: Path) -> Path:
    resolved = output_dir.resolve()
    if ".private" not in resolved.parts:
        raise ValueError("release-candidate freeze output must be under .private")
    return resolved


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def freeze(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = _load_json(config_path)
    if config.get("schema_version") != "1.0":
        raise ValueError("unsupported release-candidate config schema")
    if config.get("external_transfer_authorized") is not False:
        raise ValueError("preparation config must not authorize external transfer")
    output = _require_private_output(output_dir)
    items, sources = build_items(config)
    input_path = output / "input.jsonl"
    input_content = "".join(_canonical_json(item) + "\n" for item in items)
    _atomic_write(input_path, input_content)
    manifest = {
        "schema_version": "1.0",
        "project": "crossborder-voice",
        "candidate_version": config["candidate_version"],
        "freeze_date": config["freeze_date"],
        "status": "prepared_without_model_calls",
        "data_classification": config["data_classification"],
        "external_transfer_authorized": False,
        "model_api_calls_made": 0,
        "item_count": len(items),
        "input_file": "input.jsonl",
        "input_sha256": sha256_json(items),
        "input_file_sha256": _file_sha256(input_path),
        "source_files": {
            str(path.relative_to(ROOT)).replace("\\", "/"): _file_sha256(path)
            for path in sources.values()
        },
        "items": [
            {"item_id": item["item_id"], "input_sha256": sha256_json(item)}
            for item in items
        ],
    }
    _atomic_write(
        output / "freeze_manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    return manifest


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze CrossBorder Voice release AI-review inputs")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    manifest = freeze(args.config, args.output_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
