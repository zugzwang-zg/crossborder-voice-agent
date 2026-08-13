from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock

from tools.ai_review_workflow import (
    BudgetController,
    BudgetExceeded,
    OpenAIReviewer,
    PRIMARY_STAGES,
    REQUIRED_STAGES,
    SCORE_DIMENSIONS,
    _io_safe_path,
    adjudication_reasons,
    aggregate_item,
    export_external_packets,
    external_role_map,
    load_jsonl,
    load_pricing_config,
    prepare_api_payload,
    prepare_external_packet_payload,
    run_stage_smoke,
    run_workflow,
    scan_sensitive_data,
    sha256_json,
    validate_config,
    validate_item,
    validate_items,
    validate_review,
    validate_private_output,
)


ROOT = Path(__file__).resolve().parents[1]


def make_review(item: dict, role: dict, *, decision: str = "pass", score: int = 5) -> dict:
    return {
        "schema_version": "1.1",
        "item_id": item["item_id"],
        "role_id": role["role_id"],
        "model": role["model"],
        "input_sha256": sha256_json(item),
        "decision": decision,
        "confidence": 0.8,
        "scores": {dimension: score for dimension in SCORE_DIMENSIONS},
        "findings": [],
        "summary": "Bounded test review.",
        "limitations": ["AI pre-review is not human evaluation."],
    }


def make_audited_review(
    item: dict,
    role: dict,
    runtime_identity: dict,
    *,
    decision: str = "pass",
) -> dict:
    review = make_review(item, role, decision=decision)
    expected_role = runtime_identity["roles"][role["stage"]]
    review["_audit"] = {
        "identity_schema_version": "1.0",
        "response_id": f"response-{role['role_id']}",
        "requested_model": role["model"],
        "response_model": role["model"],
        "model_resolution_status": "exact_requested_model",
        "reasoning_effort_requested": role["reasoning_effort"],
        "sdk": runtime_identity["sdk"],
        "endpoint": runtime_identity["endpoint"],
        "runner_sha256": runtime_identity["runner_sha256"],
        "review_schema_sha256": runtime_identity["review_schema_sha256"],
        "system_prompt_sha256": expected_role["system_prompt_sha256"],
        "request_messages_sha256": "0" * 64,
        "response_service_tier": "default",
        "system_fingerprint": None,
        "response_created_at": 1786200000,
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }
    return review


class AIReviewWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(
            (ROOT / "config" / "ai_review_roles.json").read_text(encoding="utf-8")
        )
        self.stage_map = validate_config(self.config)
        self.item = load_jsonl(ROOT / "data" / "sample" / "ai_review_input.demo.jsonl")[0]

    def test_config_uses_three_distinct_models_for_blind_stages(self) -> None:
        models = {self.stage_map[stage]["model"] for stage in PRIMARY_STAGES}
        self.assertEqual(len(models), 3)
        external = self.config["external_reviewers"][0]
        self.assertEqual(external["model_label"], "deepseek-v4-pro")
        self.assertEqual(external["execution"], "manual_isolated_session")

    def test_nano_fork_uses_pinned_distinct_mechanical_model(self) -> None:
        config = json.loads(
            (ROOT / "config" / "ai_review_roles_nano.json").read_text(
                encoding="utf-8"
            )
        )
        stages = validate_config(config)
        self.assertEqual(
            stages["mechanical_screen"]["model"],
            "gpt-5.4-nano-2026-03-17",
        )
        self.assertEqual(
            len({stages[stage]["model"] for stage in PRIMARY_STAGES}), 3
        )
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 12),
        )
        nano = pricing["models"]["gpt-5.4-nano-2026-03-17"]
        self.assertEqual(nano["output_usd_per_million_tokens"], 1.25)
        self.assertTrue(nano["source_url"].startswith("https://developers.openai.com/"))

    def test_gpt54_snapshot_fork_uses_official_pinned_pricing(self) -> None:
        config = json.loads(
            (ROOT / "config" / "ai_review_roles_gpt54_snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        stages = validate_config(config)
        self.assertEqual(
            stages["mechanical_screen"]["model"],
            "gpt-5.4-2026-03-05",
        )
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 12),
        )
        snapshot = pricing["models"]["gpt-5.4-2026-03-05"]
        self.assertEqual(snapshot["input_usd_per_million_tokens"], 2.5)
        self.assertEqual(snapshot["output_usd_per_million_tokens"], 15.0)
        self.assertEqual(
            snapshot["source_url"],
            "https://developers.openai.com/api/docs/models/gpt-5.4",
        )

    def test_demo_item_and_matching_review_are_valid(self) -> None:
        validate_item(self.item, self.config["project"])
        role = self.stage_map["semantic_review"]
        validate_review(make_review(self.item, role), self.item, role)

    def test_external_packet_exports_the_evidence_location_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = export_external_packets(
                [self.item], self.config, Path(directory)
            )
            self.assertEqual(result["packet_count"], 1)
            packet_path = next(Path(directory).glob("*.packet.json"))
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            finding = packet["output_contract"]["properties"]["findings"]["items"]
            self.assertEqual(packet["schema_version"], "1.1")
            self.assertIn("evidence_path", finding["required"])
            self.assertEqual(packet["evidence_policy"]["quote_limits"]["max_characters"], 280)

    def test_external_packet_export_supports_long_windows_paths(self) -> None:
        long_item = dict(self.item)
        long_item["item_id"] = (
            "rc1-insight-01-negative-aspects-product-efficacy-general-effect"
        )
        directory = tempfile.mkdtemp()
        try:
            output_dir = Path(directory) / ("long-output-" + "x" * 150)
            result = export_external_packets(
                [long_item], self.config, output_dir
            )
            packet_path = _io_safe_path(
                output_dir
                / (
                    f"{long_item['item_id']}."
                    "cross_provider_adversarial_reviewer.packet.json"
                )
            )
            self.assertGreater(len(str(packet_path)), 260)
            self.assertTrue(packet_path.is_file())
            self.assertEqual(result["packet_count"], 1)
        finally:
            shutil.rmtree(_io_safe_path(Path(directory)), ignore_errors=True)

    def test_external_packet_export_rejects_stale_packet_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stale = Path(directory) / "old-item.external.packet.json"
            stale.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stale packet files"):
                export_external_packets([self.item], self.config, Path(directory))

    def test_disagreement_requires_adjudication(self) -> None:
        reviews = {
            stage: make_review(self.item, self.stage_map[stage]) for stage in PRIMARY_STAGES
        }
        reviews["risk_review"]["decision"] = "block"
        self.assertIn("independent_decision_disagreement", adjudication_reasons(reviews))
        self.assertIn("blocking_decision", adjudication_reasons(reviews))

    def test_mechanical_revise_cannot_be_silently_passed(self) -> None:
        reviews = {
            stage: make_review(self.item, self.stage_map[stage]) for stage in PRIMARY_STAGES
        }
        reviews["mechanical_screen"]["decision"] = "revise"
        self.assertIn("independent_decision_disagreement", adjudication_reasons(reviews))

    def test_review_rejects_quote_not_present_in_named_source(self) -> None:
        role = self.stage_map["risk_review"]
        review = make_review(self.item, role, decision="revise")
        review["findings"] = [{
            "category": "evidence",
            "severity": "high",
            "claim": "The quote was fabricated.",
            "evidence_quote": "words that do not occur",
            "reference_id": "source_review",
            "evidence_path": "/references/0/content",
            "evidence_start": 0,
            "evidence_end": 23,
            "recommendation": "Use an exact source span.",
        }]
        with self.assertRaisesRegex(ValueError, "exact source substring"):
            validate_review(review, self.item, role)

    def test_unicode_duplicate_evidence_uses_escaped_path_and_offsets(self) -> None:
        item = json.loads(json.dumps(self.item))
        source = "前缀🙂证据；重复🙂证据"
        item["candidate"]["detail/key~name"] = source
        role = self.stage_map["semantic_review"]
        review = make_review(item, role, decision="revise")
        start = source.rindex("证据")
        review["findings"] = [{
            "category": "evidence",
            "severity": "medium",
            "claim": "The second repeated span is the decisive evidence.",
            "evidence_quote": "证据",
            "reference_id": "candidate",
            "evidence_path": "/candidate/detail~1key~0name",
            "evidence_start": start,
            "evidence_end": start + len("证据"),
            "recommendation": "Keep the finding bound to the selected occurrence.",
        }]
        validate_review(review, item, role)

        review["findings"][0]["evidence_start"] = start - 1
        with self.assertRaisesRegex(ValueError, "exact source substring"):
            validate_review(review, item, role)

    def test_review_rejects_overwide_or_cross_source_evidence(self) -> None:
        item = json.loads(json.dumps(self.item))
        item["candidate"]["long_evidence"] = "x" * 281
        role = self.stage_map["risk_review"]
        review = make_review(item, role, decision="revise")
        review["findings"] = [{
            "category": "evidence",
            "severity": "medium",
            "claim": "The quote is too broad.",
            "evidence_quote": "x" * 281,
            "reference_id": "candidate",
            "evidence_path": "/candidate/long_evidence",
            "evidence_start": 0,
            "evidence_end": 281,
            "recommendation": "Quote only the decisive span.",
        }]
        with self.assertRaisesRegex(ValueError, "at most 280 characters"):
            validate_review(review, item, role)

        item["candidate"]["long_evidence"] = "line 1\nline 2\nline 3\nline 4"
        review = make_review(item, role, decision="revise")
        review["findings"] = [{
            "category": "evidence", "severity": "medium",
            "claim": "The quote spans too many lines.",
            "evidence_quote": item["candidate"]["long_evidence"],
            "reference_id": "candidate", "evidence_path": "/candidate/long_evidence",
            "evidence_start": 0, "evidence_end": len(item["candidate"]["long_evidence"]),
            "recommendation": "Select the decisive lines only.",
        }]
        with self.assertRaisesRegex(ValueError, "at most 3 lines"):
            validate_review(review, item, role)

        item["candidate"]["long_evidence"] = " padded quote "
        review = make_review(item, role, decision="revise")
        review["findings"] = [{
            "category": "evidence", "severity": "medium",
            "claim": "The quote includes boundary whitespace.",
            "evidence_quote": item["candidate"]["long_evidence"],
            "reference_id": "candidate", "evidence_path": "/candidate/long_evidence",
            "evidence_start": 0, "evidence_end": len(item["candidate"]["long_evidence"]),
            "recommendation": "Trim the quote and adjust its offsets.",
        }]
        with self.assertRaisesRegex(ValueError, "boundary whitespace"):
            validate_review(review, item, role)

        source = item["references"][0]["content"]
        quote = "felt soft"
        start = source.index(quote)
        review = make_review(item, role, decision="revise")
        review["findings"] = [{
            "category": "evidence",
            "severity": "medium",
            "claim": "A duplicated value cannot change the named source.",
            "evidence_quote": quote,
            "reference_id": "source_review",
            "evidence_path": "/candidate/source_review",
            "evidence_start": start,
            "evidence_end": start + len(quote),
            "recommendation": "Use the named reference content path.",
        }]
        with self.assertRaisesRegex(ValueError, "named reference content"):
            validate_review(review, item, role)

    def test_duplicate_item_ids_are_rejected_before_output(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate item_id"):
            validate_items([self.item, dict(self.item)], self.config["project"])

    def test_external_high_finding_is_imported_and_forces_adjudication(self) -> None:
        external_role = next(iter(external_role_map(self.config).values()))
        external = make_review(self.item, external_role, decision="revise")
        external["findings"] = [{
            "category": "evidence_boundary",
            "severity": "high",
            "claim": "The delivery claim needs owner review.",
            "evidence_quote": "arrived three days late",
            "reference_id": "source_review",
            "evidence_path": "/references/0/content",
            "evidence_start": 37,
            "evidence_end": 60,
            "recommendation": "Keep the conclusion scoped to this review.",
        }]

        def fake_review(item: dict, role: dict, prior_reviews: list[dict] | None) -> dict:
            return make_review(item, role)

        with tempfile.TemporaryDirectory() as directory:
            manifest = run_workflow(
                [self.item], self.config, Path(directory), fake_review,
                external_reviews=[external],
            )
            summary = json.loads(
                (Path(directory) / manifest["run_id"] / "summary.jsonl")
                .read_text(encoding="utf-8").strip()
            )
            self.assertTrue(summary["external_review_complete"])
            self.assertTrue(summary["adjudication_used"])
            self.assertIn("external_high_or_critical_finding", summary["adjudication_reasons"])

    def test_pass_still_requires_owner_and_forbids_human_claim(self) -> None:
        reviews = {
            stage: make_review(self.item, self.stage_map[stage]) for stage in PRIMARY_STAGES
        }
        summary = aggregate_item(self.item, reviews, [])
        self.assertEqual(summary["status"], "ai_pre_review_passed")
        self.assertTrue(summary["owner_signoff_required"])
        self.assertFalse(summary["human_evaluation_claim_allowed"])

    def test_offline_fake_run_writes_auditable_manifest(self) -> None:
        def fake_review(item: dict, role: dict, prior_reviews: list[dict] | None) -> dict:
            return make_review(item, role)

        with tempfile.TemporaryDirectory() as directory:
            manifest = run_workflow(
                [self.item], self.config, Path(directory), fake_review
            )
            run_dir = Path(directory) / manifest["run_id"]
            self.assertTrue((run_dir / "run_manifest.json").is_file())
            self.assertTrue((run_dir / "summary.jsonl").is_file())
            self.assertEqual(manifest["claim_scope"], "ai_pre_review_only_not_human_evaluation")
            summary = json.loads((run_dir / "summary.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "external_review_pending")

    def test_offline_run_supports_long_windows_result_paths(self) -> None:
        def fake_review(item: dict, role: dict, prior_reviews: list[dict] | None) -> dict:
            return make_review(item, role)

        long_item = dict(self.item)
        long_item["item_id"] = "rc1-insight-01-negative-aspects-product-efficacy-general-effect"
        directory = tempfile.mkdtemp()
        try:
            output_root = Path(directory) / ("long-output-" + "x" * 150)
            manifest = run_workflow(
                [long_item], self.config, output_root, fake_review
            )
            result_path = _io_safe_path(
                output_root
                / manifest["run_id"]
                / "reviews"
                / f"{long_item['item_id']}.mechanical_screen.json"
            )
            self.assertGreater(len(str(result_path)), 260)
            self.assertTrue(result_path.is_file())
            self.assertEqual(manifest["status"], "completed")
        finally:
            shutil.rmtree(_io_safe_path(Path(directory)), ignore_errors=True)

    def test_failed_stage_is_persisted_and_resume_skips_successes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            first_calls: list[str] = []
            observed_manifest_statuses: list[str] = []

            def flaky_review(
                item: dict, role: dict, prior_reviews: list[dict] | None
            ) -> dict:
                first_calls.append(role["stage"])
                manifest_path = next(output_root.iterdir()) / "run_manifest.json"
                observed_manifest_statuses.append(
                    json.loads(manifest_path.read_text(encoding="utf-8"))["status"]
                )
                if role["stage"] == "semantic_review":
                    raise RuntimeError("simulated upstream failure")
                return make_review(item, role)

            failed = run_workflow(
                [self.item], self.config, output_root, flaky_review
            )
            run_dir = output_root / failed["run_id"]
            summary = json.loads(
                (run_dir / "summary.jsonl").read_text(encoding="utf-8")
            )
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(summary["status"], "ai_pre_review_failed")
            self.assertEqual(summary["failed_stages"], ["semantic_review"])
            self.assertEqual(set(summary["completed_stages"]), {
                "mechanical_screen", "risk_review",
            })
            self.assertTrue(all(status == "running" for status in observed_manifest_statuses))
            self.assertEqual(len(list((run_dir / "errors").glob("*.json"))), 1)

            resumed_calls: list[str] = []

            def resumed_review(
                item: dict, role: dict, prior_reviews: list[dict] | None
            ) -> dict:
                resumed_calls.append(role["stage"])
                return make_review(item, role)

            completed = run_workflow(
                [self.item], self.config, output_root, resumed_review,
                resume_run_id=failed["run_id"],
            )
            resumed_summary = json.loads(
                (run_dir / "summary.jsonl").read_text(encoding="utf-8")
            )
            self.assertEqual(resumed_calls, ["semantic_review"])
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["resume_count"], 1)
            self.assertEqual(resumed_summary["status"], "external_review_pending")
            self.assertFalse(list(run_dir.rglob("*.tmp")))

            changed_item = json.loads(json.dumps(self.item))
            changed_item["candidate"]["resume_probe"] = True
            mismatch_calls: list[str] = []

            def must_not_run(
                item: dict, role: dict, prior_reviews: list[dict] | None
            ) -> dict:
                mismatch_calls.append(role["stage"])
                return make_review(item, role)

            with self.assertRaisesRegex(ValueError, "input_sha256"):
                run_workflow(
                    [changed_item], self.config, output_root, must_not_run,
                    resume_run_id=failed["run_id"],
                )
            self.assertEqual(mismatch_calls, [])

    def test_error_record_persists_root_cause_chain(self) -> None:
        def wrapped_failure(
            item: dict, role: dict, prior_reviews: list[dict] | None
        ) -> dict:
            if role["stage"] == "mechanical_screen":
                try:
                    raise ValueError("provider returned HTTP 503")
                except ValueError as cause:
                    raise RuntimeError("bounded retries exhausted") from cause
            return make_review(item, role)

        with tempfile.TemporaryDirectory() as directory:
            manifest = run_workflow(
                [self.item], self.config, Path(directory), wrapped_failure
            )
            error_path = next(
                (Path(directory) / manifest["run_id"] / "errors").glob("*.json")
            )
            record = json.loads(error_path.read_text(encoding="utf-8"))
        self.assertEqual(record["error_type"], "RuntimeError")
        self.assertEqual(record["root_cause_type"], "ValueError")
        self.assertEqual(record["root_cause_message"], "provider returned HTTP 503")
        self.assertEqual(len(record["error_chain"]), 2)

    def test_stage_circuit_breaker_skips_later_items(self) -> None:
        items = []
        for index in range(4):
            item = json.loads(json.dumps(self.item))
            item["item_id"] = f"{self.item['item_id']}-circuit-{index}"
            items.append(item)
        calls: list[tuple[str, str]] = []

        def failing_mechanical(
            item: dict, role: dict, prior_reviews: list[dict] | None
        ) -> dict:
            calls.append((item["item_id"], role["stage"]))
            if role["stage"] == "mechanical_screen":
                raise RuntimeError("route unavailable")
            return make_review(item, role)

        with tempfile.TemporaryDirectory() as directory:
            manifest = run_workflow(
                items, self.config, Path(directory), failing_mechanical,
                stage_failure_circuit_breaker=2,
            )
            run_dir = Path(directory) / manifest["run_id"]
            error_records = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (run_dir / "errors").glob("*.json")
            ]
        mechanical_calls = [call for call in calls if call[1] == "mechanical_screen"]
        self.assertEqual(len(mechanical_calls), 2)
        self.assertEqual(
            manifest["stage_failure_circuit_breaker"]["open_stages"],
            ["mechanical_screen"],
        )
        self.assertEqual(
            sum(record["error_type"] == "StageCircuitOpen" for record in error_records),
            2,
        )

    def test_new_run_carries_only_compatible_seeded_stages(self) -> None:
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 12),
        )

        def runtime_for(config: dict) -> dict:
            reviewer = OpenAIReviewer(
                budget=BudgetController(
                    max_api_calls=1, max_total_tokens=100000,
                    max_cost_usd="1", pricing=pricing,
                ),
                max_output_tokens=100,
                client=SimpleNamespace(responses=SimpleNamespace()),
                sdk_version="9.9.9-test",
            )
            return reviewer.build_runtime_identity(config)

        source_runtime = runtime_for(self.config)

        def source_review(
            item: dict, role: dict, prior_reviews: list[dict] | None
        ) -> dict:
            return make_audited_review(item, role, source_runtime)

        nano_config = json.loads(json.dumps(self.config))
        next(
            role for role in nano_config["roles"]
            if role["stage"] == "mechanical_screen"
        )["model"] = "gpt-5.4-nano-2026-03-17"
        target_runtime = runtime_for(nano_config)
        target_calls: list[str] = []

        def target_review(
            item: dict, role: dict, prior_reviews: list[dict] | None
        ) -> dict:
            target_calls.append(role["stage"])
            return make_audited_review(item, role, target_runtime)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = run_workflow(
                [self.item], self.config, root, source_review,
                runtime_identity=source_runtime,
            )
            source_dir = root / source["run_id"]
            target = run_workflow(
                [self.item], nano_config, root, target_review,
                runtime_identity=target_runtime,
                seed_run_dir=source_dir,
                seed_stages=("semantic_review", "risk_review"),
            )
            target_dir = root / target["run_id"]
            carried = json.loads(
                (target_dir / "reviews" / (
                    f"{self.item['item_id']}.semantic_review.json"
                )).read_text(encoding="utf-8")
            )
            resumed_calls: list[str] = []
            resumed = run_workflow(
                [self.item], nano_config, root,
                lambda item, role, prior: resumed_calls.append(role["stage"]),
                runtime_identity=target_runtime,
                resume_run_id=target["run_id"],
            )
        self.assertEqual(target_calls, ["mechanical_screen"])
        self.assertEqual(target["seed"]["carried_review_count"], 2)
        self.assertIn("carry_forward", carried["_audit"])
        self.assertEqual(resumed_calls, [])
        self.assertEqual(resumed["status"], "completed")

    def test_seed_skips_changed_item_hashes_and_reruns_only_those_stages(self) -> None:
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 12),
        )
        reviewer = OpenAIReviewer(
            budget=BudgetController(
                max_api_calls=1, max_total_tokens=100000,
                max_cost_usd="1", pricing=pricing,
            ),
            max_output_tokens=100,
            client=SimpleNamespace(responses=SimpleNamespace()),
            sdk_version="9.9.9-test",
        )
        runtime = reviewer.build_runtime_identity(self.config)
        unchanged = json.loads(json.dumps(self.item))
        changed_source = json.loads(json.dumps(self.item))
        changed_source["item_id"] = f"{self.item['item_id']}-changed"
        changed_target = json.loads(json.dumps(changed_source))
        changed_target["candidate"]["prediction"]["sentiment"] = "positive"

        def audited(
            item: dict, role: dict, prior_reviews: list[dict] | None
        ) -> dict:
            return make_audited_review(item, role, runtime)

        target_calls: list[tuple[str, str]] = []

        def target_review(
            item: dict, role: dict, prior_reviews: list[dict] | None
        ) -> dict:
            target_calls.append((item["item_id"], role["stage"]))
            return make_audited_review(item, role, runtime)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = run_workflow(
                [unchanged, changed_source], self.config, root, audited,
                runtime_identity=runtime,
            )
            target = run_workflow(
                [unchanged, changed_target], self.config, root, target_review,
                runtime_identity=runtime,
                seed_run_dir=root / source["run_id"],
                seed_stages=PRIMARY_STAGES,
            )

        self.assertEqual(target["seed"]["eligible_review_count"], 6)
        self.assertEqual(target["seed"]["carried_review_count"], 3)
        self.assertEqual(target["seed"]["skipped_incompatible_review_count"], 3)
        self.assertEqual(
            target["seed"]["skipped_incompatible_items"],
            [changed_target["item_id"]],
        )
        self.assertCountEqual(
            target_calls,
            [(changed_target["item_id"], stage) for stage in PRIMARY_STAGES],
        )

    def test_seed_carries_only_exact_context_adjudications(self) -> None:
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 12),
        )
        runtime = OpenAIReviewer(
            budget=BudgetController(
                max_api_calls=1, max_total_tokens=100000,
                max_cost_usd="1", pricing=pricing,
            ),
            max_output_tokens=100,
            client=SimpleNamespace(responses=SimpleNamespace()),
            sdk_version="9.9.9-test",
        ).build_runtime_identity(self.config)
        unchanged = json.loads(json.dumps(self.item))
        changed_source = json.loads(json.dumps(self.item))
        changed_source["item_id"] = f"{self.item['item_id']}-adjudicated"
        changed_target = json.loads(json.dumps(changed_source))
        changed_target["candidate"]["prediction"]["sentiment"] = "positive"

        def disagreement(
            item: dict, role: dict, prior_reviews: list[dict] | None
        ) -> dict:
            decision = "revise" if role["stage"] == "semantic_review" else "pass"
            return make_audited_review(
                item, role, runtime, decision=decision
            )

        target_calls: list[tuple[str, str]] = []

        def target_review(
            item: dict, role: dict, prior_reviews: list[dict] | None
        ) -> dict:
            target_calls.append((item["item_id"], role["stage"]))
            return disagreement(item, role, prior_reviews)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = run_workflow(
                [unchanged, changed_source], self.config, root, disagreement,
                runtime_identity=runtime,
            )
            target = run_workflow(
                [unchanged, changed_target], self.config, root, target_review,
                runtime_identity=runtime,
                seed_run_dir=root / source["run_id"],
                seed_stages=REQUIRED_STAGES,
            )

        self.assertEqual(target["status"], "completed")
        self.assertEqual(target["seed"]["eligible_review_count"], 8)
        self.assertEqual(target["seed"]["carried_review_count"], 4)
        self.assertEqual(target["seed"]["skipped_incompatible_review_count"], 4)
        self.assertCountEqual(
            target_calls,
            [(changed_target["item_id"], stage) for stage in REQUIRED_STAGES],
        )

    def test_single_stage_smoke_does_not_run_adjudication(self) -> None:
        runtime = OpenAIReviewer(
            budget=BudgetController(
                max_api_calls=1, max_total_tokens=100000, max_cost_usd="1",
                pricing=load_pricing_config(
                    ROOT / "config" / "ai_review_pricing.json",
                    today=dt.date(2026, 8, 12),
                ),
            ),
            max_output_tokens=100,
            client=SimpleNamespace(responses=SimpleNamespace()),
            sdk_version="9.9.9-test",
        ).build_runtime_identity(self.config)
        calls: list[str] = []

        def smoke_review(
            item: dict, role: dict, prior_reviews: list[dict] | None
        ) -> dict:
            calls.append(role["stage"])
            return make_audited_review(item, role, runtime, decision="revise")

        with tempfile.TemporaryDirectory() as directory:
            manifest = run_stage_smoke(
                [self.item], self.config, Path(directory), smoke_review,
                "mechanical_screen", runtime_identity=runtime,
            )
        self.assertEqual(calls, ["mechanical_screen"])
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(manifest["run_kind"], "single_stage_compatibility_smoke")

    def test_deferred_adjudication_completes_primary_stages_without_calling_sol(self) -> None:
        calls: list[str] = []

        def review(
            item: dict, role: dict, prior_reviews: list[dict] | None
        ) -> dict:
            calls.append(role["stage"])
            decision = "revise" if role["stage"] == "mechanical_screen" else "pass"
            return make_review(item, role, decision=decision)

        with tempfile.TemporaryDirectory() as directory:
            manifest = run_workflow(
                [self.item], self.config, Path(directory), review,
                defer_adjudication=True,
            )
            summary = load_jsonl(
                Path(directory) / manifest["run_id"] / "summary.jsonl"
            )[0]

        self.assertEqual(set(calls), set(PRIMARY_STAGES))
        self.assertNotIn("adjudication", calls)
        self.assertEqual(manifest["status"], "adjudication_pending")
        self.assertEqual(manifest["primary_review_completed_item_count"], 1)
        self.assertEqual(manifest["adjudication_pending_item_count"], 1)
        self.assertEqual(summary["status"], "adjudication_pending")
        self.assertIsNone(summary["decision"])

    def test_resume_rebinds_adjudication_when_external_context_changes(self) -> None:
        external_role = next(iter(external_role_map(self.config).values()))
        external = make_review(self.item, external_role, decision="revise")
        external["findings"] = [{
            "category": "evidence_boundary",
            "severity": "high",
            "claim": "The delivery claim needs owner review.",
            "evidence_quote": "arrived three days late",
            "reference_id": "source_review",
            "evidence_path": "/references/0/content",
            "evidence_start": 37,
            "evidence_end": 60,
            "recommendation": "Keep the conclusion scoped to this review.",
        }]

        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)

            def disagreeing_review(
                item: dict, role: dict, prior_reviews: list[dict] | None
            ) -> dict:
                decision = "revise" if role["stage"] == "semantic_review" else "pass"
                return make_review(item, role, decision=decision)

            first = run_workflow(
                [self.item], self.config, output_root, disagreeing_review
            )
            resumed_calls: list[str] = []

            def resume_review(
                item: dict, role: dict, prior_reviews: list[dict] | None
            ) -> dict:
                resumed_calls.append(role["stage"])
                return make_review(item, role)

            second = run_workflow(
                [self.item], self.config, output_root, resume_review,
                external_reviews=[external], resume_run_id=first["run_id"],
            )
            run_dir = output_root / second["run_id"]
            self.assertEqual(resumed_calls, ["adjudication"])
            self.assertEqual(len(list((run_dir / "reviews" / "history").glob("*.json"))), 1)
            adjudication = json.loads(
                (run_dir / "reviews" / f"{self.item['item_id']}.adjudication.json")
                .read_text(encoding="utf-8")
            )
            self.assertIn("adjudication_context_sha256", adjudication["_audit"])

            changed_external = json.loads(json.dumps(external))
            changed_external["summary"] = "A conflicting replacement result."
            mismatch_calls: list[str] = []

            def must_not_run(
                item: dict, role: dict, prior_reviews: list[dict] | None
            ) -> dict:
                mismatch_calls.append(role["stage"])
                return make_review(item, role)

            with self.assertRaisesRegex(ValueError, "external review differs"):
                run_workflow(
                    [self.item], self.config, output_root, must_not_run,
                    external_reviews=[changed_external],
                    resume_run_id=first["run_id"],
                )
            self.assertEqual(mismatch_calls, [])

    def test_mixed_item_outcomes_finish_run_as_partial(self) -> None:
        second_item = json.loads(json.dumps(self.item))
        second_item["item_id"] = f"{self.item['item_id']}-second"

        def mixed_review(
            item: dict, role: dict, prior_reviews: list[dict] | None
        ) -> dict:
            if item["item_id"] == self.item["item_id"] and role["stage"] == "risk_review":
                raise RuntimeError("simulated item-specific failure")
            return make_review(item, role)

        with tempfile.TemporaryDirectory() as directory:
            manifest = run_workflow(
                [self.item, second_item], self.config, Path(directory), mixed_review
            )
            run_dir = Path(directory) / manifest["run_id"]
            summaries = [
                json.loads(line) for line in
                (run_dir / "summary.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(manifest["status"], "partial")
            self.assertEqual(manifest["completed_item_count"], 1)
            self.assertEqual(manifest["failed_item_count"], 1)
            self.assertEqual(
                {summary["status"] for summary in summaries},
                {"ai_pre_review_failed", "external_review_pending"},
            )

    def test_validate_only_cli_initializes_empty_external_results(self) -> None:
        completed = subprocess.run(
            [
                sys.executable, "tools/ai_review_workflow.py",
                "--config", "config/ai_review_roles.json",
                "--input", "data/sample/ai_review_input.demo.jsonl",
                "--validate-only",
            ],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["external_reviews_validated"], 0)
        self.assertEqual(result["privacy_scan"]["finding_count"], 0)

    def test_max_items_selects_matching_review_from_full_external_jsonl(self) -> None:
        second = json.loads(json.dumps(self.item))
        second["item_id"] = "demo-crossborder-second"
        role = next(iter(external_role_map(self.config).values()))
        reviews = [make_review(self.item, role), make_review(second, role)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.jsonl"
            result_path = root / "external.jsonl"
            input_path.write_text(
                "".join(json.dumps(item) + "\n" for item in [self.item, second]),
                encoding="utf-8",
            )
            result_path.write_text(
                "".join(json.dumps(review) + "\n" for review in reviews),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable, "tools/ai_review_workflow.py",
                    "--config", "config/ai_review_roles.json",
                    "--input", str(input_path),
                    "--external-review", str(result_path),
                    "--max-items", "1", "--validate-only",
                ],
                cwd=ROOT, capture_output=True, text=True, check=True,
            )
        result = json.loads(completed.stdout)
        self.assertEqual(result["item_count"], 1)
        self.assertEqual(result["external_reviews_validated"], 1)

    def test_budget_controller_enforces_each_hard_limit_before_reserving(self) -> None:
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 9),
        )
        calls = BudgetController(
            max_api_calls=1, max_total_tokens=10000,
            max_cost_usd="10", pricing=pricing,
        )
        reservation = calls.reserve(
            model="gpt-5.6-luna", estimated_input_tokens=100,
            max_output_tokens=100,
        )
        calls.settle(reservation, {"input_tokens": 50, "output_tokens": 25})
        with self.assertRaisesRegex(BudgetExceeded, "max API calls"):
            calls.reserve(
                model="gpt-5.6-luna", estimated_input_tokens=100,
                max_output_tokens=100,
            )

        tokens = BudgetController(
            max_api_calls=2, max_total_tokens=199,
            max_cost_usd="10", pricing=pricing,
        )
        with self.assertRaisesRegex(BudgetExceeded, "max total tokens"):
            tokens.reserve(
                model="gpt-5.6-luna", estimated_input_tokens=100,
                max_output_tokens=100,
            )
        self.assertEqual(tokens.snapshot()["usage"]["api_calls_used"], 0)

        cost = BudgetController(
            max_api_calls=2, max_total_tokens=1000,
            max_cost_usd="0.00013", pricing=pricing,
        )
        with self.assertRaisesRegex(BudgetExceeded, "max cost USD"):
            cost.reserve(
                model="gpt-5.6-luna", estimated_input_tokens=100,
                max_output_tokens=100,
            )
        self.assertEqual(cost.snapshot()["usage"]["api_calls_used"], 0)

    def test_missing_usage_and_interrupted_reservation_are_never_free(self) -> None:
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 9),
        )
        budget = BudgetController(
            max_api_calls=3, max_total_tokens=1000,
            max_cost_usd="1", pricing=pricing,
        )
        reservation = budget.reserve(
            model="gpt-5.6-luna", estimated_input_tokens=100,
            max_output_tokens=100,
        )
        budget.settle(reservation, None)
        usage = budget.snapshot()["usage"]
        self.assertEqual(usage["tokens_committed"], 200)
        self.assertEqual(usage["unverified_calls"], 1)

        interrupted = BudgetController(
            max_api_calls=3, max_total_tokens=1000,
            max_cost_usd="1", pricing=pricing,
        )
        interrupted.reserve(
            model="gpt-5.6-luna", estimated_input_tokens=120,
            max_output_tokens=80,
        )
        restored = BudgetController(
            max_api_calls=3, max_total_tokens=1000,
            max_cost_usd="1", pricing=pricing,
            initial_snapshot=interrupted.snapshot(),
        )
        restored_usage = restored.snapshot()["usage"]
        self.assertEqual(restored_usage["tokens_committed"], 200)
        self.assertEqual(restored_usage["tokens_reserved"], 0)
        self.assertEqual(restored_usage["unverified_calls"], 1)

    def test_reported_output_over_per_call_cap_is_rejected(self) -> None:
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 9),
        )
        budget = BudgetController(
            max_api_calls=1, max_total_tokens=1000,
            max_cost_usd="1", pricing=pricing,
        )
        reservation = budget.reserve(
            model="gpt-5.6-luna", estimated_input_tokens=100,
            max_output_tokens=100,
        )
        with self.assertRaisesRegex(BudgetExceeded, "reserved hard limit"):
            budget.settle(
                reservation, {"input_tokens": 50, "output_tokens": 101}
            )

    def test_long_context_price_multiplier_is_reserved(self) -> None:
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 9),
        )
        budget = BudgetController(
            max_api_calls=1, max_total_tokens=300000,
            max_cost_usd="2", pricing=pricing,
        )
        budget.reserve(
            model="gpt-5.6-terra", estimated_input_tokens=272001,
            max_output_tokens=100,
        )
        reserved = Decimal(budget.snapshot()["usage"]["cost_reserved_usd"])
        self.assertEqual(reserved, Decimal("1.089804"))

    def test_openai_reviewer_forwards_output_cap_and_settles_usage(self) -> None:
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 9),
        )
        budget = BudgetController(
            max_api_calls=1, max_total_tokens=20000,
            max_cost_usd="1", pricing=pricing,
        )
        role = self.stage_map["mechanical_screen"]
        expected = make_review(self.item, role)
        captured: dict = {}

        def create(**kwargs: object) -> object:
            captured.update(kwargs)
            usage = SimpleNamespace(
                model_dump=lambda: {"input_tokens": 100, "output_tokens": 50}
            )
            return SimpleNamespace(
                id="fake-response", usage=usage,
                model="gpt-5.6-luna-2026-08-01",
                service_tier="default", system_fingerprint="fp-test",
                created_at=1786200000,
                output_text=json.dumps(expected),
            )

        client = SimpleNamespace(
            base_url="https://private-proxy.example/v1",
            responses=SimpleNamespace(create=create),
        )
        reviewer = OpenAIReviewer(
            budget=budget, max_output_tokens=321, retries=0, client=client,
            sdk_version="9.9.9-test",
        )
        review = reviewer.review(self.item, role)
        self.assertEqual(captured["max_output_tokens"], 321)
        self.assertFalse(captured["store"])
        self.assertEqual(captured["service_tier"], "default")
        self.assertEqual(review["_audit"]["response_id"], "fake-response")
        self.assertEqual(
            review["_audit"]["response_model"], "gpt-5.6-luna-2026-08-01"
        )
        self.assertEqual(
            review["_audit"]["model_resolution_status"],
            "provider_returned_different_or_resolved_model",
        )
        self.assertEqual(review["_audit"]["sdk"]["version"], "9.9.9-test")
        self.assertEqual(review["_audit"]["endpoint"]["category"], "custom_or_proxy")
        self.assertNotIn("private-proxy.example", json.dumps(review))
        self.assertEqual(len(review["_audit"]["request_messages_sha256"]), 64)
        runtime_identity = reviewer.build_runtime_identity(self.config)
        self.assertEqual(runtime_identity["sdk"]["version"], "9.9.9-test")
        self.assertEqual(len(runtime_identity["runner_sha256"]), 64)
        self.assertEqual(len(runtime_identity["review_schema_sha256"]), 64)
        self.assertNotIn("private-proxy.example", json.dumps(runtime_identity))
        official = OpenAIReviewer(
            budget=budget, max_output_tokens=321, retries=0,
            client=SimpleNamespace(
                base_url="https://api.openai.com/v1/", responses=SimpleNamespace()
            ),
            sdk_version="9.9.9-test",
        ).build_runtime_identity(self.config)
        self.assertEqual(official["endpoint"]["category"], "official_openai")
        usage = budget.snapshot()["usage"]
        self.assertEqual(usage["tokens_committed"], 150)
        self.assertEqual(usage["tokens_reserved"], 0)

    def test_openai_reviewer_disables_sdk_level_retries(self) -> None:
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 9),
        )
        budget = BudgetController(
            max_api_calls=1, max_total_tokens=20000,
            max_cost_usd="1", pricing=pricing,
        )
        captured: dict = {}
        fake_openai = ModuleType("openai")

        class FakeOpenAI:
            def __init__(self, **kwargs: object) -> None:
                captured.update(kwargs)
                self.responses = SimpleNamespace()

        fake_openai.OpenAI = FakeOpenAI
        with mock.patch.dict(sys.modules, {"openai": fake_openai}):
            OpenAIReviewer(budget=budget, max_output_tokens=321)
        self.assertEqual(captured, {"max_retries": 0})

    def test_pricing_snapshot_must_be_fresh(self) -> None:
        with self.assertRaisesRegex(ValueError, "snapshot is 31 days old"):
            load_pricing_config(
                ROOT / "config" / "ai_review_pricing.json",
                max_age_days=30, today=dt.date(2026, 9, 9),
            )

    def test_execute_rejects_small_budget_before_api_key_check(self) -> None:
        environment = dict(os.environ)
        environment.pop("OPENAI_API_KEY", None)
        completed = subprocess.run(
            [
                sys.executable, "tools/ai_review_workflow.py",
                "--config", "config/ai_review_roles.json",
                "--input", "data/sample/ai_review_input.demo.jsonl",
                "--execute", "--max-api-calls", "1",
                "--max-total-tokens", "100000",
                "--max-output-tokens", "100",
                "--max-cost-usd", "100",
                "--data-classification", "public",
                "--api-data-controls", "default",
                "--confirm-api-data-policy",
            ],
            cwd=ROOT, capture_output=True, text=True, env=environment,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("minimum initial review plan", completed.stderr)
        self.assertNotIn("OPENAI_API_KEY is required", completed.stderr)

    def test_run_manifest_records_budget_and_pricing_hash(self) -> None:
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 9),
        )
        budget = BudgetController(
            max_api_calls=3, max_total_tokens=10000,
            max_cost_usd="1", pricing=pricing,
        )

        def fake_review(item: dict, role: dict, prior_reviews: list[dict] | None) -> dict:
            return make_review(item, role)

        with tempfile.TemporaryDirectory() as directory:
            manifest = run_workflow(
                [self.item], self.config, Path(directory), fake_review,
                budget_controller=budget, budget_plan={"test_plan": True},
            )
        self.assertEqual(manifest["budget"]["limits"]["max_api_calls"], 3)
        self.assertTrue(manifest["budget"]["plan"]["test_plan"])
        self.assertEqual(len(manifest["budget"]["pricing"]["pricing_sha256"]), 64)

    def test_parallel_review_reservations_are_atomically_persisted(self) -> None:
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 9),
        )
        budget = BudgetController(
            max_api_calls=3, max_total_tokens=50000,
            max_cost_usd="10", pricing=pricing,
        )

        def create(**kwargs: object) -> object:
            payload = json.loads(kwargs["input"][1]["content"])
            identity = payload["required_identity"]
            review = {
                **identity,
                "decision": "pass",
                "confidence": 0.8,
                "scores": {dimension: 5 for dimension in SCORE_DIMENSIONS},
                "findings": [],
                "summary": "Concurrent fake review.",
                "limitations": ["AI pre-review is not human evaluation."],
            }
            usage = SimpleNamespace(
                model_dump=lambda: {"input_tokens": 100, "output_tokens": 50}
            )
            return SimpleNamespace(
                id=f"fake-{identity['role_id']}", usage=usage,
                model=identity["model"], service_tier="default",
                system_fingerprint="fp-concurrent", created_at=1786200000,
                output_text=json.dumps(review),
            )

        reviewer = OpenAIReviewer(
            budget=budget, max_output_tokens=100, retries=0,
            client=SimpleNamespace(responses=SimpleNamespace(create=create)),
            sdk_version="9.9.9-test",
        )
        runtime_identity = reviewer.build_runtime_identity(self.config)
        with tempfile.TemporaryDirectory() as directory:
            manifest = run_workflow(
                [self.item], self.config, Path(directory), reviewer.review,
                budget_controller=budget, budget_plan={"concurrency_test": True},
                runtime_identity=runtime_identity,
            )
            persisted = json.loads(
                (Path(directory) / manifest["run_id"] / "run_manifest.json")
                .read_text(encoding="utf-8")
            )
        self.assertEqual(persisted["status"], "completed")
        self.assertEqual(persisted["budget"]["usage"]["api_calls_used"], 3)
        self.assertEqual(persisted["budget"]["usage"]["tokens_committed"], 450)
        self.assertEqual(persisted["budget"]["usage"]["outstanding_reservations"], 0)
        self.assertEqual(
            persisted["runtime_identity"]["observed"]["response_count"], 3
        )
        self.assertEqual(
            persisted["runtime_identity"]["observed"]["response_service_tiers"],
            ["default"],
        )

    def test_missing_response_model_fails_closed(self) -> None:
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 9),
        )
        budget = BudgetController(
            max_api_calls=1, max_total_tokens=20000,
            max_cost_usd="1", pricing=pricing,
        )
        role = self.stage_map["mechanical_screen"]
        expected = make_review(self.item, role)

        def create(**kwargs: object) -> object:
            usage = SimpleNamespace(
                model_dump=lambda: {"input_tokens": 100, "output_tokens": 50}
            )
            return SimpleNamespace(
                id="missing-model", usage=usage, output_text=json.dumps(expected)
            )

        reviewer = OpenAIReviewer(
            budget=budget, max_output_tokens=100, retries=0,
            client=SimpleNamespace(responses=SimpleNamespace(create=create)),
            sdk_version="9.9.9-test",
        )
        with self.assertRaisesRegex(RuntimeError, "failed after 1 attempts") as raised:
            reviewer.review(self.item, role)
        self.assertIn("actual model identity", str(raised.exception.__cause__))

    def test_authentication_error_is_not_retried(self) -> None:
        pricing = load_pricing_config(
            ROOT / "config" / "ai_review_pricing.json",
            today=dt.date(2026, 8, 12),
        )
        budget = BudgetController(
            max_api_calls=3, max_total_tokens=100000,
            max_cost_usd="1", pricing=pricing,
        )
        calls = 0

        class AuthenticationFailure(RuntimeError):
            status_code = 401
            code = "INVALID_API_KEY"

        def create(**kwargs: object) -> object:
            nonlocal calls
            calls += 1
            raise AuthenticationFailure("invalid API key")

        reviewer = OpenAIReviewer(
            budget=budget, max_output_tokens=100, retries=2,
            client=SimpleNamespace(responses=SimpleNamespace(create=create)),
            sdk_version="9.9.9-test",
        )
        with self.assertRaisesRegex(RuntimeError, "failed after 1 attempts"):
            reviewer.review(self.item, self.stage_map["mechanical_screen"])
        self.assertEqual(calls, 1)
        self.assertEqual(budget.snapshot()["usage"]["api_calls_used"], 1)

    def test_resume_rejects_changed_runtime_identity_before_review_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = run_workflow(
                [self.item], self.config, root,
                lambda item, role, prior: make_review(item, role),
            )
            path = root / manifest["run_id"] / "run_manifest.json"
            persisted = json.loads(path.read_text(encoding="utf-8"))
            persisted["runtime_identity"] = {"context_sha256": "0" * 64}
            path.write_text(
                json.dumps(persisted, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            pricing = load_pricing_config(
                ROOT / "config" / "ai_review_pricing.json",
                today=dt.date(2026, 8, 9),
            )
            reviewer = OpenAIReviewer(
                budget=BudgetController(
                    max_api_calls=1, max_total_tokens=1000,
                    max_cost_usd="1", pricing=pricing,
                ),
                max_output_tokens=100, retries=0,
                client=SimpleNamespace(responses=SimpleNamespace()),
                sdk_version="9.9.9-test",
            )
            runtime_identity = reviewer.build_runtime_identity(self.config)
            called = False

            def must_not_run(item: dict, role: dict, prior: list[dict] | None) -> dict:
                nonlocal called
                called = True
                return make_review(item, role)

            with self.assertRaisesRegex(ValueError, "runtime identity does not match"):
                run_workflow(
                    [self.item], self.config, root, must_not_run,
                    resume_run_id=manifest["run_id"],
                    runtime_identity=runtime_identity,
                )
            self.assertFalse(called)

    def test_privacy_scan_blocks_secrets_even_when_redaction_is_enabled(self) -> None:
        exposed = json.loads(json.dumps(self.item))
        synthetic_secret = "sk-" + "proj-" + "abcdefghijklmnop1234567890"
        exposed["candidate"]["notes"] = "OPENAI_API_KEY=" + synthetic_secret
        _, findings = scan_sensitive_data(exposed, redact=True)
        self.assertTrue(any(finding["action"] == "blocked" for finding in findings))
        serialized = json.dumps(findings)
        self.assertNotIn("sk-proj-", serialized)
        with self.assertRaisesRegex(ValueError, "privacy scan blocked") as raised:
            prepare_api_payload(
                [exposed], [], classification="internal",
                api_data_controls="default", confirm_api_data_policy=True,
                redact_sensitive_data=True, output=Path(".private/ai_review"),
            )
        self.assertNotIn("sk-proj-", str(raised.exception))

    def test_privacy_redaction_is_deterministic_and_does_not_mutate_source(self) -> None:
        personal = json.loads(json.dumps(self.item))
        personal["candidate"]["contact"] = "Email analyst@example.com or 555-123-4567."
        sanitized_a, _, privacy_a = prepare_api_payload(
            [personal], [], classification="internal",
            api_data_controls="default", confirm_api_data_policy=True,
            redact_sensitive_data=True, output=Path(".private/ai_review"),
        )
        sanitized_b, _, privacy_b = prepare_api_payload(
            [personal], [], classification="internal",
            api_data_controls="default", confirm_api_data_policy=True,
            redact_sensitive_data=True, output=Path(".private/ai_review"),
        )
        self.assertIn("analyst@example.com", personal["candidate"]["contact"])
        self.assertEqual(sanitized_a, sanitized_b)
        self.assertEqual(privacy_a["context_sha256"], privacy_b["context_sha256"])
        redacted = sanitized_a[0]["candidate"]["contact"]
        self.assertNotIn("analyst@example.com", redacted)
        self.assertNotIn("555-123-4567", redacted)
        self.assertIn("<REDACTED:email>", redacted)
        self.assertEqual(privacy_a["scan"]["redaction_count"], 2)

    def test_privacy_classification_and_confirmation_fail_closed(self) -> None:
        common = {
            "items": [self.item], "external_reviews": [],
            "redact_sensitive_data": False,
            "output": Path(".private/ai_review"),
        }
        with self.assertRaisesRegex(ValueError, "confirm-api-data-policy"):
            prepare_api_payload(
                classification="internal", api_data_controls="default",
                confirm_api_data_policy=False, **common,
            )
        with self.assertRaisesRegex(ValueError, "restricted data"):
            prepare_api_payload(
                classification="restricted", api_data_controls="zero_data_retention",
                confirm_api_data_policy=True, **common,
            )
        with self.assertRaisesRegex(ValueError, "confidential data requires"):
            prepare_api_payload(
                classification="confidential", api_data_controls="default",
                confirm_api_data_policy=True, **common,
            )

    def test_non_private_output_requires_public_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "review-output"
            with self.assertRaisesRegex(ValueError, "under a .private directory"):
                validate_private_output(output, "internal")
            with self.assertRaisesRegex(ValueError, "only for public data"):
                validate_private_output(
                    output, "internal", allow_non_private=True
                )
            result = validate_private_output(
                output, "public", allow_non_private=True
            )
            self.assertEqual(result["status"], "public_override_non_private_path")

    def test_privacy_context_is_persisted_and_bound_to_resume(self) -> None:
        def fake_review(item: dict, role: dict, prior_reviews: list[dict] | None) -> dict:
            return make_review(item, role)

        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / ".private" / "ai_review"
            items, external, privacy = prepare_api_payload(
                [self.item], [], classification="internal",
                api_data_controls="default", confirm_api_data_policy=True,
                redact_sensitive_data=False, output=output_root,
            )
            first = run_workflow(
                items, self.config, output_root, fake_review,
                external_reviews=external, privacy_context=privacy,
            )
            manifest_path = output_root / first["run_id"] / "run_manifest.json"
            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["privacy"]["data_classification"], "internal")
            self.assertEqual(len(persisted["privacy"]["context_sha256"]), 64)

            _, _, changed_privacy = prepare_api_payload(
                [self.item], [], classification="public",
                api_data_controls="default", confirm_api_data_policy=True,
                redact_sensitive_data=False, output=output_root,
            )
            calls: list[str] = []

            def must_not_run(
                item: dict, role: dict, prior_reviews: list[dict] | None
            ) -> dict:
                calls.append(role["stage"])
                return make_review(item, role)

            with self.assertRaisesRegex(ValueError, "privacy context"):
                run_workflow(
                    items, self.config, output_root, must_not_run,
                    resume_run_id=first["run_id"],
                    privacy_context=changed_privacy,
                )
            self.assertEqual(calls, [])

    def test_privacy_context_allows_later_external_review_import(self) -> None:
        external_role = next(iter(external_role_map(self.config).values()))
        external = make_review(self.item, external_role)
        common = {
            "classification": "internal", "api_data_controls": "default",
            "confirm_api_data_policy": True, "redact_sensitive_data": False,
            "output": Path(".private/ai_review"),
        }
        _, _, before = prepare_api_payload([self.item], [], **common)
        _, _, after = prepare_api_payload([self.item], [external], **common)
        self.assertEqual(before["context_sha256"], after["context_sha256"])
        self.assertNotEqual(
            before["source_external_reviews_sha256"],
            after["source_external_reviews_sha256"],
        )

    def test_execute_requires_privacy_confirmation_before_api_key(self) -> None:
        environment = dict(os.environ)
        environment.pop("OPENAI_API_KEY", None)
        completed = subprocess.run(
            [
                sys.executable, "tools/ai_review_workflow.py",
                "--config", "config/ai_review_roles.json",
                "--input", "data/sample/ai_review_input.demo.jsonl",
                "--execute", "--max-items", "1",
                "--max-api-calls", "12", "--max-total-tokens", "60000",
                "--max-output-tokens", "4096", "--max-cost-usd", "2",
                "--data-classification", "internal",
                "--api-data-controls", "default",
            ],
            cwd=ROOT, capture_output=True, text=True, env=environment,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--confirm-api-data-policy", completed.stderr)
        self.assertNotIn("OPENAI_API_KEY is required", completed.stderr)

    def test_external_packet_privacy_gate_redacts_but_does_not_authorize_transfer(self) -> None:
        personal = json.loads(json.dumps(self.item))
        personal["candidate"]["email"] = "owner@example.com"
        with self.assertRaisesRegex(ValueError, "data-classification"):
            prepare_external_packet_payload(
                [personal], classification="", redact_sensitive_data=True,
                output=Path(".private/packets"),
            )
        sanitized, privacy = prepare_external_packet_payload(
            [personal], classification="internal", redact_sensitive_data=True,
            output=Path(".private/packets"),
        )
        self.assertEqual(sanitized[0]["candidate"]["email"], "<REDACTED:email>")
        self.assertFalse(privacy["external_transfer_authorized"])


if __name__ == "__main__":
    unittest.main()
