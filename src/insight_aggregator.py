"""Deterministic aggregation and traceable consumer-insight generation."""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


ASPECT_NAMES = {
    "product.efficacy.general_effect": "总体效果",
    "product.efficacy.speed_duration": "起效与持久",
    "product.efficacy.cleansing": "清洁效果",
    "product.efficacy.brightening_whitening": "提亮美白",
    "product.efficacy.hair_styling": "头发造型",
    "product.efficacy.skin_texture": "皮肤质感改善",
    "product.sensory.scent": "气味",
    "product.sensory.texture_consistency": "产品质地",
    "product.sensory.absorption": "吸收",
    "product.sensory.greasiness": "油腻感",
    "product.sensory.stickiness": "黏腻感",
    "product.sensory.residue_staining": "残留染色",
    "product.sensory.comfort_irritation": "舒适刺激",
    "product.appearance.color_shade": "颜色色号",
    "product.appearance.finish_shine": "妆效光泽",
    "product.appearance.design_look": "设计外观",
    "product.usability.ease_of_use": "易用性",
    "product.usability.application_control": "施用控制",
    "product.usability.dispenser": "泵头喷头",
    "product.usability.instructions": "说明书",
    "product.usability.handling_portability": "握持便携",
    "product.quality.material_build": "材质做工",
    "product.quality.durability_breakage": "耐用破损",
    "product.quality.mechanical_electrical": "机械电气",
    "product.suitability.skin_hair_fit": "肤质发质适配",
    "product.suitability.body_area_fit": "部位适配",
    "product.suitability.skill_professional_fit": "技能专业适配",
    "value.price_value": "价格性价比",
    "value.size_quantity": "尺寸数量",
    "packaging.seal_leak_protection": "密封防漏",
    "packaging.arrival_condition": "到货状态",
    "fulfillment.delivery": "配送",
    "fulfillment.item_accuracy": "订单准确完整",
    "fulfillment.return_refund": "退货退款",
    "fulfillment.seller_service": "卖家客服",
    "listing_trust.photo_description_match": "图文一致",
    "listing_trust.authenticity": "真实性",
}

ISSUE_NAMES = {
    "no_effect": "效果无效",
    "insufficient_effect": "效果不足",
    "adverse_reaction": "不良反应",
    "texture_problem": "质地问题",
    "scent_problem": "气味问题",
    "residue_staining": "残留染色",
    "color_mismatch": "颜色不符",
    "size_quantity_mismatch": "尺寸数量不符",
    "leakage_spillage": "泄漏溢出",
    "opened_used_item": "开封或疑似二手",
    "damage_breakage": "损坏断裂",
    "durability_problem": "耐用性问题",
    "mechanical_malfunction": "机械故障",
    "broken_dispenser": "泵头喷头故障",
    "difficult_to_use": "难以使用",
    "wrong_item_variant": "错发商品或变体",
    "missing_parts": "缺件",
    "description_photo_mismatch": "图文不符",
    "counterfeit_suspected": "疑似假货",
    "late_not_delivered": "延迟或未送达",
    "return_refund_problem": "退货退款问题",
    "seller_support_problem": "卖家支持问题",
    "price_value_problem": "价格性价比问题",
    "other_explicit_issue": "其他明确问题",
}

MOTIVATION_NAMES = {
    "efficacy_claim": "效果驱动",
    "price_value": "价格驱动",
    "recommendation": "推荐驱动",
    "brand_familiarity": "品牌熟悉",
    "repeat_purchase": "复购",
    "gift": "送礼",
    "travel_portability": "旅行便携",
    "availability": "可获得性",
    "professional_need": "专业需求",
    "specific_user_need": "特定人群需求",
    "appearance_preference": "外观颜色偏好",
    "convenience": "便利驱动",
}

SCENARIO_NAMES = {
    "daily_routine": "日常护理",
    "travel": "旅行",
    "gift": "送礼",
    "home_household": "家庭家务",
    "professional_salon": "专业沙龙",
    "beginner_practice": "初学练习",
    "sensitive_area": "敏感部位",
    "teen_family": "家庭成员或青少年",
    "client_use": "客户使用",
}

