"""Prepare a compact, traceable data bundle for the dashboard."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.insight_aggregator import (  # noqa: E402
    ASPECT_NAMES,
    GAP_NAMES,
    ISSUE_NAMES,
    MOTIVATION_NAMES,
    SCENARIO_NAMES,
    SPEECH_NAMES,
)


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def compact_record(record: dict) -> dict:
    source = record["source"]
    analysis = record["analysis"]
    return {
        "id": record["review_id"],
        "language": source["language"],
        "stars": source["stars"],
        "title": source.get("title", ""),
        "body": source.get("body", ""),
        "sentiment": analysis["sentiment"],
        "intensity": analysis["sentiment_intensity"],
        "confidence": analysis["confidence"],
        "aspects": [
            {
                "code": item["aspect"],
                "polarity": item["polarity"],
                "evidence": item.get("evidence", []),
                "opinion": item.get("opinion", ""),
            }
            for item in analysis.get("aspects", [])
        ],
        "issues": [
            {"code": item["issue"], "evidence": item.get("evidence", "")}
            for item in analysis.get("issue_types", [])
        ],
        "motivations": [
            {"code": item["motivation"], "evidence": item.get("evidence", "")}
            for item in analysis.get("purchase_motivations", [])
        ],
        "scenarios": [
            {"code": item["scenario"], "evidence": item.get("evidence", "")}
            for item in analysis.get("usage_scenarios", [])
        ],
        "speechActs": [
            {"code": item["speech_act"], "evidence": item.get("evidence", "")}
            for item in analysis.get("speech_acts", [])
        ],
        "actions": [
            {
                "audience": item["audience"],
                "action": item["action"],
                "evidence": item.get("evidence", ""),
            }
            for item in analysis.get("recommended_actions", [])
        ],
        "expectationGap": analysis.get(
            "expectation_gap", {"present": False, "type": "none", "evidence": []}
        ),
    }


def main() -> int:
    source_path = PROJECT_ROOT / "data/processed/review_analysis_v11.jsonl"
    insights_path = PROJECT_ROOT / "reports/consumer_insights.json"
    output_path = PROJECT_ROOT / "dashboard/public/data/dashboard-data.json"

    records = read_jsonl(source_path)
    insight_report = json.loads(insights_path.read_text(encoding="utf-8"))
    compact = [compact_record(record) for record in records]

    source_ids = {record["id"] for record in compact}
    missing_ids = sorted(
        {
            review_id
            for insight in insight_report["insights"]
            for review_id in insight["data_evidence"]["source_review_ids"]
            if review_id not in source_ids
        }
    )
    if missing_ids:
        raise ValueError(f"Insight evidence IDs missing from source data: {missing_ids[:5]}")

    labels = {
        "aspects": ASPECT_NAMES,
        "issues": ISSUE_NAMES,
        "motivations": MOTIVATION_NAMES,
        "scenarios": SCENARIO_NAMES,
        "speechActs": SPEECH_NAMES,
        "expectationGaps": GAP_NAMES,
        "sentiments": {
            "positive": "正向",
            "negative": "负向",
            "mixed": "正负混合",
            "neutral": "中性",
            "uncertain": "不确定",
        },
    }
    payload = {
        "meta": {
            "title": "跨境电商评论洞察台",
            "source": "review_analysis_v11.jsonl",
            "generatedFrom": len(compact),
            "languages": dict(Counter(record["language"] for record in compact)),
            "stars": dict(
                sorted(Counter(str(record["stars"]) for record in compact).items())
            ),
            "traceability": insight_report["traceability"],
            "promptVersion": "v9_consistency_guard",
            "schemaVersion": "1.7.0",
        },
        "labels": labels,
        "records": compact,
        "insights": insight_report["insights"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "pass",
                "output": str(output_path),
                "records": len(compact),
                "insights": len(insight_report["insights"]),
                "missing_trace_ids": len(missing_ids),
                "bytes": output_path.stat().st_size,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
