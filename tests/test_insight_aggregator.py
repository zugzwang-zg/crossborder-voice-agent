"""Tests for deterministic aggregation and traceability."""

from __future__ import annotations

import unittest

from src.insight_aggregator import (
    aggregate_records,
    validate_report_traceability,
)


def record(
    review_id: str,
    *,
    language: str,
    stars: int,
    aspect: str,
    polarity: str,
    evidence: str,
    issue: str | None = None,
    product_id: str = "unknown",
    product_subcategory: str = "unknown",
) -> dict:
    return {
        "review_id": review_id,
        "source": {
            "language": language,
            "stars": stars,
            "title": "",
            "body": evidence,
            "product_id": product_id,
            "product_subcategory": product_subcategory,
        },
        "analysis": {
            "confidence": 0.95,
            "aspects": [
                {
                    "aspect": aspect,
                    "polarity": polarity,
                    "opinion": evidence,
                    "evidence": [evidence],
                }
            ],
            "issue_types": (
                [{"issue": issue, "evidence": evidence}] if issue else []
            ),
            "purchase_motivations": [],
            "usage_scenarios": [],
            "speech_acts": [],
            "expectation_gap": {
                "present": False,
                "type": "none",
                "evidence": [],
            },
        },
    }


class AggregatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            record(
                "en_1",
                language="en",
                stars=1,
                aspect="product.usability.ease_of_use",
                polarity="negative",
                evidence="Hard to apply",
                issue="difficult_to_use",
            ),
            record(
                "es_1",
                language="es",
                stars=2,
                aspect="product.usability.ease_of_use",
                polarity="negative",
                evidence="Difícil de aplicar",
                issue="difficult_to_use",
            ),
        ]

    def test_counts_distinct_reviews_and_languages(self) -> None:
        report = aggregate_records(
            self.records,
            min_support=2,
            max_insights=15,
        )
        pain = report["tables"]["low_star_pain_points"][0]
        self.assertEqual(pain["support_reviews"], 2)
        self.assertEqual(pain["en_reviews"], 1)
        self.assertEqual(pain["es_reviews"], 1)

    def test_aspect_polarity_counts_are_language_specific(self) -> None:
        records = [
            record(
                "en_positive",
                language="en",
                stars=5,
                aspect="product.usability.ease_of_use",
                polarity="positive",
                evidence="Easy to apply",
            ),
            record(
                "es_negative",
                language="es",
                stars=1,
                aspect="product.usability.ease_of_use",
                polarity="negative",
                evidence="Difícil de aplicar",
            ),
        ]
        report = aggregate_records(records, min_support=2, max_insights=15)
        rows = report["tables"]["aspect_by_language"]
        english = next(row for row in rows if row["language"] == "en")
        spanish = next(row for row in rows if row["language"] == "es")
        self.assertEqual(english["positive_mentions"], 1)
        self.assertEqual(english["negative_mentions"], 0)
        self.assertEqual(english["positive_rate"], 1.0)
        self.assertEqual(spanish["positive_mentions"], 0)
        self.assertEqual(spanish["negative_mentions"], 1)
        self.assertEqual(spanish["negative_rate"], 1.0)

    def test_taste_only_evidence_does_not_support_scent_aspect(self) -> None:
        mixed_evidence = record(
            "en_mixed_evidence",
            language="en",
            stars=5,
            aspect="product.sensory.scent",
            polarity="positive",
            evidence="Tastes minty",
        )
        mixed_evidence["analysis"]["aspects"][0]["evidence"].append(
            "It smells fresh"
        )
        records = [
            record(
                "en_taste",
                language="en",
                stars=5,
                aspect="product.sensory.scent",
                polarity="positive",
                evidence="The taste is really delicious",
            ),
            record(
                "en_scent",
                language="en",
                stars=5,
                aspect="product.sensory.scent",
                polarity="positive",
                evidence="Smells delicious",
            ),
            record(
                "es_scent",
                language="es",
                stars=5,
                aspect="product.sensory.scent",
                polarity="positive",
                evidence="Su aroma es agradable",
            ),
            mixed_evidence,
        ]

        report = aggregate_records(records, min_support=2, max_insights=15)
        scent = next(
            item for item in report["insights"]
            if item["insight_id"] == "positive_aspects:product.sensory.scent"
        )
        self.assertEqual(scent["data_evidence"]["support_reviews"], 3)
        self.assertEqual(
            scent["data_evidence"]["source_review_ids"],
            ["en_mixed_evidence", "en_scent", "es_scent"],
        )
        self.assertNotIn(
            "The taste is really delicious",
            {quote["quote"] for quote in scent["representative_quotes"]},
        )
        self.assertIn(
            "It smells fresh",
            {quote["quote"] for quote in scent["representative_quotes"]},
        )

    def test_insight_has_two_traceable_quotes(self) -> None:
        report = aggregate_records(
            self.records,
            min_support=2,
            max_insights=15,
        )
        matching = [
            item
            for item in report["insights"]
            if item["insight_id"] == "low_star_issues:difficult_to_use"
        ]
        self.assertEqual(len(matching), 1)
        item = matching[0]
        self.assertEqual(
            item["data_evidence"]["source_review_ids"],
            ["en_1", "es_1"],
        )
        self.assertEqual(len(item["representative_quotes"]), 2)
        self.assertEqual(
            {quote["quote"] for quote in item["representative_quotes"]},
            {"Hard to apply", "Difícil de aplicar"},
        )

    def test_product_actions_do_not_add_unsupported_priority_usage_or_fulfillment(self) -> None:
        report = aggregate_records(
            self.records,
            min_support=2,
            max_insights=15,
        )
        item = next(
            insight for insight in report["insights"]
            if insight["insight_id"]
            == "negative_aspects:product.usability.ease_of_use"
        )
        self.assertNotIn("优先", item["title"])
        self.assertNotIn("履约", item["recommended_action"])
        self.assertNotIn("正确使用", item["content_topic"])
        self.assertNotIn("常见问题", item["content_topic"])
        self.assertIn("验证后", item["recommended_action"])
        self.assertIn(
            item["support_volume_tier"], {"exploratory", "medium", "high"}
        )
        self.assertEqual(
            item["confidence_or_evidence_grade"],
            f"{item['support_volume_tier']}_support_volume",
        )
        self.assertEqual(
            item["sample_size_and_confidence"]["grade_semantics"],
            "deterministic_support_volume_only",
        )
        self.assertEqual(
            item["sample_size_and_confidence"]["configured_min_support"], 2
        )

    def test_small_input_is_not_marked_ready(self) -> None:
        report = aggregate_records(
            self.records,
            min_support=2,
            max_insights=15,
        )
        self.assertEqual(
            report["summary"]["insight_readiness"],
            "insufficient_data",
        )
        self.assertTrue(report["sampling"]["is_small_sample"])
        self.assertFalse(report["sampling"]["is_weighted"])
        self.assertFalse(
            report["sampling"]["population_prevalence_supported"]
        )
        self.assertIn("exploratory", report["sampling"]["warning"])
        self.assertIsNone(report["scope"]["known_scope_records"])
        self.assertEqual(
            report["scope"]["scope_metadata_status"],
            "not_applicable_for_global_scope",
        )

    def test_product_scope_excludes_other_products_and_annotates_tables(self) -> None:
        records = [
            record(
                "p1_en",
                language="en",
                stars=1,
                aspect="product.usability.ease_of_use",
                polarity="negative",
                evidence="Hard to use",
                issue="difficult_to_use",
                product_id="P1",
                product_subcategory="serum",
            ),
            record(
                "p1_es",
                language="es",
                stars=2,
                aspect="product.usability.ease_of_use",
                polarity="negative",
                evidence="Difícil de usar",
                issue="difficult_to_use",
                product_id="P1",
                product_subcategory="serum",
            ),
            record(
                "p2_en",
                language="en",
                stars=1,
                aspect="product.sensory.scent",
                polarity="negative",
                evidence="Bad smell",
                issue="scent_problem",
                product_id="P2",
                product_subcategory="cleanser",
            ),
        ]
        report = aggregate_records(
            records,
            min_support=2,
            scope_field="product_id",
            scope_value="P1",
        )
        self.assertEqual(report["summary"]["records"], 2)
        self.assertEqual(report["scope"]["value"], "P1")
        self.assertEqual(report["scope"]["selected_records"], 2)
        pain = report["tables"]["low_star_pain_points"][0]
        self.assertEqual(pain["issue_code"], "difficult_to_use")
        self.assertEqual(pain["sample_size"], 2)
        self.assertEqual(pain["scope_value"], "P1")
        self.assertTrue(pain["small_sample_warning"])
        self.assertEqual(report["insights"][0]["analysis_scope"]["value"], "P1")
        insight = report["insights"][0]
        self.assertEqual(insight["scope"]["value"], "P1")
        self.assertEqual(insight["support_count"], 2)
        self.assertEqual(insight["support_rate"], 1.0)
        self.assertEqual(insight["action_type"], "product")
        self.assertTrue(insight["recommended_action"])
        self.assertEqual(
            insight["representative_review_ids"],
            insight["data_evidence"]["source_review_ids"],
        )
        self.assertTrue(insight["limitations"])

    def test_packaging_and_fulfillment_use_distinct_operational_routes(self) -> None:
        records = [
            record(
                "packaging_en",
                language="en",
                stars=1,
                aspect="packaging.arrival_condition",
                polarity="negative",
                evidence="The package arrived crushed",
            ),
            record(
                "packaging_es",
                language="es",
                stars=2,
                aspect="packaging.arrival_condition",
                polarity="negative",
                evidence="El paquete llegó aplastado",
            ),
            record(
                "fulfillment_en",
                language="en",
                stars=1,
                aspect="fulfillment.delivery",
                polarity="negative",
                evidence="Delivery was delayed",
            ),
            record(
                "fulfillment_es",
                language="es",
                stars=2,
                aspect="fulfillment.delivery",
                polarity="negative",
                evidence="La entrega se retrasó",
            ),
        ]
        report = aggregate_records(records, min_support=2, max_insights=15)
        by_id = {item["insight_id"]: item for item in report["insights"]}

        packaging = by_id["negative_aspects:packaging.arrival_condition"]
        self.assertEqual(packaging["category"], "packaging_improvement")
        self.assertEqual(packaging["action_type"], "packaging")
        self.assertIn("包装", packaging["recommended_action"])
        self.assertIn("假设", packaging["recommended_action"])
        self.assertIn("调查工单", packaging["recommended_action"])
        self.assertNotIn("失败路径", packaging["recommended_action"])
        self.assertIn("仓储", packaging["possible_cause"])
        self.assertNotIn("使用方式", packaging["possible_cause"])
        self.assertEqual(packaging["title"], "调查到货状态异常")
        self.assertIn("包装与运营负责人", packaging["recommended_action"])
        self.assertIn("物流与运营负责人", packaging["recommended_action"])
        self.assertIn("仅在事件分类与调查确认", packaging["content_topic"])

        fulfillment = by_id["negative_aspects:fulfillment.delivery"]
        self.assertEqual(fulfillment["category"], "fulfillment_improvement")
        self.assertEqual(fulfillment["action_type"], "fulfillment")
        self.assertIn("物流与运营负责人", fulfillment["recommended_action"])
        self.assertIn("待验证潜在原因", fulfillment["recommended_action"])
        self.assertNotIn("失败路径", fulfillment["recommended_action"])
        self.assertIn("承运", fulfillment["possible_cause"])
        self.assertNotIn("产品表现", fulfillment["possible_cause"])
        self.assertIn("跟踪或支持信息缺口", fulfillment["content_topic"])

    def test_reviewed_templates_do_not_overstate_or_misroute_causes(self) -> None:
        performance_records = [
            record(
                "gap_en",
                language="en",
                stars=2,
                aspect="product.efficacy.general_effect",
                polarity="negative",
                evidence="It did not work as expected",
            ),
            record(
                "gap_es",
                language="es",
                stars=2,
                aspect="product.efficacy.general_effect",
                polarity="negative",
                evidence="No funcionó como esperaba",
            ),
        ]
        for item in performance_records:
            item["analysis"]["expectation_gap"] = {
                "present": True,
                "type": "performance",
                "evidence": [item["source"]["body"]],
            }
        performance = next(
            item
            for item in aggregate_records(
                performance_records, min_support=2
            )["insights"]
            if item["insight_id"] == "expectation_gaps:performance"
        )
        self.assertIn("核验后", performance["recommended_action"])
        self.assertNotIn("已验证", performance["recommended_action"])
        self.assertIn("预期结果", performance["content_topic"])
        self.assertNotIn("如何判断", performance["content_topic"])

        late_records = [
            record(
                "late_en",
                language="en",
                stars=1,
                aspect="fulfillment.delivery",
                polarity="negative",
                evidence="It never arrived",
                issue="late_not_delivered",
            ),
            record(
                "late_es",
                language="es",
                stars=1,
                aspect="fulfillment.delivery",
                polarity="negative",
                evidence="Nunca llegó",
                issue="late_not_delivered",
            ),
        ]
        late = next(
            item
            for item in aggregate_records(late_records, min_support=2)["insights"]
            if item["insight_id"] == "low_star_issues:late_not_delivered"
        )
        self.assertEqual(late["action_type"], "faq")
        self.assertIn("跟踪信息", late["possible_cause"])
        self.assertNotIn("使用方式", late["possible_cause"])
        self.assertIn("待验证假设", late["product_recommendation"])
        self.assertNotIn("高频咨询", late["product_recommendation"])
        self.assertIn("升级渠道", late["marketing_recommendation"])

    def test_repurchase_cause_is_tied_to_repurchase_signal(self) -> None:
        records = [
            record(
                "repeat_en",
                language="en",
                stars=5,
                aspect="product.efficacy.general_effect",
                polarity="positive",
                evidence="I will buy it again",
            ),
            record(
                "repeat_es",
                language="es",
                stars=5,
                aspect="product.efficacy.general_effect",
                polarity="positive",
                evidence="Lo compraré de nuevo",
            ),
        ]
        for item in records:
            item["analysis"]["speech_acts"] = [
                {
                    "speech_act": "repurchase_intent",
                    "evidence": item["source"]["body"],
                }
            ]
        repurchase = next(
            item
            for item in aggregate_records(records, min_support=2)["insights"]
            if item["insight_id"] == "speech_acts:repurchase_intent"
        )
        self.assertIn("复购表述", repurchase["possible_cause"])
        self.assertIn("再次购买意愿", repurchase["possible_cause"])
        self.assertNotIn("页面预期", repurchase["possible_cause"])
        self.assertIn("复购行为与意向", repurchase["title"])
        self.assertIn("历史评论中的复购表述", repurchase["product_recommendation"])

    def test_remediation_four_templates_and_evidence_are_bounded(self) -> None:
        specs = [
            ("effect_en", "en", 5, "product.efficacy.general_effect", "positive", "It really works"),
            ("effect_es", "es", 5, "product.efficacy.general_effect", "positive", "Cumple con su función"),
            ("value_en", "en", 5, "value.price_value", "positive", "Good value for the price"),
            ("value_es", "es", 5, "value.price_value", "positive", "Buena relación calidad precio"),
            ("durability_generic", "en", 2, "product.quality.durability_breakage", "negative", "Cheaply made"),
            ("durability_en", "en", 1, "product.quality.durability_breakage", "negative", "The strap broke in a week"),
            ("durability_es", "es", 1, "product.quality.durability_breakage", "negative", "Se rompió en una semana"),
            ("scent_en", "en", 2, "product.sensory.scent", "negative", "Smelled horrible"),
            ("scent_es", "es", 2, "product.sensory.scent", "negative", "Desprende mucho olor"),
        ]
        records = [
            record(
                review_id,
                language=language,
                stars=stars,
                aspect=aspect,
                polarity=polarity,
                evidence=evidence,
            )
            for review_id, language, stars, aspect, polarity, evidence in specs
        ]
        insights = {
            item["insight_id"]: item
            for item in aggregate_records(records, min_support=2)["insights"]
        }

        effect = insights["positive_aspects:product.efficacy.general_effect"]
        self.assertIn("不能确定评价形成的原因", effect["possible_cause"])
        self.assertNotIn("使用方式", effect["possible_cause"])
        self.assertNotIn("页面预期", effect["possible_cause"])

        value = insights["positive_aspects:value.price_value"]
        self.assertIn("当前在售产品及版本", value["marketing_recommendation"])
        self.assertIn("当前价格", value["marketing_recommendation"])
        self.assertIn("2015—2019年历史证据", value["marketing_recommendation"])
        self.assertIn("不验证声明真实性", value["marketing_recommendation"])

        durability = insights["negative_aspects:product.quality.durability_breakage"]
        durability_quotes = {
            quote["quote"] for quote in durability["representative_quotes"]
        }
        self.assertNotIn("Cheaply made", durability_quotes)
        self.assertIn("The strap broke in a week", durability_quotes)

        scent = insights["negative_aspects:product.sensory.scent"]
        self.assertIn("需要区分且可能重叠", scent["possible_cause"])
        self.assertNotIn("相互独立", scent["possible_cause"])

    def test_representative_quotes_reject_known_semantic_conflicts(self) -> None:
        records = [
            record(
                "effect_bad",
                language="en",
                stars=4,
                aspect="product.efficacy.general_effect",
                polarity="positive",
                evidence="I loved the actual hair ties",
            ),
            record(
                "effect_en",
                language="en",
                stars=4,
                aspect="product.efficacy.general_effect",
                polarity="positive",
                evidence="It really works",
            ),
            record(
                "effect_es",
                language="es",
                stars=4,
                aspect="product.efficacy.general_effect",
                polarity="positive",
                evidence="Cumple con su función",
            ),
            record(
                "insufficient_retention",
                language="en",
                stars=1,
                aspect="product.efficacy.hair_styling",
                polarity="negative",
                evidence="These do not stay in place.",
                issue="insufficient_effect",
            ),
            record(
                "insufficient_direct_en",
                language="en",
                stars=1,
                aspect="product.efficacy.general_effect",
                polarity="negative",
                evidence="It did not work well for me",
                issue="insufficient_effect",
            ),
            record(
                "insufficient_direct_es",
                language="es",
                stars=1,
                aspect="product.efficacy.general_effect",
                polarity="negative",
                evidence="No hidrata lo suficiente",
                issue="insufficient_effect",
            ),
            record(
                "scent_weak",
                language="es",
                stars=4,
                aspect="product.sensory.scent",
                polarity="positive",
                evidence="su aroma",
            ),
            record(
                "scent_en",
                language="en",
                stars=4,
                aspect="product.sensory.scent",
                polarity="positive",
                evidence="Smells very good",
            ),
            record(
                "scent_es",
                language="es",
                stars=4,
                aspect="product.sensory.scent",
                polarity="positive",
                evidence="Tiene un olor increíble",
            ),
            record(
                "use_missing",
                language="en",
                stars=2,
                aspect="product.usability.ease_of_use",
                polarity="negative",
                evidence="there was no cleaning brush",
            ),
            record(
                "use_en",
                language="en",
                stars=2,
                aspect="product.usability.ease_of_use",
                polarity="negative",
                evidence="Hard to apply",
            ),
            record(
                "use_es",
                language="es",
                stars=2,
                aspect="product.usability.ease_of_use",
                polarity="negative",
                evidence="Muy difícil de usar",
            ),
        ]
        insights = {
            item["insight_id"]: item
            for item in aggregate_records(records, min_support=2)["insights"]
        }
        effect_quotes = {
            quote["quote"]
            for quote in insights[
                "positive_aspects:product.efficacy.general_effect"
            ]["representative_quotes"]
        }
        scent_quotes = {
            quote["quote"]
            for quote in insights[
                "positive_aspects:product.sensory.scent"
            ]["representative_quotes"]
        }
        usability_quotes = {
            quote["quote"]
            for quote in insights[
                "negative_aspects:product.usability.ease_of_use"
            ]["representative_quotes"]
        }
        insufficient_quotes = {
            quote["quote"]
            for quote in insights[
                "low_star_issues:insufficient_effect"
            ]["representative_quotes"]
        }
        self.assertNotIn("I loved the actual hair ties", effect_quotes)
        self.assertNotIn("su aroma", scent_quotes)
        self.assertNotIn("there was no cleaning brush", usability_quotes)
        self.assertNotIn("These do not stay in place.", insufficient_quotes)

    def test_release_insights_exclude_model_confidence_and_audit_support_rate(self) -> None:
        report = aggregate_records(self.records, min_support=2, max_insights=15)
        for insight in report["insights"]:
            self.assertNotIn("mean_model_confidence", insight["data_evidence"])
            audit = insight["support_rate_audit"]
            self.assertEqual(audit["numerator"], insight["support_count"])
            self.assertEqual(audit["denominator"], len(self.records))
            self.assertEqual(audit["value"], insight["support_rate"])

    def test_unknown_scope_cannot_be_presented_as_product_analysis(self) -> None:
        with self.assertRaisesRegex(ValueError, "known source value"):
            aggregate_records(
                self.records,
                min_support=2,
                scope_field="product_id",
                scope_value="unknown",
            )

    def test_traceability_validator_rejects_changed_quote(self) -> None:
        report = aggregate_records(
            self.records,
            min_support=2,
            max_insights=15,
        )
        report["insights"][0]["representative_quotes"][0]["quote"] = (
            "not in source"
        )
        failures = validate_report_traceability(report, self.records)
        self.assertTrue(any("not exact source text" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
