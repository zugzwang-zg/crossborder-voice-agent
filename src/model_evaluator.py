"""Frozen-set evaluation utilities for Baseline and Improved predictions."""

from __future__ import annotations

import csv
import hashlib
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SENTIMENT_LABELS = ["negative", "mixed", "neutral", "positive", "uncertain"]


def split_labels(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split("|") if item.strip()}


def safe_div(numerator: int | float, denominator: int | float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    invalid = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                invalid += 1
    return records, invalid


def sentiment_metrics(
    gold_rows: list[dict[str, str]],
    predictions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    total = len(gold_rows)
    correct = 0
    per_class: dict[str, dict[str, float | int]] = {}
    confusion: dict[str, dict[str, int]] = {
        label: {predicted: 0 for predicted in [*SENTIMENT_LABELS, "missing"]}
        for label in SENTIMENT_LABELS
    }
    for label in SENTIMENT_LABELS:
        gold_support = sum(row["gold_sentiment"] == label for row in gold_rows)
        if gold_support == 0:
            continue
        tp = fp = fn = 0
        for row in gold_rows:
            predicted = (
                predictions.get(row["review_id"], {})
                .get("analysis", {})
                .get("sentiment")
            )
            gold = row["gold_sentiment"]
            if predicted == label and gold == label:
                tp += 1
            elif predicted == label and gold != label:
                fp += 1
            elif predicted != label and gold == label:
                fn += 1
        precision = safe_div(tp, tp + fp)
        recall = safe_div(tp, tp + fn)
        f1 = safe_div(2 * precision * recall, precision + recall)
        per_class[label] = {
            "support": gold_support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    for row in gold_rows:
        predicted = (
            predictions.get(row["review_id"], {})
            .get("analysis", {})
            .get("sentiment")
        )
        correct += predicted == row["gold_sentiment"]
        predicted_label = str(predicted) if predicted in SENTIMENT_LABELS else "missing"
        confusion[row["gold_sentiment"]][predicted_label] += 1
    macro_f1 = (
        round(
            sum(float(item["f1"]) for item in per_class.values())
            / len(per_class),
            4,
        )
        if per_class
        else 0.0
    )
    return {
        "accuracy": safe_div(correct, total),
        "macro_f1": macro_f1,
        "correct": correct,
        "total": total,
        "per_class": per_class,
        "confusion_matrix": confusion,
        "confusion_labels": [*SENTIMENT_LABELS, "missing"],
    }


def multilabel_metrics(
    gold_rows: list[dict[str, str]],
    predictions: dict[str, dict[str, Any]],
    *,
    gold_field: str,
    prediction_field: str,
    label_key: str,
) -> dict[str, Any]:
    tp = fp = fn = exact = 0
    gold_instances = predicted_instances = 0
    label_counts: dict[str, Counter[str]] = {}
    for row in gold_rows:
        gold = split_labels(row.get(gold_field))
        predicted_items = (
            predictions.get(row["review_id"], {})
            .get("analysis", {})
            .get(prediction_field, [])
        )
        predicted = {
            str(item[label_key])
            for item in predicted_items
            if isinstance(item, dict) and item.get(label_key)
        }
        for label in gold | predicted:
            counts = label_counts.setdefault(label, Counter())
            if label in gold and label in predicted:
                counts["tp"] += 1
            elif label in predicted:
                counts["fp"] += 1
            else:
                counts["fn"] += 1
        tp += len(gold & predicted)
        fp += len(predicted - gold)
        fn += len(gold - predicted)
        exact += gold == predicted
        gold_instances += len(gold)
        predicted_instances += len(predicted)
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    per_label: dict[str, dict[str, float | int]] = {}
    for label, counts in sorted(label_counts.items()):
        label_precision = safe_div(counts["tp"], counts["tp"] + counts["fp"])
        label_recall = safe_div(counts["tp"], counts["tp"] + counts["fn"])
        per_label[label] = {
            "support": counts["tp"] + counts["fn"],
            "precision": label_precision,
            "recall": label_recall,
            "f1": safe_div(
                2 * label_precision * label_recall,
                label_precision + label_recall,
            ),
        }
    macro_f1 = safe_div(
        sum(float(item["f1"]) for item in per_label.values()),
        len(per_label),
    )
    return {
        "precision": precision,
        "recall": recall,
        "f1": safe_div(2 * precision * recall, precision + recall),
        "record_exact_match_accuracy": safe_div(exact, len(gold_rows)),
        "exact_match_records": exact,
        "records": len(gold_rows),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "gold_label_instances": gold_instances,
        "predicted_label_instances": predicted_instances,
        "macro_f1": macro_f1,
        "per_label": per_label,
    }


def confidence_calibration_metrics(
    gold_rows: list[dict[str, str]],
    predictions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Audit whether model self-reported confidence tracks sentiment accuracy."""
    boundaries = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 1.000001)]
    observations: list[tuple[float, bool]] = []
    for row in gold_rows:
        analysis = predictions.get(row["review_id"], {}).get("analysis", {})
        confidence = analysis.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            continue
        bounded = max(0.0, min(1.0, float(confidence)))
        observations.append((bounded, analysis.get("sentiment") == row["gold_sentiment"]))
    bins: list[dict[str, Any]] = []
    weighted_error = 0.0
    for lower, upper in boundaries:
        values = [item for item in observations if lower <= item[0] < upper]
        if not values:
            continue
        mean_confidence = sum(item[0] for item in values) / len(values)
        accuracy = sum(item[1] for item in values) / len(values)
        gap = abs(mean_confidence - accuracy)
        weighted_error += gap * len(values)
        bins.append({
            "lower": lower,
            "upper": min(upper, 1.0),
            "records": len(values),
            "mean_confidence": round(mean_confidence, 4),
            "accuracy": round(accuracy, 4),
            "absolute_gap": round(gap, 4),
        })
    count = len(observations)
    ece = round(weighted_error / count, 4) if count else None
    return {
        "records_with_confidence": count,
        "coverage": safe_div(count, len(gold_rows)),
        "mean_confidence": (
            round(sum(item[0] for item in observations) / count, 4) if count else None
        ),
        "observed_accuracy": (
            round(sum(item[1] for item in observations) / count, 4) if count else None
        ),
        "expected_calibration_error": ece,
        "status": (
            "not_available" if ece is None else "uncalibrated" if ece > 0.05 else "provisionally_aligned"
        ),
        "display_policy": "treat_as_model_self_report_not_probability",
        "bins": bins,
    }


def iter_evidence_claims(
    record: dict[str, Any],
) -> Iterable[tuple[str, str, str]]:
    analysis = record.get("analysis", {})
    sentiment = str(analysis.get("sentiment", ""))
    for evidence in analysis.get("sentiment_evidence", []):
        yield "sentiment", sentiment, str(evidence)
    for item in analysis.get("aspects", []):
        label = f"{item.get('aspect')}:{item.get('polarity')}"
        for evidence in item.get("evidence", []):
            yield "aspect", label, str(evidence)
    mappings = [
        ("issue", "issue_types", "issue"),
        ("purchase_motivation", "purchase_motivations", "motivation"),
        ("usage_scenario", "usage_scenarios", "scenario"),
        ("speech_act", "speech_acts", "speech_act"),
        ("recommended_action", "recommended_actions", "action"),
    ]
    for claim_type, field, label_key in mappings:
        for item in analysis.get(field, []):
            evidence = item.get("evidence")
            if evidence:
                yield claim_type, str(item.get(label_key, "")), str(evidence)
    gap = analysis.get("expectation_gap", {})
    for evidence in gap.get("evidence", []):
        yield "expectation_gap", str(gap.get("type", "")), str(evidence)


def evidence_substring_metrics(
    gold_rows: list[dict[str, str]],
    predictions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    row_by_id = {row["review_id"]: row for row in gold_rows}
    total = valid = 0
    for review_id, record in predictions.items():
        if review_id not in row_by_id:
            continue
        row = row_by_id[review_id]
        source = f"{row['review_title']}\n{row['review_body']}"
        for _, _, evidence in iter_evidence_claims(record):
            total += 1
            valid += bool(evidence and evidence in source)
    return {
        "validity": safe_div(valid, total),
        "valid_claims": valid,
        "total_claims": total,
    }


def version_metrics(
    gold_rows: list[dict[str, str]],
    prediction_records: list[dict[str, Any]],
    *,
    invalid_json_lines: int = 0,
) -> dict[str, Any]:
    predictions = {
        str(record["review_id"]): record
        for record in prediction_records
        if record.get("review_id")
    }
    languages: dict[str, Any] = {}
    for language in ("en", "es"):
        subset = [row for row in gold_rows if row["language"] == language]
        languages[language] = {
            "sentiment": sentiment_metrics(subset, predictions),
            "aspects": multilabel_metrics(
                subset,
                predictions,
                gold_field="gold_aspects",
                prediction_field="aspects",
                label_key="aspect",
            ),
            "issues": multilabel_metrics(
                subset,
                predictions,
                gold_field="gold_issue",
                prediction_field="issue_types",
                label_key="issue",
            ),
            "confidence_calibration": confidence_calibration_metrics(subset, predictions),
        }
    unique_predictions = len(predictions)
    return {
        "records_expected": len(gold_rows),
        "records_parsed": unique_predictions,
        "invalid_json_lines": invalid_json_lines,
        "json_parse_success_rate": safe_div(
            unique_predictions, len(gold_rows)
        ),
        "sentiment": sentiment_metrics(gold_rows, predictions),
        "aspects": multilabel_metrics(
            gold_rows,
            predictions,
            gold_field="gold_aspects",
            prediction_field="aspects",
            label_key="aspect",
        ),
        "issues": multilabel_metrics(
            gold_rows,
            predictions,
            gold_field="gold_issue",
            prediction_field="issue_types",
            label_key="issue",
        ),
        "evidence_substring": evidence_substring_metrics(
            gold_rows, predictions
        ),
        "confidence_calibration": confidence_calibration_metrics(gold_rows, predictions),
        "by_language": languages,
    }


def failure_cases(
    gold_rows: list[dict[str, str]],
    versions: dict[str, list[dict[str, Any]]],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    predictions = {
        version: {
            str(record["review_id"]): record for record in records
        }
        for version, records in versions.items()
    }
    failures: list[dict[str, Any]] = []
    for row in gold_rows:
        gold_aspects = split_labels(row.get("gold_aspects"))
        gold_issues = split_labels(row.get("gold_issue"))
        for version, by_id in predictions.items():
            analysis = by_id.get(row["review_id"], {}).get("analysis", {})
            predicted_sentiment = analysis.get("sentiment")
            predicted_aspects = {
                str(item["aspect"])
                for item in analysis.get("aspects", [])
                if item.get("aspect")
            }
            predicted_issues = {
                str(item["issue"])
                for item in analysis.get("issue_types", [])
                if item.get("issue")
            }
            sentiment_error = int(
                predicted_sentiment != row["gold_sentiment"]
            )
            aspect_fp = sorted(predicted_aspects - gold_aspects)
            aspect_fn = sorted(gold_aspects - predicted_aspects)
            issue_fp = sorted(predicted_issues - gold_issues)
            issue_fn = sorted(gold_issues - predicted_issues)
            score = (
                sentiment_error * 3
                + len(aspect_fp)
                + len(aspect_fn)
                + len(issue_fp)
                + len(issue_fn)
            )
            if score == 0:
                continue
            reasons = []
            if sentiment_error:
                reasons.append("sentiment_mismatch")
            if aspect_fp:
                reasons.append("aspect_false_positive")
            if aspect_fn:
                reasons.append("aspect_false_negative")
            if issue_fp:
                reasons.append("issue_false_positive")
            if issue_fn:
                reasons.append("issue_false_negative")
            failures.append(
                {
                    "error_score": score,
                    "version": version,
                    "review_id": row["review_id"],
                    "language": row["language"],
                    "stars": row["stars"],
                    "review_title": row["review_title"],
                    "review_body": row["review_body"],
                    "gold_sentiment": row["gold_sentiment"],
                    "predicted_sentiment": predicted_sentiment or "",
                    "gold_aspects": "|".join(sorted(gold_aspects)),
                    "predicted_aspects": "|".join(
                        sorted(predicted_aspects)
                    ),
                    "aspect_false_positives": "|".join(aspect_fp),
                    "aspect_false_negatives": "|".join(aspect_fn),
                    "gold_issues": "|".join(sorted(gold_issues)),
                    "predicted_issues": "|".join(sorted(predicted_issues)),
                    "issue_false_positives": "|".join(issue_fp),
                    "issue_false_negatives": "|".join(issue_fn),
                    "failure_types": "|".join(reasons),
                }
            )
    failures.sort(
        key=lambda item: (
            -int(item["error_score"]),
            str(item["review_id"]),
            str(item["version"]),
        )
    )
    selected: list[dict[str, Any]] = []
    language_counts: Counter[str] = Counter()
    for item in failures:
        if language_counts[item["language"]] >= max(limit // 2, 1):
            continue
        selected.append(item)
        language_counts[item["language"]] += 1
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        selected_ids = {
            (item["version"], item["review_id"]) for item in selected
        }
        selected.extend(
            item
            for item in failures
            if (item["version"], item["review_id"]) not in selected_ids
        )
    return selected[:limit]


def _stable_rank(*values: str) -> str:
    return hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()


def manual_evidence_rows(
    gold_rows: list[dict[str, str]],
    versions: dict[str, list[dict[str, Any]]],
    *,
    per_version: int = 25,
) -> list[dict[str, Any]]:
    source = {row["review_id"]: row for row in gold_rows}
    rows: list[dict[str, Any]] = []
    for version, records in versions.items():
        candidates: list[dict[str, Any]] = []
        for record in records:
            review_id = str(record["review_id"])
            if review_id not in source:
                continue
            gold = source[review_id]
            review_text = f"{gold['review_title']}\n{gold['review_body']}"
            for claim_type, label, evidence in iter_evidence_claims(record):
                candidates.append(
                    {
                        "review_id": review_id,
                        "language": gold["language"],
                        "stars": gold["stars"],
                        "version": version,
                        "claim_type": claim_type,
                        "predicted_label": label,
                        "evidence": evidence,
                        "review_title": gold["review_title"],
                        "review_body": gold["review_body"],
                        "exact_substring_valid": (
                            "yes" if evidence in review_text else "no"
                        ),
                        "semantic_support_yes_no": "",
                        "reviewer_notes": "",
                        "_rank": _stable_rank(
                            "evidence", version, review_id, claim_type, evidence
                        ),
                    }
                )
        chosen: list[dict[str, Any]] = []
        for language, quota in (("en", 13), ("es", 12)):
            pool = sorted(
                (
                    item
                    for item in candidates
                    if item["language"] == language
                ),
                key=lambda item: item["_rank"],
            )
            chosen.extend(pool[: min(quota, per_version - len(chosen))])
        if len(chosen) < per_version:
            used = {
                (item["review_id"], item["claim_type"], item["evidence"])
                for item in chosen
            }
            remaining = sorted(
                (
                    item
                    for item in candidates
                    if (
                        item["review_id"],
                        item["claim_type"],
                        item["evidence"],
                    )
                    not in used
                ),
                key=lambda item: item["_rank"],
            )
            chosen.extend(remaining[: per_version - len(chosen)])
        for item in chosen:
            item.pop("_rank", None)
        rows.extend(chosen)
    return rows


def manual_business_rows(
    gold_rows: list[dict[str, str]],
    versions: dict[str, list[dict[str, Any]]],
    *,
    per_version: int = 20,
) -> list[dict[str, Any]]:
    source = {row["review_id"]: row for row in gold_rows}
    rows: list[dict[str, Any]] = []
    for version, records in versions.items():
        candidates: list[dict[str, Any]] = []
        for record in records:
            review_id = str(record["review_id"])
            if review_id not in source:
                continue
            gold = source[review_id]
            for index, action in enumerate(
                record.get("analysis", {}).get("recommended_actions", [])
            ):
                candidates.append(
                    {
                        "review_id": review_id,
                        "language": gold["language"],
                        "stars": gold["stars"],
                        "version": version,
                        "action_index": index + 1,
                        "audience": action.get("audience", ""),
                        "action": action.get("action", ""),
                        "evidence": action.get("evidence", ""),
                        "review_title": gold["review_title"],
                        "review_body": gold["review_body"],
                        "specificity_score_1_5": "",
                        "data_grounding_score_1_5": "",
                        "actionability_score_1_5": "",
                        "over_inference_control_score_1_5": "",
                        "reviewer_notes": "",
                        "_rank": _stable_rank(
                            "business",
                            version,
                            review_id,
                            str(index),
                            str(action.get("action", "")),
                        ),
                    }
                )
        chosen: list[dict[str, Any]] = []
        for language, quota in (("en", 10), ("es", 10)):
            pool = sorted(
                (
                    item
                    for item in candidates
                    if item["language"] == language
                ),
                key=lambda item: item["_rank"],
            )
            chosen.extend(pool[: min(quota, per_version - len(chosen))])
        if len(chosen) < per_version:
            chosen_ids = {
                (item["review_id"], item["action_index"]) for item in chosen
            }
            remaining = sorted(
                (
                    item
                    for item in candidates
                    if (item["review_id"], item["action_index"])
                    not in chosen_ids
                ),
                key=lambda item: item["_rank"],
            )
            chosen.extend(remaining[: per_version - len(chosen)])
        for item in chosen:
            item.pop("_rank", None)
        rows.extend(chosen)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise RuntimeError(f"Cannot write empty CSV: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_comparison_svg(
    path: Path,
    metrics: dict[str, dict[str, Any]],
    manual_review: dict[str, Any] | None = None,
) -> None:
    rows: list[tuple[str, float, float, str, str]] = []
    automatic_specs = [
        ("情感 Accuracy", "sentiment", "accuracy"),
        ("情感 Macro-F1", "sentiment", "macro_f1"),
        ("属性 Precision", "aspects", "precision"),
        ("属性 Recall", "aspects", "recall"),
        ("属性 F1", "aspects", "f1"),
        ("痛点完全匹配率", "issues", "record_exact_match_accuracy"),
        ("证据原文有效率", "evidence_substring", "validity"),
        ("JSON 解析成功率", None, "json_parse_success_rate"),
    ]
    for label, section, field in automatic_specs:
        baseline_value = (
            metrics["baseline"][field]
            if section is None
            else metrics["baseline"][section][field]
        )
        improved_value = (
            metrics["improved"][field]
            if section is None
            else metrics["improved"][section][field]
        )
        rows.append(
            (
                label,
                float(baseline_value),
                float(improved_value),
                f"{float(baseline_value) * 100:.1f}%",
                f"{float(improved_value) * 100:.1f}%",
            )
        )
    if manual_review:
        evidence = manual_review.get("evidence", {})
        if evidence.get("status") == "complete":
            baseline_value = evidence["by_version"]["baseline"][
                "semantic_evidence_validity"
            ]
            improved_value = evidence["by_version"]["improved"][
                "semantic_evidence_validity"
            ]
            rows.append(
                (
                    "人工证据语义有效率",
                    float(baseline_value),
                    float(improved_value),
                    f"{float(baseline_value) * 100:.1f}%",
                    f"{float(improved_value) * 100:.1f}%",
                )
            )
        business = manual_review.get("business_advice", {})
        if business.get("status") == "complete":
            baseline_score = business["by_version"]["baseline"][
                "overall_mean"
            ]
            improved_score = business["by_version"]["improved"][
                "overall_mean"
            ]
            rows.append(
                (
                    "商业建议人工评分",
                    float(baseline_score) / 5,
                    float(improved_score) / 5,
                    f"{float(baseline_score):.2f}/5",
                    f"{float(improved_score):.2f}/5",
                )
            )
    width = 1120
    height = 100 + len(rows) * 70
    plot_x = 220
    plot_width = 780
    baseline_color = "#64748b"
    improved_color = "#2563eb"
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img">',
        "<title>Baseline 与 Improved 模型评测对比</title>",
        "<desc>八项指标的分组水平条形图，数值范围为百分之零到百分之一百。</desc>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="34" font-family="sans-serif" font-size="22" '
        'font-weight="600" fill="#0f172a">Baseline 与 Improved 模型评测对比</text>',
        f'<rect x="{plot_x}" y="50" width="14" height="14" rx="2" '
        f'fill="{baseline_color}"/><text x="{plot_x + 22}" y="62" '
        'font-family="sans-serif" font-size="13" fill="#334155">Baseline</text>',
        f'<rect x="{plot_x + 115}" y="50" width="14" height="14" rx="2" '
        f'fill="{improved_color}"/><text x="{plot_x + 137}" y="62" '
        'font-family="sans-serif" font-size="13" fill="#334155">Improved</text>',
    ]
    for tick in range(0, 101, 20):
        x = plot_x + plot_width * tick / 100
        elements.append(
            f'<line x1="{x:.1f}" y1="80" x2="{x:.1f}" '
            f'y2="{height - 30}" stroke="#e2e8f0" stroke-width="1"/>'
        )
        elements.append(
            f'<text x="{x:.1f}" y="{height - 10}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="12" fill="#64748b">{tick}%</text>'
        )
    for index, (
        label,
        baseline_value,
        improved_value,
        baseline_display,
        improved_display,
    ) in enumerate(rows):
        y = 92 + index * 70
        elements.append(
            f'<text x="{plot_x - 12}" y="{y + 21}" text-anchor="end" '
            f'font-family="sans-serif" font-size="14" fill="#0f172a">'
            f"{html.escape(label)}</text>"
        )
        for offset, value, display, color in (
            (0, baseline_value, baseline_display, baseline_color),
            (27, improved_value, improved_display, improved_color),
        ):
            percent = float(value) * 100
            bar_width = plot_width * float(value)
            elements.append(
                f'<rect x="{plot_x}" y="{y + offset}" '
                f'width="{bar_width:.1f}" height="18" rx="3" fill="{color}"/>'
            )
            label_x = min(plot_x + bar_width + 8, width - 62)
            elements.append(
                f'<text x="{label_x:.1f}" y="{y + offset + 14}" '
                f'font-family="sans-serif" font-size="12" fill="#0f172a">'
                f"{html.escape(display)}</text>"
            )
    elements.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")
