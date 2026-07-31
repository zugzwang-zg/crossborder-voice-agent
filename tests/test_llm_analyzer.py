"""Unit and integration tests for the analysis pipeline."""

from __future__ import annotations

import csv
import http.client
import json
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.llm_analyzer import (
    MockResponsesProvider,
    OpenAIResponsesProvider,
    ProviderError,
    ProviderResult,
    estimate_cost,
    responses_endpoint,
    review_source_text,
    run_pipeline,
)
from src.schema import (
    AnalysisValidationError,
    normalize_analysis,
    validate_analysis,
)
from src.schema import ANALYSIS_SCHEMA, API_ANALYSIS_SCHEMA


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_config() -> dict:
    return {
        "model": "gpt-5.6-sol",
        "prompt_version": "v9_consistency_guard",
        "reasoning_effort": "low",
        "text_verbosity": "low",
        "max_output_tokens": 2500,
        "max_retries": 2,
        "retry_base_seconds": 0,
        "store": False,
    }


def find_retry_id() -> str:
    for index in range(1000):
        candidate = f"retry_{index}"
        if MockResponsesProvider.should_fail_first(candidate):
            return candidate
    raise AssertionError("Could not find deterministic retry test id")


class UsageRetryProvider(MockResponsesProvider):
    """Test double that charges usage on a validation-failed first attempt."""

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.prompts: list[str] = []

    def analyze(
        self, review: dict[str, str], prompt: str, attempt: int
    ) -> ProviderResult:
        self.prompts.append(prompt)
        result = super().analyze(review, prompt, attempt=2)
        if attempt == 1:
            result.analysis["sentiment_evidence"] = ["not in source"]
        result.metadata["usage"] = {
            "input_tokens": 100 + attempt,
            "cached_input_tokens": 0,
            "output_tokens": 10 + attempt,
            "total_tokens": 110 + 2 * attempt,
        }
        return result


class SemanticNoiseProvider(MockResponsesProvider):
    """Test double that emits a removable unsupported optional label."""

    def analyze(
        self, review: dict[str, str], prompt: str, attempt: int
    ) -> ProviderResult:
        result = super().analyze(review, prompt, attempt=2)
        result.analysis["issue_types"] = [
            {
                "issue": "texture_problem",
                "evidence": review["review_title"],
            }
        ]
        return result


class FatalProvider(MockResponsesProvider):
    """Test double for a systemic non-retryable relay rejection."""

    name = "openai"

    def analyze(
        self, review: dict[str, str], prompt: str, attempt: int
    ) -> ProviderResult:
        raise ProviderError(
            "OpenAI HTTP 400: systemic rejection",
            retryable=False,
            status_code=400,
        )