SPEECH_NAMES = {
    "praise": "表扬",
    "complaint": "抱怨",
    "recommendation": "推荐",
    "warning": "警告",
    "suggestion": "建议",
    "comparison": "比较",
    "repurchase_intent": "复购意图",
    "rejection_no_repurchase": "拒绝复购",
    "return_refund_intent": "退货退款意图",
    "request_help": "求助请求",
    "uncertainty_hedging": "不确定缓和",
    "sarcasm_irony": "反讽",
}

GAP_NAMES = {
    "photo_description": "图片描述落差",
    "color_shade": "颜色落差",
    "size_quantity": "尺寸数量落差",
    "product_form": "产品形态落差",
    "performance": "效果落差",
    "delivery": "配送落差",
    "price": "价格落差",
    "authenticity": "真实性落差",
}

CATEGORY_NAMES = {
    "product_improvement": "产品改进",
    "listing_optimization": "商品详情页优化",
    "advertising_selling_point": "广告卖点",
    "content_topic": "内容选题",
    "customer_service_faq": "客服FAQ",
}

VALID_SCOPE_FIELDS = {"product_id", "product_subcategory"}
UNKNOWN_SCOPE_VALUES = {"", "unknown", "null", "none"}
DEFAULT_SMALL_SAMPLE_THRESHOLD = 30


def _normalized_scope_value(value: Any) -> str:
    return "" if value is None else str(value).strip()


