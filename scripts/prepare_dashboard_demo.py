"""Create a public-safe dashboard bundle from the local full bundle."""

from __future__ import annotations

import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = PROJECT_ROOT / "data" / "sample" / "demo_reviews.csv"
FULL_BUNDLE_PATH = (
    PROJECT_ROOT / "dashboard" / "public" / "data" / "dashboard-data.json"
)
DEMO_BUNDLE_PATH = (
    PROJECT_ROOT
    / "dashboard"
    / "public"
    / "data"
    / "dashboard-data.demo.json"
)


def main() -> int:
    with SAMPLE_PATH.open(encoding="utf-8-sig", newline="") as handle:
        sample_ids = {row["review_id"] for row in csv.DictReader(handle)}
    full = json.loads(FULL_BUNDLE_PATH.read_text(encoding="utf-8"))
    demo_records = [
        record for record in full["records"] if record["id"] in sample_ids
    ]
    if len(demo_records) != len(sample_ids):
        found = {record["id"] for record in demo_records}
        raise RuntimeError(
            f"Full dashboard bundle is missing demo IDs: {sorted(sample_ids - found)}"
        )

    demo_insights = []
    for source_insight in full["insights"]:
        insight = json.loads(json.dumps(source_insight, ensure_ascii=False))
        insight["data_evidence"]["source_review_ids"] = [
            review_id
            for review_id in insight["data_evidence"]["source_review_ids"]
            if review_id in sample_ids
        ]
        insight["representative_quotes"] = [
            quote
            for quote in insight["representative_quotes"]
            if quote["review_id"] in sample_ids
        ]
        demo_insights.append(insight)

    visible_insights = sum(
        bool(insight["data_evidence"]["source_review_ids"])
        for insight in demo_insights
    )
    demo = {
        "meta": {
            **full["meta"],
            "title": "跨境电商评论洞察台｜Public Demo",
            "source": "public demo sample",
            "generatedFrom": len(demo_records),
            "mode": "demo",
            "fullDatasetRecords": len(full["records"]),
            "traceability": {
                "status": "demo_subset",
                "insights_checked": len(demo_insights),
                "visible_insights": visible_insights,
                "failures": 0,
            },
        },
        "labels": full["labels"],
        "records": demo_records,
        "insights": demo_insights,
    }
    DEMO_BUNDLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEMO_BUNDLE_PATH.write_text(
        json.dumps(demo, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "pass",
                "output": str(DEMO_BUNDLE_PATH.relative_to(PROJECT_ROOT)),
                "records": len(demo_records),
                "formal_insights": len(demo_insights),
                "visible_insights": visible_insights,
                "bytes": DEMO_BUNDLE_PATH.stat().st_size,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