class FailingResponse:
    """Context-managed response double that fails while reading its body."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def __enter__(self) -> "FailingResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        raise self.error


class ProviderNetworkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            **test_config(),
            "base_url": "https://api.example",
            "timeout_seconds": 90,
        }
        self.provider = OpenAIResponsesProvider(self.config, "test-key")
        self.review = {
            "review_id": "network_1",
            "language": "en",
            "stars": "1",
            "review_title": "Bad",
            "review_body": "It failed.",
        }

    def test_interrupted_response_body_is_retryable(self) -> None:
        errors = [
            http.client.IncompleteRead(b"partial", 100),
            http.client.RemoteDisconnected("remote closed connection"),
            ConnectionResetError("connection reset"),
            ConnectionAbortedError("connection aborted"),
            BrokenPipeError("broken pipe"),
            ssl.SSLError("TLS connection interrupted"),
        ]
        for error in errors:
            with self.subTest(error_type=type(error).__name__):
                with patch(
                    "src.llm_analyzer.urllib.request.urlopen",
                    return_value=FailingResponse(error),
                ):
                    with self.assertRaises(ProviderError) as caught:
                        self.provider.analyze(
                            self.review, "test prompt", attempt=1
                        )
                self.assertTrue(caught.exception.retryable)
                self.assertIn("OpenAI network error", str(caught.exception))


class SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.review = {
            "review_id": "ok_1",
            "language": "en",
            "stars": "5",
            "review_title": "Works well",
            "review_body": "I like it.",
        }
        self.provider = MockResponsesProvider(test_config())

    def test_valid_mock_payload_passes(self) -> None:
        payload = self.provider.analyze(
            self.review, "unused", attempt=2
        ).analysis
        validated = validate_analysis(
            payload,
            source_text=review_source_text(self.review),
            expected_review_id="ok_1",
            expected_language="en",
        )
        self.assertEqual(validated["sentiment_evidence"], ["Works well"])

    def test_hallucinated_evidence_is_rejected(self) -> None:
        payload = self.provider.analyze(
            self.review, "unused", attempt=2
        ).analysis
        payload["sentiment_evidence"] = ["text not present in review"]
        with self.assertRaises(AnalysisValidationError):
            validate_analysis(
                payload,
                source_text=review_source_text(self.review),
                expected_review_id="ok_1",
                expected_language="en",
            )

    def test_separate_mixed_evidence_and_aspect_evidence_arrays(self) -> None:
        payload = self.provider.analyze(
            self.review, "unused", attempt=2
        ).analysis
        payload["sentiment"] = "mixed"
        payload["sentiment_evidence"] = ["Works well", "I like it."]
        payload["aspects"] = [
            {
                "aspect": "product.efficacy.general_effect",
                "opinion": "It works well.",
                "polarity": "positive",
                "evidence": ["Works well"],
            }
        ]
        validate_analysis(
            payload,
            source_text=review_source_text(self.review),
            expected_review_id="ok_1",
            expected_language="en",
        )

    def test_mixed_sentiment_requires_two_evidence_snippets(self) -> None:
        payload = self.provider.analyze(
            self.review, "unused", attempt=2
        ).analysis
        payload["sentiment"] = "mixed"
        with self.assertRaises(AnalysisValidationError):
            validate_analysis(
                payload,
                source_text=review_source_text(self.review),
                expected_review_id="ok_1",
                expected_language="en",
            )

    def test_responses_endpoint_uses_station_base_url(self) -> None:
        self.assertEqual(
            responses_endpoint({"base_url": "https://api.aijws.com/"}),
            "https://api.aijws.com/responses",
        )
        self.assertEqual(
            responses_endpoint(
                {
                    "base_url": "https://ignored.example",
                    "endpoint": "https://proxy.example/v1/responses",
                }
            ),
            "https://proxy.example/v1/responses",
        )

    def test_standard_cost_uses_config_pricing(self) -> None:
        cost = estimate_cost(
            {
                "input_tokens": 44893,
                "cached_input_tokens": 17664,
                "output_tokens": 3508,
                "total_tokens": 48401,
            },
            "openai",
            {
                "pricing_usd_per_1m": {
                    "input": 1.0,
                    "cached_input": 0.1,
                    "output": 6.0,
                }
            },
        )
        self.assertEqual(cost, 0.0500434)

    def test_api_schema_removes_descriptions_only(self) -> None:
        serialized_full = json.dumps(ANALYSIS_SCHEMA)
        serialized_api = json.dumps(API_ANALYSIS_SCHEMA)
        self.assertIn('"description"', serialized_full)
        self.assertNotIn('"description"', serialized_api)
        self.assertEqual(
            API_ANALYSIS_SCHEMA["required"], ANALYSIS_SCHEMA["required"]
        )

    def test_no_repurchase_requires_explicit_repeat_purchase_evidence(
        self,
    ) -> None:
        review = {
            **self.review,
            "review_title": "Never will recommend to anyone",
            "review_body": "Very disappointing.",
        }
        payload = self.provider.analyze(
            review, "unused", attempt=2
        ).analysis
        payload["speech_acts"] = [
            {
                "speech_act": "rejection_no_repurchase",
                "evidence": "Never will recommend to anyone",
            }
        ]
        with self.assertRaises(AnalysisValidationError):
            validate_analysis(
                payload,
                source_text=review_source_text(review),
                expected_review_id="ok_1",
                expected_language="en",
            )

        normalized, events = normalize_analysis(
            payload,
            source_text=review_source_text(review),
        )
        self.assertEqual(normalized["speech_acts"], [])
        self.assertTrue(
            any(
                event["operation"] == "drop_unsupported_label"
                and event["label"] == "rejection_no_repurchase"
                for event in events
            )
        )
        validate_analysis(
            normalized,
            source_text=review_source_text(review),
            expected_review_id="ok_1",
            expected_language="en",
        )

        review["review_body"] = "I will not buy this again."
        payload["speech_acts"][0]["evidence"] = "I will not buy this again"
        validate_analysis(
            payload,
            source_text=review_source_text(review),
            expected_review_id="ok_1",
            expected_language="en",
        )

    def test_duplicate_presence_labels_are_normalized_with_audit_event(
        self,
    ) -> None:
        payload = self.provider.analyze(
            self.review, "unused", attempt=2
        ).analysis
        payload["speech_acts"] = [
            {"speech_act": "praise", "evidence": "Works well"},
            {"speech_act": "praise", "evidence": "I like it"},
        ]
        normalized, events = normalize_analysis(payload)
        self.assertEqual(len(normalized["speech_acts"]), 1)
        self.assertEqual(events[0]["operation"], "drop_duplicate_label")
        validate_analysis(
            normalized,
            source_text=review_source_text(self.review),
            expected_review_id="ok_1",
            expected_language="en",
        )

    def test_unsupported_optional_labels_are_dropped_with_audit(self) -> None:
        review = {
            **self.review,
            "review_title": "Inspected only",
            "review_body": (
                "The packaging was tin. The cap is not a dispenser. "
                "The cream caused a headache. As a pro groomer."
            ),
        }
        payload = self.provider.analyze(
            review, "unused", attempt=2
        ).analysis
        payload["aspects"] = [
            {
                "aspect": "packaging.seal_leak_protection",
                "opinion": "Tin packaging protects against leaks.",
                "polarity": "neutral",
                "evidence": ["The packaging was tin"],
            }
        ]
        payload["issue_types"] = [
            {
                "issue": "broken_dispenser",
                "evidence": "The cap is not a dispenser",
            }
        ]
        payload["purchase_motivations"] = [
            {
                "motivation": "professional_need",
                "evidence": "As a pro groomer",
            }
        ]
        payload["speech_acts"] = [
            {
                "speech_act": "warning",
                "evidence": "The cream caused a headache",
            }
        ]
        normalized, events = normalize_analysis(
            payload,
            source_text=review_source_text(review),
        )
        self.assertEqual(normalized["aspects"], [])
        self.assertEqual(normalized["issue_types"], [])
        self.assertEqual(normalized["purchase_motivations"], [])
        self.assertEqual(normalized["speech_acts"], [])
        self.assertEqual(
            sum(
                event["operation"] == "drop_unsupported_label"
                for event in events
            ),
            4,
        )

    def test_logically_forced_values_are_normalized(self) -> None:
        review = {
            **self.review,
            "review_title": "Gift delivery",
            "review_body": (
                "It arrived in good condition and the print was nice."
            ),
        }
        payload = self.provider.analyze(
            review, "unused", attempt=2
        ).analysis
        payload["sentiment"] = "positive"
        payload["sentiment_evidence"] = [
            "arrived in good condition",
            "the print was nice",
        ]
        payload["aspects"] = [
            {
                "aspect": "packaging.arrival_condition",
                "opinion": "It arrived in good condition.",
                "polarity": "positive",
                "evidence": ["arrived in good condition"],
            },
            {
                "aspect": "product.appearance.design_look",
                "opinion": "The print was nice.",
                "polarity": "negative",
                "evidence": ["the print was nice"],
            },
        ]
        payload["experience_status"] = "delivery_only"
        normalized, events = normalize_analysis(
            payload,
            source_text=review_source_text(review),
        )
        self.assertEqual(normalized["sentiment"], "mixed")
        self.assertEqual(normalized["experience_status"], "unclear")
        changed_fields = {
            event["field"]
            for event in events
            if event["operation"] == "set_logically_forced_value"
        }
        self.assertEqual(
            changed_fields, {"sentiment", "experience_status"}
        )

    def test_compound_action_without_compound_evidence_is_dropped(
        self,
    ) -> None:
        payload = self.provider.analyze(
            self.review, "unused", attempt=2
        ).analysis
        payload["recommended_actions"] = [
            {
                "audience": "product",
                "action": "Improve adhesion and reduce irritation.",
                "evidence": "Works well",
            }
        ]
        normalized, events = normalize_analysis(
            payload,
            source_text=review_source_text(self.review),
        )
        self.assertEqual(normalized["recommended_actions"], [])
        self.assertTrue(
            any(
                event["operation"] == "drop_unsupported_action"
                for event in events
            )
        )

    def test_targeted_semantic_boundary_errors_are_rejected(self) -> None:
        cases = [
            {
                "body": "But its okay for what I'm doing.",
                "field": "aspects",
                "value": [
                    {
                        "aspect": (
                            "product.suitability.skill_professional_fit"
                        ),
                        "opinion": "It suits the task.",
                        "polarity": "positive",
                        "evidence": ["its okay for what I'm doing"],
                    }
                ],
            },
            {
                "body": "Given as a gift.",
                "field": "aspects",
                "value": [
                    {
                        "aspect": "product.usability.handling_portability",
                        "opinion": "It is portable.",
                        "polarity": "positive",
                        "evidence": ["Given as a gift"],
                    }
                ],
            },
            {
                "body": "No hace espuma.",
                "field": "aspects",
                "value": [
                    {
                        "aspect": "product.efficacy.cleansing",
                        "opinion": "No limpia.",
                        "polarity": "negative",
                        "evidence": ["No hace espuma"],
                    }
                ],
            },
            {
                "body": "No hace espuma.",
                "field": "issue_types",
                "value": [
                    {
                        "issue": "insufficient_effect",
                        "evidence": "No hace espuma",
                    }
                ],
            },
            {
                "body": "Me enreda muchísimo el pelo.",
                "field": "aspects",
                "value": [
                    {
                        "aspect": "product.suitability.skin_hair_fit",
                        "opinion": "No es adecuado para el pelo.",
                        "polarity": "negative",
                        "evidence": ["Me enreda muchísimo el pelo"],
                    }
                ],
            },
            {
                "body": "Se hace difícil aplicarlo.",
                "field": "aspects",
                "value": [
                    {
                        "aspect": "product.usability.application_control",
                        "opinion": "Es difícil de aplicar.",
                        "polarity": "negative",
                        "evidence": ["difícil aplicarlo"],
                    }
                ],
            },
            {
                "body": "Me enreda muchísimo el pelo.",
                "field": "issue_types",
                "value": [
                    {
                        "issue": "texture_problem",
                        "evidence": "Me enreda muchísimo el pelo",
                    }
                ],
            },
            {
                "body": "el pelo no queda con más brillo.",
                "field": "aspects",
                "value": [
                    {
                        "aspect": (
                            "product.efficacy.brightening_whitening"
                        ),
                        "opinion": "No aporta brillo al pelo.",
                        "polarity": "negative",
                        "evidence": ["el pelo no queda con más brillo"],
                    }
                ],
            },
            {
                "body": "Lo uso para las cicatrices.",
                "field": "usage_scenarios",
                "value": [
                    {
                        "scenario": "sensitive_area",
                        "evidence": "para las cicatrices",
                    }
                ],
            },
            {
                "body": "I'll update with photos soon.",
                "field": "speech_acts",
                "value": [
                    {
                        "speech_act": "suggestion",
                        "evidence": "I'll update with photos soon",
                    }
                ],
            },
            {
                "body": "The cream caused a headache.",
                "field": "speech_acts",
                "value": [
                    {
                        "speech_act": "warning",
                        "evidence": "The cream caused a headache",
                    }
                ],
            },
            {
                "body": "As a pro groomer.",
                "field": "purchase_motivations",
                "value": [
                    {
                        "motivation": "professional_need",
                        "evidence": "As a pro groomer",
                    }
                ],
            },
            {
                "body": "The cap is not a dispenser.",
                "field": "issue_types",
                "value": [
                    {
                        "issue": "broken_dispenser",
                        "evidence": "The cap is not a dispenser",
                    }
                ],
            },
            {
                "body": "The packaging was tin.",
                "field": "aspects",
                "value": [
                    {
                        "aspect": "product.quality.material_build",
                        "opinion": "The product uses tin.",
                        "polarity": "neutral",
                        "evidence": ["The packaging was tin"],
                    }
                ],
            },
            {
                "body": "The tube has a vinyl sticker on it.",
                "field": "aspects",
                "value": [
                    {
                        "aspect": "packaging.arrival_condition",
                        "opinion": "The item arrived in poor condition.",
                        "polarity": "negative",
                        "evidence": ["The tube has a vinyl sticker on it"],
                    }
                ],
            },
            {
                "body": (
                    "I may have to have them trimmed to suit my face."
                ),
                "field": "aspects",
                "value": [
                    {
                        "aspect": "product.suitability.body_area_fit",
                        "opinion": "They fit the face.",
                        "polarity": "neutral",
                        "evidence": ["suit my face"],
                    }
                ],
            },
        ]
        for index, case in enumerate(cases):
            with self.subTest(case=index):
                review = {
                    **self.review,
                    "review_title": "Review",
                    "review_body": case["body"],
                }
                payload = self.provider.analyze(
                    review, "unused", attempt=2
                ).analysis
                payload[case["field"]] = case["value"]
                with self.assertRaises(AnalysisValidationError):
                    validate_analysis(
                        payload,
                        source_text=review_source_text(review),
                        expected_review_id="ok_1",
                        expected_language="en",
                    )

    def test_supported_fit_application_and_texture_boundaries_pass(
        self,
    ) -> None:
        review = {
            **self.review,
            "review_title": "Specific product details",
            "review_body": (
                "Great for oily skin. It squirts like a water gun. "
                "The cream is too thick and sticky."
            ),
        }
        payload = self.provider.analyze(
            review, "unused", attempt=2
        ).analysis
        payload["sentiment"] = "mixed"
        payload["sentiment_evidence"] = [
            "Great for oily skin",
            "It squirts like a water gun",
        ]
        payload["aspects"] = [
            {
                "aspect": "product.suitability.skin_hair_fit",
                "opinion": "Suitable for oily skin.",
                "polarity": "positive",
                "evidence": ["Great for oily skin"],
            },
            {
                "aspect": "product.usability.application_control",
                "opinion": "The spray is difficult to control.",
                "polarity": "negative",
                "evidence": ["It squirts like a water gun"],
            },
        ]
        payload["issue_types"] = [
            {
                "issue": "texture_problem",
                "evidence": "too thick and sticky",
            }
        ]
        validate_analysis(
            payload,
            source_text=review_source_text(review),
            expected_review_id="ok_1",
            expected_language="en",
        )

    def test_sentiment_and_aspect_polarities_must_be_consistent(
        self,
    ) -> None:
        review = {
            **self.review,
            "review_title": "Cute but synthetic",
            "review_body": "It is cute, but it feels synthetic.",
        }
        payload = self.provider.analyze(
            review, "unused", attempt=2
        ).analysis
        payload["sentiment"] = "positive"
        payload["aspects"] = [
            {
                "aspect": "product.appearance.design_look",
                "opinion": "It is cute.",
                "polarity": "positive",
                "evidence": ["It is cute"],
            },
            {
                "aspect": "product.sensory.texture_consistency",
                "opinion": "It feels synthetic.",
                "polarity": "negative",
                "evidence": ["it feels synthetic"],
            },
        ]
        with self.assertRaises(AnalysisValidationError):
            validate_analysis(
                payload,
                source_text=review_source_text(review),
                expected_review_id="ok_1",
                expected_language="en",
            )

    def test_uncertain_sentiment_rejects_explicit_praise(self) -> None:
        payload = self.provider.analyze(
            self.review, "unused", attempt=2
        ).analysis
        payload["sentiment"] = "uncertain"
        payload["speech_acts"] = [
            {"speech_act": "praise", "evidence": "Works well"}
        ]
        with self.assertRaises(AnalysisValidationError):
            validate_analysis(
                payload,
                source_text=review_source_text(self.review),
                expected_review_id="ok_1",
                expected_language="en",
            )

    def test_supported_consistency_boundaries_pass(self) -> None:
        review = {
            **self.review,
            "review_title": "Professional purchase",
            "review_body": (
                "I bought this for my clients. The pump is broken. "
                "Do not buy. It arrived in good condition. "
                "The tool itself is sturdy."
            ),
        }
        payload = self.provider.analyze(
            review, "unused", attempt=2
        ).analysis
        payload["aspects"] = [
            {
                "aspect": "packaging.arrival_condition",
                "opinion": "It arrived in good condition.",
                "polarity": "positive",
                "evidence": ["arrived in good condition"],
            },
            {
                "aspect": "product.quality.material_build",
                "opinion": "The tool is sturdy.",
                "polarity": "positive",
                "evidence": ["The tool itself is sturdy"],
            },
        ]
        payload["issue_types"] = [
            {"issue": "broken_dispenser", "evidence": "The pump is broken"}
        ]
        payload["purchase_motivations"] = [
            {
                "motivation": "professional_need",
                "evidence": "I bought this for my clients",
            }
        ]
        payload["speech_acts"] = [
            {"speech_act": "warning", "evidence": "Do not buy"}
        ]
        validate_analysis(
            payload,
            source_text=review_source_text(review),
            expected_review_id="ok_1",
            expected_language="en",
        )


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_path = self.root / "input.csv"
        self.output_path = self.root / "output.jsonl"
        self.error_path = self.root / "errors.jsonl"
        self.run_log_path = self.root / "run.json"
        self.prompt_path = (
            PROJECT_ROOT / "prompts" / "v9_consistency_guard_prompt.md"
        )
        retry_id = find_retry_id()
        rows = [
            {
                "review_id": retry_id,
                "language": "en",
                "stars": "1",
                "review_title": "Bad pump",
                "review_body": "It broke.",
            },
            {
                "review_id": "normal_1",
                "language": "es",
                "stars": "5",
                "review_title": "Muy bueno",
                "review_body": "Me encanta.",
            },
        ]
        with self.input_path.open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_once(self, *, resume: bool) -> dict:
        config = test_config()
        return run_pipeline(
            provider=MockResponsesProvider(config),
            config=config,
            input_path=self.input_path,
            output_path=self.output_path,
            error_path=self.error_path,
            run_log_path=self.run_log_path,
            prompt_path=self.prompt_path,
            resume=resume,
            max_retries=2,
        )

    def test_retry_and_resume(self) -> None:
        first = self.run_once(resume=False)
        self.assertEqual(first["successful_records"], 2)
        self.assertEqual(first["failed_records"], 0)
        self.assertGreaterEqual(first["retry_count"], 1)
        self.assertEqual(first["parse_success_rate"], 1.0)

        second = self.run_once(resume=True)
        self.assertEqual(second["processed_records"], 0)
        self.assertEqual(second["skipped_existing_records"], 2)
        lines = [
            json.loads(line)
            for line in self.output_path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(lines), 2)
        self.assertEqual(len({line["review_id"] for line in lines}), 2)

        self.error_path.write_text(
            json.dumps(
                {
                    "review_id": "normal_1",
                    "error_type": "old",
                    "error": "resolved",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        third = self.run_once(resume=True)
        self.assertEqual(third["unresolved_error_records"], 0)
        self.assertEqual(third["resolved_error_records_removed"], 1)
        self.assertEqual(self.error_path.read_text(encoding="utf-8"), "")

    def test_failed_validation_usage_and_retry_feedback_are_recorded(
        self,
    ) -> None:
        config = test_config()
        provider = UsageRetryProvider(config)
        run = run_pipeline(
            provider=provider,
            config=config,
            input_path=self.input_path,
            output_path=self.output_path,
            error_path=self.error_path,
            run_log_path=self.run_log_path,
            prompt_path=self.prompt_path,
            resume=False,
            max_retries=2,
        )
        self.assertEqual(run["successful_records"], 2)
        self.assertEqual(run["attempted_provider_calls"], 4)
        self.assertEqual(run["usage"]["input_tokens"], 406)
        self.assertEqual(run["usage"]["output_tokens"], 46)
        self.assertEqual(len(provider.prompts), 4)
        self.assertEqual(
            sum("Retry correction" in prompt for prompt in provider.prompts),
            2,
        )
        records = [
            json.loads(line)
            for line in self.output_path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(records[0]["_run"]["attempt_events"]), 2)
        self.assertEqual(
            records[0]["_run"]["attempt_events"][0]["status"], "failed"
        )

    def test_semantic_normalization_avoids_paid_style_retries(self) -> None:
        config = test_config()
        run = run_pipeline(
            provider=SemanticNoiseProvider(config),
            config=config,
            input_path=self.input_path,
            output_path=self.output_path,
            error_path=self.error_path,
            run_log_path=self.run_log_path,
            prompt_path=self.prompt_path,
            resume=False,
            max_retries=2,
        )
        self.assertEqual(run["successful_records"], 2)
        self.assertEqual(run["attempted_provider_calls"], 2)
        self.assertEqual(run["retry_count"], 0)
        records = [
            json.loads(line)
            for line in self.output_path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertTrue(records[0]["_run"]["normalizations"])
        self.assertEqual(records[0]["analysis"]["issue_types"], [])

    def test_systemic_nonretryable_provider_errors_trigger_fail_fast(
        self,
    ) -> None:
        rows = [
            {
                "review_id": f"fatal_{index}",
                "language": "en",
                "stars": "1",
                "review_title": "Bad",
                "review_body": "It failed.",
            }
            for index in range(5)
        ]
        with self.input_path.open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        config = test_config()
        config["base_url"] = "https://api.example"
        run = run_pipeline(
            provider=FatalProvider(config),
            config=config,
            input_path=self.input_path,
            output_path=self.output_path,
            error_path=self.error_path,
            run_log_path=self.run_log_path,
            prompt_path=self.prompt_path,
            resume=False,
            max_retries=2,
        )
        self.assertEqual(run["status"], "aborted_fatal_provider_error")
        self.assertTrue(run["aborted_early"])
        self.assertEqual(run["attempted_provider_calls"], 3)
        self.assertEqual(run["failed_records"], 3)
        self.assertEqual(run["unprocessed_records"], 2)


if __name__ == "__main__":
    unittest.main()
