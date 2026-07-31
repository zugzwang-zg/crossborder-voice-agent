"""Evaluate Baseline and Improved on the frozen 100-review gold set."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model_evaluator import (
    failure_cases,
    manual_business_rows,
    manual_evidence_rows,
    read_csv,
    read_jsonl,
    version_metrics,
    write_comparison_svg,
    write_csv,
)


GOLD_PATH = PROJECT_ROOT / "data" / "annotation" / "gold_sample.csv"
BASELINE_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "baseline_predictions.jsonl"
)
IMPROVED_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "improved_predictions.jsonl"
)
EVIDENCE_REVIEW_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "evidence_manual_review.csv"
)
BUSINESS_REVIEW_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "business_advice_manual_review.csv"
)
FAILURES_PATH = (
    PROJECT_ROOT / "reports" / "failure_cases.csv"
)
REPORT_JSON_PATH = PROJECT_ROOT / "reports" / "evaluation_report.json"
REPORT_MD_PATH = PROJECT_ROOT / "reports" / "evaluation_report.md"
CHART_PATH = PROJECT_ROOT / "reports" / "model_version_comparison.svg"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_manual_evidence(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "pending", "completed": 0, "required": 50}
    rows = read_csv(path)
    completed = [
        row
        for row in rows
        if row.get("semantic_support_yes_no", "").strip().casefold()
        in {"yes", "no"}
    ]
    result: dict[str, Any] = {
        "status": "complete" if len(completed) == len(rows) else "pending",
        "completed": len(completed),
        "required": len(rows),
        "by_version": {},
    }
    by_version: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in completed:
        by_version[row["version"]].append(row)
    for version, version_rows in by_version.items():
        valid = sum(
            row["semantic_support_yes_no"].strip().casefold() == "yes"
            for row in version_rows
        )
        result["by_version"][version] = {
            "valid": valid,
            "reviewed": len(version_rows),
            "semantic_evidence_validity": round(
                valid / len(version_rows), 4
            ),
        }
    return result


def read_manual_business(path: Path) -> dict[str, Any]:
    score_fields = [
        "specificity_score_1_5",
        "data_grounding_score_1_5",
        "actionability_score_1_5",
        "over_inference_control_score_1_5",
    ]
    if not path.exists():
        return {"status": "pending", "completed": 0, "required": 40}
    rows = read_csv(path)
    completed: list[dict[str, Any]] = []
    for row in rows:
        try:
            scores = {field: int(row[field]) for field in score_fields}
        except (KeyError, TypeError, ValueError):
            continue
        if not all(1 <= score <= 5 for score in scores.values()):
            continue
        completed.append({**row, "_scores": scores})
    result: dict[str, Any] = {
        "status": "complete" if len(completed) == len(rows) else "pending",
        "completed": len(completed),
        "required": len(rows),
        "by_version": {},
    }
    by_version: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in completed:
        by_version[row["version"]].append(row)
    for version, version_rows in by_version.items():
        dimension_means = {
            field: round(
                sum(row["_scores"][field] for row in version_rows)
                / len(version_rows),
                3,
            )
            for field in score_fields
        }
        result["by_version"][version] = {
            "reviewed_actions": len(version_rows),
            "dimension_means": dimension_means,
            "overall_mean": round(
                sum(dimension_means.values()) / len(dimension_means), 3
            ),
        }
    return result


def target_status(value: float, target: float) -> str:
    return "pass" if value >= target else "below_target"


def markdown_report(report: dict[str, Any]) -> str:
    baseline = report["versions"]["baseline"]
    improved = report["versions"]["improved"]
    manual_evidence = report["manual_review"]["evidence"]
    manual_business = report["manual_review"]["business_advice"]
    lines = [
        "# 模型评测报告",
        "",
        f"- 评测集：冻结人工金标准 {report['dataset']['records']} 条",
        "- 语言分布：英语 50 条，西班牙语 50 条",
        "- 对比版本：Baseline `v1_basic`；Improved `v9_consistency_guard`",
        "- 模型：两版均为 `gpt-5.6-luna`",
        "- 评测原则：相同模型、相同100条评论、相同结构化输出Schema；只改变提示词指导。",
        f"- 报告状态：`{report['status']}`",
        "",
        "## 总体自动评测",
        "",
        "| 指标 | Baseline | Improved | 建议目标 | Improved结果 |",
        "|---|---:|---:|---:|---|",
        (
            f"| JSON解析成功率 | {baseline['json_parse_success_rate']:.1%} | "
            f"{improved['json_parse_success_rate']:.1%} | ≥95% | "
            f"{report['targets']['json_parse_success_rate']['status']} |"
        ),
        (
            f"| 情感 Accuracy | {baseline['sentiment']['accuracy']:.1%} | "
            f"{improved['sentiment']['accuracy']:.1%} | ≥80% | "
            f"{report['targets']['sentiment_accuracy']['status']} |"
        ),
        (
            f"| 情感 Macro-F1 | {baseline['sentiment']['macro_f1']:.1%} | "
            f"{improved['sentiment']['macro_f1']:.1%} | — | — |"
        ),
        (
            f"| 属性 Precision | {baseline['aspects']['precision']:.1%} | "
            f"{improved['aspects']['precision']:.1%} | — | — |"
        ),
        (
            f"| 属性 Recall | {baseline['aspects']['recall']:.1%} | "
            f"{improved['aspects']['recall']:.1%} | — | — |"
        ),
        (
            f"| 属性 F1 | {baseline['aspects']['f1']:.1%} | "
            f"{improved['aspects']['f1']:.1%} | ≥70% | "
            f"{report['targets']['aspect_f1']['status']} |"
        ),
        (
            f"| 痛点完全匹配率 | "
            f"{baseline['issues']['record_exact_match_accuracy']:.1%} | "
            f"{improved['issues']['record_exact_match_accuracy']:.1%} | — | — |"
        ),
        (
            f"| 证据原文子串有效率 | "
            f"{baseline['evidence_substring']['validity']:.1%} | "
            f"{improved['evidence_substring']['validity']:.1%} | — | — |"
        ),
        "",
        "说明：属性指标采用多标签微平均；痛点完全匹配率以人工金标问题集合为准；"
        "原文子串有效率只证明引用来自评论，语义是否真正支持标签另由人工抽查。",
        "",
        "## 多语言表现",
        "",
        "| 版本 | 语言 | 情感Accuracy | 情感Macro-F1 | 属性Precision | 属性Recall | 属性F1 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for version_name, metrics in (
        ("Baseline", baseline),
        ("Improved", improved),
    ):
        for language in ("en", "es"):
            item = metrics["by_language"][language]
            lines.append(
                f"| {version_name} | {language} | "
                f"{item['sentiment']['accuracy']:.1%} | "
                f"{item['sentiment']['macro_f1']:.1%} | "
                f"{item['aspects']['precision']:.1%} | "
                f"{item['aspects']['recall']:.1%} | "
                f"{item['aspects']['f1']:.1%} |"
            )
    lines.extend(
        [
            "",
            "## 人工复核状态",
            "",
            (
                f"- 证据语义有效性："
                f"{report['manual_review']['evidence']['completed']} / "
                f"{report['manual_review']['evidence']['required']}，"
                f"状态 `{report['manual_review']['evidence']['status']}`。"
            ),
            (
                f"- 商业建议四维评分："
                f"{report['manual_review']['business_advice']['completed']} / "
                f"{report['manual_review']['business_advice']['required']}，"
                f"状态 `{report['manual_review']['business_advice']['status']}`。"
            ),
            "- 商业建议评分维度：具体性、数据依据、可执行性、过度推断控制，均为1—5分。",
            "",
        ]
    )
    if manual_evidence["status"] == "complete":
        baseline_manual_evidence = manual_evidence["by_version"]["baseline"]
        improved_manual_evidence = manual_evidence["by_version"]["improved"]
        lines.extend(
            [
                "### 证据语义有效性人工抽查",
                "",
                "| 版本 | 有效/抽查 | 语义有效率 | 目标 | 结果 |",
                "|---|---:|---:|---:|---|",
                (
                    f"| Baseline | {baseline_manual_evidence['valid']} / "
                    f"{baseline_manual_evidence['reviewed']} | "
                    f"{baseline_manual_evidence['semantic_evidence_validity']:.1%} | "
                    "— | — |"
                ),
                (
                    f"| Improved | {improved_manual_evidence['valid']} / "
                    f"{improved_manual_evidence['reviewed']} | "
                    f"{improved_manual_evidence['semantic_evidence_validity']:.1%} | "
                    f"≥90% | {report['targets']['evidence_validity']['status']} |"
                ),
                "",
            ]
        )
    if manual_business["status"] == "complete":
        baseline_business = manual_business["by_version"]["baseline"]
        improved_business = manual_business["by_version"]["improved"]
        dimension_labels = [
            ("具体性", "specificity_score_1_5"),
            ("数据依据", "data_grounding_score_1_5"),
            ("可执行性", "actionability_score_1_5"),
            ("过度推断控制", "over_inference_control_score_1_5"),
        ]
        lines.extend(
            [
                "### 商业建议人工评分",
                "",
                "| 维度 | Baseline | Improved | Improved差值 |",
                "|---|---:|---:|---:|",
            ]
        )
        for label, field in dimension_labels:
            baseline_score = baseline_business["dimension_means"][field]
            improved_score = improved_business["dimension_means"][field]
            lines.append(
                f"| {label} | {baseline_score:.2f} | "
                f"{improved_score:.2f} | "
                f"{improved_score - baseline_score:+.2f} |"
            )
        lines.extend(
            [
                (
                    f"| **总体均分** | **{baseline_business['overall_mean']:.3f}** | "
                    f"**{improved_business['overall_mean']:.3f}** | "
                    f"**{improved_business['overall_mean'] - baseline_business['overall_mean']:+.3f}** |"
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## 版本对比结论",
            "",
            (
                f"- Improved 情感准确率比 Baseline 提高 "
                f"{(improved['sentiment']['accuracy'] - baseline['sentiment']['accuracy']) * 100:.1f} "
                "个百分点。"
            ),
            (
                f"- Improved 属性 F1 提高 "
                f"{(improved['aspects']['f1'] - baseline['aspects']['f1']) * 100:.2f} "
                "个百分点，主要来自误报减少和Precision提升。"
            ),
            (
                f"- Improved 痛点 F1 提高 "
                f"{(improved['issues']['f1'] - baseline['issues']['f1']) * 100:.2f} "
                "个百分点，痛点集合完全匹配率提高 "
                f"{(improved['issues']['record_exact_match_accuracy'] - baseline['issues']['record_exact_match_accuracy']) * 100:.1f} "
                "个百分点。"
            ),
        ]
    )
    if manual_evidence["status"] == "complete":
        lines.append(
            "- 人工证据语义有效率由 "
            f"{manual_evidence['by_version']['baseline']['semantic_evidence_validity']:.1%} "
            "提高到 "
            f"{manual_evidence['by_version']['improved']['semantic_evidence_validity']:.1%}。"
        )
    if manual_business["status"] == "complete":
        lines.append(
            "- 商业建议总体人工均分基本持平："
            f"{manual_business['by_version']['baseline']['overall_mean']:.3f} "
            "对 "
            f"{manual_business['by_version']['improved']['overall_mean']:.3f}；"
            "Improved在过度推断控制上更好，但可执行性略低。"
        )
    lines.extend(
        [
            "- 以上为100条冻结评测集上的描述性结果；人工证据与建议评分为平衡抽样，不作统计显著性外推。",
            "",
            "## 失败案例",
            "",
        ]
    )
    for index, item in enumerate(report["failure_cases"][:10], start=1):
        lines.extend(
            [
                f"### {index}. {item['version']} · {item['review_id']} · "
                f"{item['language']} · {item['stars']}星",
                "",
                f"- 失败类型：`{item['failure_types']}`",
                f"- 人工情感：`{item['gold_sentiment']}`；预测："
                f"`{item['predicted_sentiment']}`",
                f"- 属性误报：`{item['aspect_false_positives'] or '无'}`",
                f"- 属性漏报：`{item['aspect_false_negatives'] or '无'}`",
                f"- 痛点误报：`{item['issue_false_positives'] or '无'}`",
                f"- 痛点漏报：`{item['issue_false_negatives'] or '无'}`",
                f"- 评论原文：{item['review_title']} — {item['review_body']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 失败原因归纳",
            "",
            "1. 多属性长评论容易出现细粒度属性漏报，尤其同一句同时包含效果、适配与使用体验时。",
            "2. `mixed` 与单一正负情感的边界依赖是否存在明确、独立的相反评价。",
            "3. 属性与具体痛点标签粒度不同：模型可能识别到属性，但未输出对应问题类型，或反之。",
            "4. 短评论上下文不足，星级能够辅助判断，但不能替代文本证据。",
            "5. 英西表达中的省略、缓和、比较和口语拼写会影响细粒度标签召回。",
            "",
            "## 下一轮改进建议",
            "",
            "- 失败案例只能用于下一轮开发，不在本次金标准上修改Prompt后重测。",
            "- 另建新的开发集补充多属性长评论、短文本及英西口语边界案例。",
            "- 将高频混淆属性整理为成对反例，并增加细粒度标签互斥或共现规则。",
            "- 下一版本完成后必须换用新的冻结评测集，避免对本次100条过拟合。",
            "",
            "## 产物",
            "",
            "- `reports/model_version_comparison.svg`",
            "- `reports/failure_cases.csv`",
            "- `data/evaluation/evidence_manual_review.csv`",
            "- `data/evaluation/business_advice_manual_review.csv`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    missing = [
        str(path)
        for path in (GOLD_PATH, BASELINE_PATH, IMPROVED_PATH)
        if not path.exists()
    ]
    if missing:
        print(
            json.dumps(
                {
                    "status": "blocked_missing_predictions",
                    "missing": missing,
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    gold = read_csv(GOLD_PATH)
    baseline_records, baseline_invalid = read_jsonl(BASELINE_PATH)
    improved_records, improved_invalid = read_jsonl(IMPROVED_PATH)
    versions = {
        "baseline": baseline_records,
        "improved": improved_records,
    }
    metrics = {
        "baseline": version_metrics(
            gold,
            baseline_records,
            invalid_json_lines=baseline_invalid,
        ),
        "improved": version_metrics(
            gold,
            improved_records,
            invalid_json_lines=improved_invalid,
        ),
    }
    failures = failure_cases(gold, versions, limit=10)
    write_csv(FAILURES_PATH, failures)

    if not EVIDENCE_REVIEW_PATH.exists():
        write_csv(
            EVIDENCE_REVIEW_PATH,
            manual_evidence_rows(gold, versions, per_version=25),
        )
    if not BUSINESS_REVIEW_PATH.exists():
        write_csv(
            BUSINESS_REVIEW_PATH,
            manual_business_rows(gold, versions, per_version=20),
        )

    manual_evidence = read_manual_evidence(EVIDENCE_REVIEW_PATH)
    manual_business = read_manual_business(BUSINESS_REVIEW_PATH)
    status = (
        "complete"
        if manual_evidence["status"] == "complete"
        and manual_business["status"] == "complete"
        else "awaiting_manual_review"
    )
    report = {
        "status": status,
        "dataset": {
            "records": len(gold),
            "languages": {"en": 50, "es": 50},
            "role": "frozen_held_out_final_evaluation",
        },
        "comparison": {
            "baseline": "v1_basic",
            "improved": "v9_consistency_guard",
            "model": "gpt-5.6-luna",
            "schema_version": "1.7.0",
        },
        "versions": metrics,
        "targets": {
            "json_parse_success_rate": {
                "target": 0.95,
                "actual": metrics["improved"]["json_parse_success_rate"],
                "status": target_status(
                    metrics["improved"]["json_parse_success_rate"], 0.95
                ),
            },
            "sentiment_accuracy": {
                "target": 0.80,
                "actual": metrics["improved"]["sentiment"]["accuracy"],
                "status": target_status(
                    metrics["improved"]["sentiment"]["accuracy"], 0.80
                ),
            },
            "aspect_f1": {
                "target": 0.70,
                "actual": metrics["improved"]["aspects"]["f1"],
                "status": target_status(
                    metrics["improved"]["aspects"]["f1"], 0.70
                ),
            },
            "evidence_validity": {
                "target": 0.90,
                "actual": (
                    manual_evidence["by_version"]["improved"][
                        "semantic_evidence_validity"
                    ]
                    if manual_evidence["status"] == "complete"
                    else None
                ),
                "status": (
                    target_status(
                        manual_evidence["by_version"]["improved"][
                            "semantic_evidence_validity"
                        ],
                        0.90,
                    )
                    if manual_evidence["status"] == "complete"
                    else "pending"
                ),
            },
        },
        "manual_review": {
            "evidence": manual_evidence,
            "business_advice": manual_business,
        },
        "failure_cases": failures,
    }
    write_json(REPORT_JSON_PATH, report)
    REPORT_MD_PATH.write_text(markdown_report(report), encoding="utf-8")
    write_comparison_svg(CHART_PATH, metrics, report["manual_review"])
    print(
        json.dumps(
            {
                "status": status,
                "baseline_records": metrics["baseline"]["records_parsed"],
                "improved_records": metrics["improved"]["records_parsed"],
                "baseline_sentiment_accuracy": metrics["baseline"][
                    "sentiment"
                ]["accuracy"],
                "improved_sentiment_accuracy": metrics["improved"][
                    "sentiment"
                ]["accuracy"],
                "baseline_aspect_f1": metrics["baseline"]["aspects"]["f1"],
                "improved_aspect_f1": metrics["improved"]["aspects"]["f1"],
                "manual_evidence": manual_evidence["status"],
                "manual_business": manual_business["status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