def select_scope(
    records: list[dict[str, Any]],
    *,
    scope_field: str | None,
    scope_value: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select a product scope without inferring missing metadata."""

    if scope_field is None and scope_value is None:
        return list(records), {
            "type": "global",
            "field": None,
            "value": None,
            "input_records": len(records),
            "selected_records": len(records),
            "known_scope_records": len(records),
            "unknown_scope_records": 0,
        }
    if scope_field not in VALID_SCOPE_FIELDS:
        raise ValueError(
            f"scope_field must be one of {sorted(VALID_SCOPE_FIELDS)}"
        )
    normalized_value = _normalized_scope_value(scope_value)
    if normalized_value.casefold() in UNKNOWN_SCOPE_VALUES:
        raise ValueError(
            "scope_value must be a known source value, not an unknown marker"
        )

    known_records: list[dict[str, Any]] = []
    unknown_count = 0
    selected: list[dict[str, Any]] = []
    for record in records:
        value = _normalized_scope_value(record.get("source", {}).get(scope_field))
        if value.casefold() in UNKNOWN_SCOPE_VALUES:
            unknown_count += 1
            continue
        known_records.append(record)
        if value == normalized_value:
            selected.append(record)
    if not selected:
        raise ValueError(
            f"No records match {scope_field}={normalized_value!r}"
        )
    return selected, {
        "type": "product_scope",
        "field": scope_field,
        "value": normalized_value,
        "input_records": len(records),
        "selected_records": len(selected),
        "known_scope_records": len(known_records),
        "unknown_scope_records": unknown_count,
    }


def sampling_metadata(
    records: list[dict[str, Any]],
    *,
    strategy: str,
    small_sample_threshold: int,
) -> dict[str, Any]:
    """Describe the denominator and external-validity boundary."""

    if small_sample_threshold < 1:
        raise ValueError("small_sample_threshold must be at least 1")
    strata = Counter(
        f"{record['source']['language']}:{int(record['source']['stars'])}"
        for record in records
    )
    is_small = len(records) < small_sample_threshold
    if strategy == "language_star_stratified":
        note = (
            "Language × star strata were sampled deliberately. Percentages are "
            "descriptive for the selected sample and do not estimate natural "
            "market prevalence."
        )
    else:
        note = (
            "Sampling weights are unavailable. Percentages are descriptive for "
            "the selected sample and do not estimate market prevalence."
        )
    return {
        "strategy": strategy,
        "sample_size": len(records),
        "denominator": "selected unique review records",
        "is_weighted": False,
        "population_prevalence_supported": False,
        "small_sample_threshold": small_sample_threshold,
        "is_small_sample": is_small,
        "warning": (
            f"Only {len(records)} records remain; interpret rankings and rates "
            "as exploratory."
            if is_small
            else None
        ),
        "strata_counts": dict(sorted(strata.items())),
        "note": note,
    }


def _annotate_table_rows(
    tables: dict[str, list[dict[str, Any]]],
    *,
    scope: dict[str, Any],
    sampling: dict[str, Any],
) -> None:
    for rows in tables.values():
        for row in rows:
            row["scope_field"] = scope["field"]
            row["scope_value"] = scope["value"]
            row["sample_size"] = sampling["sample_size"]
            row["is_weighted"] = sampling["is_weighted"]
            row["small_sample_warning"] = sampling["warning"]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON at {path}:{line_number}: {error}"
                ) from error
    return records


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@dataclass
class EvidenceItem:
    review_id: str
    language: str
    stars: int
    quote: str


@dataclass
class StatBucket:
    review_ids: set[str] = field(default_factory=set)
    languages: Counter[str] = field(default_factory=Counter)
    stars: Counter[int] = field(default_factory=Counter)
    polarities: Counter[str] = field(default_factory=Counter)
    language_polarities: dict[str, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    confidences: list[float] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)

    def add(
        self,
        *,
        review_id: str,
        language: str,
        stars: int,
        confidence: float,
        quote: str,
        polarity: str | None = None,
    ) -> None:
        first_for_review = review_id not in self.review_ids
        self.review_ids.add(review_id)
        if first_for_review:
            self.languages[language] += 1
            self.stars[stars] += 1
            self.confidences.append(confidence)
        if polarity:
            self.polarities[polarity] += 1
            self.language_polarities[language][polarity] += 1
        if quote and not any(
            item.review_id == review_id and item.quote == quote
            for item in self.evidence
        ):
            self.evidence.append(
                EvidenceItem(review_id, language, stars, quote)
            )

    @property
    def support_count(self) -> int:
        return len(self.review_ids)

    @property
    def mean_confidence(self) -> float:
        return (
            round(statistics.mean(self.confidences), 4)
            if self.confidences
            else 0.0
        )


def _first_evidence(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return next(
            (item for item in value if isinstance(item, str) and item),
            "",
        )
    return ""


def _selected_evidence(bucket: StatBucket, limit: int = 3) -> list[dict[str, Any]]:
    selected: list[EvidenceItem] = []
    used_languages: set[str] = set()
    for item in bucket.evidence:
        if item.language not in used_languages:
            selected.append(item)
            used_languages.add(item.language)
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        for item in bucket.evidence:
            if item in selected:
                continue
            selected.append(item)
            if len(selected) >= limit:
                break
    return [
        {
            "review_id": item.review_id,
            "language": item.language,
            "stars": item.stars,
            "quote": item.quote,
        }
        for item in selected
    ]


def _confidence_grade(bucket: StatBucket, min_support: int) -> str:
    if bucket.support_count >= max(20, min_support * 4):
        return "high"
    if bucket.support_count >= max(8, min_support * 2):
        return "medium"
    return "exploratory"


def _register(
    groups: dict[str, dict[str, StatBucket]],
    family: str,
    code: str,
    record: dict[str, Any],
    evidence: Any,
    polarity: str | None = None,
) -> None:
    source = record["source"]
    analysis = record["analysis"]
    groups[family].setdefault(code, StatBucket()).add(
        review_id=record["review_id"],
        language=source["language"],
        stars=int(source["stars"]),
        confidence=float(analysis["confidence"]),
        quote=_first_evidence(evidence),
        polarity=polarity,
    )


def build_groups(
    records: Iterable[dict[str, Any]],
) -> dict[str, dict[str, StatBucket]]:
    groups: dict[str, dict[str, StatBucket]] = defaultdict(dict)
    for record in records:
        analysis = record["analysis"]
        stars = int(record["source"]["stars"])
        for item in analysis["aspects"]:
            _register(
                groups,
                "aspects",
                item["aspect"],
                record,
                item["evidence"],
                item["polarity"],
            )
            if item["polarity"] == "positive":
                _register(
                    groups,
                    "positive_aspects",
                    item["aspect"],
                    record,
                    item["evidence"],
                    item["polarity"],
                )
            elif item["polarity"] in {"negative", "mixed"}:
                _register(
                    groups,
                    "negative_aspects",
                    item["aspect"],
                    record,
                    item["evidence"],
                    item["polarity"],
                )
        for item in analysis["issue_types"]:
            _register(
                groups,
                "issues",
                item["issue"],
                record,
                item["evidence"],
            )
            if stars <= 2:
                _register(
                    groups,
                    "low_star_issues",
                    item["issue"],
                    record,
                    item["evidence"],
                )
        for item in analysis["purchase_motivations"]:
            _register(
                groups,
                "motivations",
                item["motivation"],
                record,
                item["evidence"],
            )
            if stars >= 4:
                _register(
                    groups,
                    "high_star_motivations",
                    item["motivation"],
                    record,
                    item["evidence"],
                )
        for item in analysis["usage_scenarios"]:
            _register(
                groups,
                "scenarios",
                item["scenario"],
                record,
                item["evidence"],
            )
        for item in analysis["speech_acts"]:
            _register(
                groups,
                "speech_acts",
                item["speech_act"],
                record,
                item["evidence"],
            )
        gap = analysis["expectation_gap"]
        if gap["present"]:
            _register(
                groups,
                "expectation_gaps",
                gap["type"],
                record,
                gap["evidence"],
            )
    return groups


def aspect_rows(
    groups: dict[str, dict[str, StatBucket]],
    language_totals: Counter[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, bucket in groups["aspects"].items():
        for language in ["en", "es"]:
            mentions = bucket.languages[language]
            language_polarities = bucket.language_polarities[language]
            polarity_total = sum(language_polarities.values())
            rows.append(
                {
                    "aspect_code": code,
                    "aspect_name": ASPECT_NAMES.get(code, code),
                    "language": language,
                    "support_reviews": mentions,
                    "share_of_language_reviews": round(
                        mentions / language_totals[language], 4
                    )
                    if language_totals[language]
                    else 0,
                    "positive_mentions": language_polarities["positive"],
                    "negative_mentions": language_polarities["negative"],
                    "mixed_mentions": language_polarities["mixed"],
                    "neutral_mentions": language_polarities["neutral"],
                    "positive_rate": (
                        round(language_polarities["positive"] / polarity_total, 4)
                        if polarity_total
                        else 0
                    ),
                    "negative_rate": (
                        round(language_polarities["negative"] / polarity_total, 4)
                        if polarity_total
                        else 0
                    ),
                    "mixed_rate": (
                        round(language_polarities["mixed"] / polarity_total, 4)
                        if polarity_total
                        else 0
                    ),
                    "neutral_rate": (
                        round(language_polarities["neutral"] / polarity_total, 4)
                        if polarity_total
                        else 0
                    ),
                    "mean_confidence": bucket.mean_confidence,
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            row["language"],
            -row["support_reviews"],
            row["aspect_code"],
        ),
    )


def bucket_rows(
    buckets: dict[str, StatBucket],
    names: dict[str, str],
    *,
    code_field: str,
) -> list[dict[str, Any]]:
    return [
        {
            code_field: code,
            "name": names.get(code, code),
            "support_reviews": bucket.support_count,
            "en_reviews": bucket.languages["en"],
            "es_reviews": bucket.languages["es"],
            "stars_1": bucket.stars[1],
            "stars_2": bucket.stars[2],
            "stars_3": bucket.stars[3],
            "stars_4": bucket.stars[4],
            "stars_5": bucket.stars[5],
            "mean_confidence": bucket.mean_confidence,
        }
        for code, bucket in sorted(
            buckets.items(),
            key=lambda item: (-item[1].support_count, item[0]),
        )
    ]


def language_comparison_rows(
    groups: dict[str, dict[str, StatBucket]],
    language_totals: Counter[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, bucket in groups["aspects"].items():
        en_rate = (
            bucket.languages["en"] / language_totals["en"]
            if language_totals["en"]
            else 0
        )
        es_rate = (
            bucket.languages["es"] / language_totals["es"]
            if language_totals["es"]
            else 0
        )
        rows.append(
            {
                "aspect_code": code,
                "aspect_name": ASPECT_NAMES.get(code, code),
                "en_support": bucket.languages["en"],
                "es_support": bucket.languages["es"],
                "en_rate": round(en_rate, 4),
                "es_rate": round(es_rate, 4),
                "absolute_rate_gap": round(abs(en_rate - es_rate), 4),
                "higher_attention_language": (
                    "en" if en_rate > es_rate else "es"
                    if es_rate > en_rate
                    else "tie"
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -row["absolute_rate_gap"],
            row["aspect_code"],
        ),
    )


def _candidate(
    *,
    family: str,
    code: str,
    name: str,
    category: str,
    bucket: StatBucket,
    min_support: int,
) -> dict[str, Any] | None:
    evidence = _selected_evidence(bucket)
    if bucket.support_count < min_support or len(evidence) < 2:
        return None
    if category == "product_improvement":
        title = f"优先改善{name}相关痛点"
        product_action = f"围绕“{name}”排查高频失败路径并做针对性改进。"
        marketing_action = "改进完成并验证前，不将该项作为强承诺卖点。"
        content_topic = f"制作“{name}常见问题与正确使用方式”内容。"
    elif category == "listing_optimization":
        title = f"在详情页前置说明{name}"
        product_action = "核对实物、规格和页面承诺是否一致。"
        marketing_action = f"在标题、图片或要点中明确“{name}”的适用边界。"
        content_topic = f"制作“购买前如何判断{name}”说明内容。"
    elif category == "advertising_selling_point":
        title = f"验证后强化{name}卖点"
        product_action = f"持续监测“{name}”在不同批次和人群中的稳定性。"
        marketing_action = f"在证据稳定后，将“{name}”转化为具体、可验证卖点。"
        content_topic = f"围绕“{name}”制作真实使用案例。"
    elif category == "customer_service_faq":
        title = f"建立{name}客服FAQ"
        product_action = "将高频咨询和失败原因反馈给产品与运营团队。"
        marketing_action = "在购买前提示适用条件、处理方式和服务边界。"
        content_topic = f"制作“{name}处理步骤”FAQ内容。"
    else:
        title = f"围绕{name}建设内容专题"
        product_action = "通过进一步用户研究验证不同场景的真实需求。"
        marketing_action = f"按语言和场景测试“{name}”内容表达。"
        content_topic = f"制作“{name}场景指南与案例”系列。"
    return {
        "insight_id": f"{family}:{code}",
        "category": category,
        "category_name": CATEGORY_NAMES[category],
        "title": title,
        "affected_audience": {
            "languages": dict(bucket.languages),
            "star_distribution": {
                str(star): bucket.stars[star] for star in range(1, 6)
            },
        },
        "data_evidence": {
            "support_reviews": bucket.support_count,
            "mean_model_confidence": bucket.mean_confidence,
            "source_review_ids": sorted(bucket.review_ids),
        },
        "representative_quotes": evidence,
        "possible_cause": (
            f"评论集中提及“{name}”，可能反映产品表现、使用方式或页面预期"
            "之间存在差异；评论数据只能提示方向，不能证明因果。"
        ),
        "product_recommendation": product_action,
        "marketing_recommendation": marketing_action,
        "content_topic": content_topic,
        "sample_size_and_confidence": {
            "support_reviews": bucket.support_count,
            "evidence_quotes": len(evidence),
            "grade": _confidence_grade(bucket, min_support),
        },
        "_score": (
            bucket.support_count * 10
            + min(bucket.languages["en"], bucket.languages["es"]) * 2
            + round(bucket.mean_confidence * 5, 2)
        ),
    }


def generate_insights(
    groups: dict[str, dict[str, StatBucket]],
    *,
    min_support: int,
    max_insights: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    specs = [
        (
            "low_star_issues",
            ISSUE_NAMES,
            "product_improvement",
        ),
        (
            "negative_aspects",
            ASPECT_NAMES,
            "product_improvement",
        ),
        (
            "expectation_gaps",
            GAP_NAMES,
            "listing_optimization",
        ),
        (
            "positive_aspects",
            ASPECT_NAMES,
            "advertising_selling_point",
        ),
        (
            "high_star_motivations",
            MOTIVATION_NAMES,
            "advertising_selling_point",
        ),
        (
            "scenarios",
            SCENARIO_NAMES,
            "content_topic",
        ),
        (
            "speech_acts",
            SPEECH_NAMES,
            "content_topic",
        ),
    ]
    for family, names, category in specs:
        for code, bucket in groups[family].items():
            if family == "speech_acts" and code not in {
                "warning",
                "suggestion",
                "repurchase_intent",
                "rejection_no_repurchase",
                "return_refund_intent",
                "request_help",
            }:
                # Generic praise/complaint counts remain in the expression
                # behavior table, but are too broad to become recommendations.
                continue
            actual_category = category
            if code in {
                "request_help",
                "return_refund_intent",
                "return_refund_problem",
                "seller_support_problem",
                "late_not_delivered",
            }:
                actual_category = "customer_service_faq"
            item = _candidate(
                family=family,
                code=code,
                name=names.get(code, code),
                category=actual_category,
                bucket=bucket,
                min_support=min_support,
            )
            if item:
                candidates.append(item)

    candidates.sort(key=lambda item: (-item["_score"], item["insight_id"]))
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for category in CATEGORY_NAMES:
        match = next(
            (
                item
                for item in candidates
                if item["category"] == category
                and item["insight_id"] not in selected_ids
            ),
            None,
        )
        if match:
            selected.append(match)
            selected_ids.add(match["insight_id"])
    for item in candidates:
        if len(selected) >= max_insights:
            break
        if item["insight_id"] in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(item["insight_id"])
    for item in selected:
        item.pop("_score", None)
    return selected


def aggregate_records(
    records: list[dict[str, Any]],
    *,
    min_support: int,
    max_insights: int = 15,
    required_records: int = 1000,
    sampling_strategy: str = "language_star_stratified",
    small_sample_threshold: int = DEFAULT_SMALL_SAMPLE_THRESHOLD,
    scope_field: str | None = None,
    scope_value: str | None = None,
) -> dict[str, Any]:
    scoped_records, scope = select_scope(
        records,
        scope_field=scope_field,
        scope_value=scope_value,
    )
    sampling = sampling_metadata(
        scoped_records,
        strategy=sampling_strategy,
        small_sample_threshold=small_sample_threshold,
    )
    language_totals = Counter(
        record["source"]["language"] for record in scoped_records
    )
    star_totals = Counter(
        int(record["source"]["stars"]) for record in scoped_records
    )
    groups = build_groups(scoped_records)
    insights = generate_insights(
        groups,
        min_support=min_support,
        max_insights=max_insights,
    )
    for insight in insights:
        insight["analysis_scope"] = {
            "field": scope["field"],
            "value": scope["value"],
            "selected_records": scope["selected_records"],
        }
        insight["sampling_boundary"] = {
            "sample_size": sampling["sample_size"],
            "is_weighted": sampling["is_weighted"],
            "population_prevalence_supported": sampling[
                "population_prevalence_supported"
            ],
            "warning": sampling["warning"],
        }
    tables = {
        "aspect_by_language": aspect_rows(groups, language_totals),
        "low_star_pain_points": bucket_rows(
            groups["low_star_issues"],
            ISSUE_NAMES,
            code_field="issue_code",
        ),
        "high_star_purchase_drivers": bucket_rows(
            groups["high_star_motivations"],
            MOTIVATION_NAMES,
            code_field="motivation_code",
        ),
        "usage_scenarios": bucket_rows(
            groups["scenarios"],
            SCENARIO_NAMES,
            code_field="scenario_code",
        ),
        "expectation_gaps": bucket_rows(
            groups["expectation_gaps"],
            GAP_NAMES,
            code_field="gap_code",
        ),
        "speech_acts": bucket_rows(
            groups["speech_acts"],
            SPEECH_NAMES,
            code_field="speech_act_code",
        ),
        "language_focus_comparison": language_comparison_rows(
            groups, language_totals
        ),
    }
    _annotate_table_rows(tables, scope=scope, sampling=sampling)
    return {
        "summary": {
            "records": len(scoped_records),
            "language_counts": dict(sorted(language_totals.items())),
            "star_counts": {
                str(star): star_totals[star] for star in range(1, 6)
            },
            "min_support": min_support,
            "required_records": required_records,
            "insights_generated": len(insights),
            "insight_readiness": (
                "ready"
                if len(scoped_records) >= required_records
                and 10 <= len(insights) <= 15
                else "insufficient_data"
            ),
        },
        "scope": scope,
        "sampling": sampling,
        "tables": tables,
        "insights": insights,
    }


def validate_report_traceability(
    report: dict[str, Any],
    records: list[dict[str, Any]],
) -> list[str]:
    """Check that every insight count and quote traces to its source review."""

    sources = {record["review_id"]: record["source"] for record in records}
    min_support = int(report["summary"]["min_support"])
    failures: list[str] = []
    for item in report["insights"]:
        insight_id = item["insight_id"]
        evidence = item["data_evidence"]
        source_ids = evidence["source_review_ids"]
        if evidence["support_reviews"] != len(set(source_ids)):
            failures.append(
                f"{insight_id}: support count does not match unique source IDs"
            )
        if evidence["support_reviews"] < min_support:
            failures.append(f"{insight_id}: support is below threshold")
        quotes = item["representative_quotes"]
        if not 2 <= len(quotes) <= 3:
            failures.append(f"{insight_id}: requires 2-3 evidence quotes")
        for quote in quotes:
            review_id = quote["review_id"]
            source = sources.get(review_id)
            if source is None:
                failures.append(f"{insight_id}: unknown review ID {review_id}")
                continue
            if review_id not in source_ids:
                failures.append(
                    f"{insight_id}: quote ID {review_id} missing from source IDs"
                )
            source_text = f"{source.get('title', '')}\n{source.get('body', '')}"
            if quote["quote"] not in source_text:
                failures.append(
                    f"{insight_id}: quote is not exact source text for {review_id}"
                )
            if quote["language"] != source.get("language"):
                failures.append(
                    f"{insight_id}: language mismatch for {review_id}"
                )
            if int(quote["stars"]) != int(source.get("stars", 0)):
                failures.append(f"{insight_id}: star mismatch for {review_id}")
    return failures


def markdown_report(report: dict[str, Any], *, title: str) -> str:
    summary = report["summary"]
    lines = [
        f"# {title}",
        "",
        f"- 输入记录：{summary['records']}",
        f"- 语言分布：{summary['language_counts']}",
        f"- 星级分布：{summary['star_counts']}",
        f"- 最小支持评论数：{summary['min_support']}",
        f"- 正式分析要求记录数：{summary['required_records']}",
        f"- 生成洞察：{summary['insights_generated']}",
        f"- 正式洞察就绪状态：`{summary['insight_readiness']}`",
        f"- 分析范围：{report['scope']}",
        f"- 抽样口径：{report['sampling']['note']}",
        "",
    ]
    if report["sampling"]["warning"]:
        lines.extend([f"> {report['sampling']['warning']}", ""])
    if summary["insight_readiness"] != "ready":
        lines.extend(
            [
                "> 当前输入不足以形成 10—15 条正式洞察；以下内容仅用于验证"
                "聚合与证据追溯流程，不应作为正式市场结论。",
                "",
            ]
        )
    for index, item in enumerate(report["insights"], start=1):
        evidence = item["data_evidence"]
        lines.extend(
            [
                f"## {index}. {item['title']}",
                "",
                f"- 洞察分类：{item['category_name']}",
                f"- 影响人群：{item['affected_audience']}",
                (
                    "- 数据证据："
                    f"{evidence['support_reviews']} 条独立评论；"
                    f"平均模型置信度 {evidence['mean_model_confidence']}"
                ),
                "- 典型原话：",
                "",
            ]
        )
        for quote in item["representative_quotes"]:
            lines.append(
                f"  - `{quote['review_id']}`（{quote['language']}，"
                f"{quote['stars']}星）：“{quote['quote']}”"
            )
        lines.extend(
            [
                "",
                f"- 可能原因：{item['possible_cause']}",
                f"- 产品建议：{item['product_recommendation']}",
                f"- 营销建议：{item['marketing_recommendation']}",
                f"- 内容选题：{item['content_topic']}",
                (
                    "- 样本量与可信度："
                    f"{item['sample_size_and_confidence']}"
                ),
                "",
            ]
        )
    return "\n".join(lines)


def save_report_bundle(
    report: dict[str, Any],
    *,
    output_dir: Path,
    report_json: Path,
    report_markdown: Path,
    title: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for table_name, rows in report["tables"].items():
        write_csv(output_dir / f"{table_name}.csv", rows)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_markdown.write_text(
        markdown_report(report, title=title),
        encoding="utf-8",
    )


__all__ = [
    "aggregate_records",
    "load_jsonl",
    "markdown_report",
    "sampling_metadata",
    "save_report_bundle",
    "select_scope",
    "validate_report_traceability",
]
