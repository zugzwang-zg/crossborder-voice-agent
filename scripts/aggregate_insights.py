"""Aggregate validated reviews and generate traceable insight cards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.insight_aggregator import (
    aggregate_records,
    load_jsonl,
    save_report_bundle,
    validate_report_traceability,
)
from src.llm_analyzer import review_source_text
from src.schema import AnalysisValidationError, validate_analysis


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/review_analysis_v11.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/aggregated"),
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=Path("reports/consumer_insights.json"),
    )
    parser.add_argument(
        "--report-markdown",
        type=Path,
        default=Path("reports/consumer_insights.md"),
    )
    parser.add_argument("--min-support", type=int, default=5)
    parser.add_argument("--max-insights", type=int, default=15)
    parser.add_argument(
        "--sampling-strategy",
        choices=["language_star_stratified", "unweighted_unknown"],
        default="language_star_stratified",
    )
    parser.add_argument("--small-sample-threshold", type=int, default=30)
    parser.add_argument(
        "--scope-field",
        choices=["product_id", "product_subcategory"],
    )
    parser.add_argument("--scope-value")
    parser.add_argument(
        "--title",
        default="跨境电商英西双语消费者洞察",
    )
    args = parser.parse_args()
    if bool(args.scope_field) != bool(args.scope_value):
        parser.error("--scope-field and --scope-value must be provided together")

    records = load_jsonl(args.input)
    failures: list[dict[str, str]] = []
    seen: set[str] = set()
    for record in records:
        review_id = str(record.get("review_id"))
        if review_id in seen:
            failures.append(
                {"review_id": review_id, "error": "duplicate review_id"}
            )
            continue
        seen.add(review_id)
        source = record.get("source", {})
        try:
            validate_analysis(
                record.get("analysis"),
                source_text=review_source_text(
                    {
                        "review_title": source.get("title", ""),
                        "review_body": source.get("body", ""),
                    }
                ),
                expected_review_id=review_id,
                expected_language=source.get("language"),
            )
        except AnalysisValidationError as error:
            failures.append(
                {"review_id": review_id, "error": str(error)}
            )
    if failures:
        print(
            json.dumps(
                {"status": "fail", "validation_failures": failures},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    report = aggregate_records(
        records,
        min_support=args.min_support,
        max_insights=args.max_insights,
        sampling_strategy=args.sampling_strategy,
        small_sample_threshold=args.small_sample_threshold,
        scope_field=args.scope_field,
        scope_value=args.scope_value,
    )
    traceability_failures = validate_report_traceability(report, records)
    if traceability_failures:
        print(
            json.dumps(
                {
                    "status": "fail",
                    "traceability_failures": traceability_failures,
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    report["traceability"] = {
        "status": "pass",
        "insights_checked": len(report["insights"]),
        "failures": 0,
    }
    report["source"] = {
        "input_path": str(args.input),
        "validated_records": len(records),
        "duplicate_ids": 0,
    }
    save_report_bundle(
        report,
        output_dir=args.output_dir,
        report_json=args.report_json,
        report_markdown=args.report_markdown,
        title=args.title,
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
