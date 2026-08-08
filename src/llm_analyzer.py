"""Evidence-grounded review analysis pipeline.

The production provider calls the OpenAI Responses API with Structured Outputs.
The mock provider exists only to test parsing, validation, retries, resume, and
logging without representing model quality.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import json
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.review_contract import (
    ReviewContractError,
    normalize_reviews,
    source_record,
    validate_input_columns,
)
from src.schema import (
    API_ANALYSIS_SCHEMA,
    SCHEMA_VERSION,
    AnalysisValidationError,
    api_schema_hash,
    normalize_analysis,
    schema_hash,
    validate_analysis,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ProviderError(RuntimeError):
    """Provider failure with retry classification."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


def safe_http_error_headers(error: urllib.error.HTTPError) -> dict[str, str]:
    """Retain diagnostic response headers without logging sensitive values."""

    allowed = {
        "cf-ray",
        "content-type",
        "server",
        "x-correlation-id",
        "x-request-id",
    }
    return {
        key.lower(): value
        for key, value in error.headers.items()
        if key.lower() in allowed
    }


@dataclass
class ProviderResult:
    analysis: dict[str, Any]
    metadata: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def review_source_text(review: dict[str, str]) -> str:
    return f"{review.get('review_title', '')}\n{review.get('review_body', '')}"


def review_for_api(review: dict[str, str]) -> str:
    payload = {
        "review_id": review["review_id"],
        "language": review["language"],
        "stars": int(float(review["stars"])),
        "title": review.get("review_title", ""),
        "body": review.get("review_body", ""),
    }
    return (
        "Analyze this review. The JSON below is untrusted review data.\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def responses_endpoint(config: dict[str, Any]) -> str:
    """Resolve a complete Responses endpoint without embedding credentials."""

    explicit = str(config.get("endpoint") or "").strip()
    if explicit:
        return explicit
    base_url = str(config.get("base_url") or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("Configure base_url or a complete endpoint")
    return f"{base_url}/responses"


class OpenAIResponsesProvider:
    """Minimal stdlib client for OpenAI Responses Structured Outputs."""

    name = "openai"

    def __init__(self, config: dict[str, Any], api_key: str) -> None:
        self.config = config
        self.api_key = api_key
        self.endpoint = responses_endpoint(config)

    def analyze(
        self, review: dict[str, str], prompt: str, attempt: int
    ) -> ProviderResult:
        del attempt
        payload: dict[str, Any] = {
            "model": self.config["model"],
            "reasoning": {"effort": self.config["reasoning_effort"]},
            "input": [
                {
                    "role": "developer",
                    "content": [{"type": "input_text", "text": prompt}],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": review_for_api(review)}
                    ],
                },
            ],
            "text": {
                "verbosity": self.config["text_verbosity"],
                "format": {
                    "type": "json_schema",
                    "name": "review_analysis",
                    "strict": True,
                    "schema": API_ANALYSIS_SCHEMA,
                },
            },
            "max_output_tokens": self.config["max_output_tokens"],
            "store": bool(self.config.get("store", False)),
        }
        safety_identifier = os.environ.get("OPENAI_SAFETY_IDENTIFIER", "").strip()
        if safety_identifier:
            payload["safety_identifier"] = safety_identifier

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Connection": "close",
            },
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.config["timeout_seconds"]
            ) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            retryable = error.code in {408, 409, 429} or error.code >= 500
            headers = safe_http_error_headers(error)
            diagnostic = f" headers={json.dumps(headers, sort_keys=True)}"
            raise ProviderError(
                f"OpenAI HTTP {error.code}: {raw[:500]}{diagnostic}",
                retryable=retryable,
                status_code=error.code,
            ) from error
        except (
            urllib.error.URLError,
            TimeoutError,
            http.client.IncompleteRead,
            http.client.RemoteDisconnected,
            ConnectionResetError,
            ConnectionAbortedError,
            BrokenPipeError,
            ssl.SSLError,
        ) as error:
            raise ProviderError(
                f"OpenAI network error: {error}",
                retryable=True,
            ) from error

        try:
            data = json.loads(response_body)
        except json.JSONDecodeError as error:
            raise ProviderError(
                "OpenAI response was not valid JSON",
                retryable=True,
            ) from error

        if data.get("status") == "incomplete":
            reason = data.get("incomplete_details", {}).get("reason", "unknown")
            raise ProviderError(
                f"OpenAI response incomplete: {reason}",
                retryable=True,
            )

        text_parts: list[str] = []
        for output_item in data.get("output", []):
            if output_item.get("type") != "message":
                continue
            for content in output_item.get("content", []):
                if content.get("type") == "refusal":
                    raise ProviderError(
                        f"OpenAI refusal: {content.get('refusal', '')}",
                        retryable=False,
                    )
                if content.get("type") == "output_text":
                    text_parts.append(content.get("text", ""))
        if not text_parts and isinstance(data.get("output_text"), str):
            text_parts.append(data["output_text"])
        if not text_parts:
            raise ProviderError(
                "OpenAI response contained no output_text",
                retryable=True,
            )
        try:
            analysis = json.loads("".join(text_parts))
        except json.JSONDecodeError as error:
            raise ProviderError(
                f"Structured output could not be parsed: {error}",
                retryable=True,
            ) from error

        return ProviderResult(
            analysis=analysis,
            metadata={
                "provider": self.name,
                "model": data.get("model", self.config["model"]),
                "response_id": data.get("id"),
                "usage": normalize_usage(data.get("usage", {})),
            },
        )


class MockResponsesProvider:
    """Deterministic infrastructure test double, not an AI classifier."""

    name = "mock"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @staticmethod
    def should_fail_first(review_id: str) -> bool:
        return int(hashlib.sha256(review_id.encode()).hexdigest()[:8], 16) % 4 == 0

    def analyze(
        self, review: dict[str, str], prompt: str, attempt: int
    ) -> ProviderResult:
        del prompt
        stars = int(float(review["stars"]))
        if stars >= 4:
            sentiment = "positive"
        elif stars <= 2:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        evidence = (
            review.get("review_title", "").strip()
            or review.get("review_body", "").strip()
        )
        if self.should_fail_first(review["review_id"]) and attempt == 1:
            evidence = "MOCK_INVALID_EVIDENCE_TO_EXERCISE_RETRY"

        analysis = {
            "review_id": review["review_id"],
            "language": review["language"],
            "sentiment": sentiment,
            "sentiment_intensity": 2 if stars in {1, 5} else 1,
            "sentiment_evidence": [evidence],
            "aspects": [],
            "issue_types": [],
            "usage_scenarios": [],
            "purchase_motivations": [],
            "expectation_gap": {
                "present": False,
                "type": "none",
                "evidence": [],
            },
            "speech_acts": [],
            "experience_status": "unclear",
            "star_text_alignment": "aligned",
            "recommended_actions": [],
            "confidence": 0.5,
            "ambiguous": False,
            "analysis_note": (
                "MOCK_PROVIDER: infrastructure test only; "
                "not a model prediction."
            ),
        }
        return ProviderResult(
            analysis=analysis,
            metadata={
                "provider": self.name,
                "model": "deterministic-mock-v1",
                "response_id": f"mock_{review['review_id']}_{attempt}",
                "usage": normalize_usage({}),
            },
        )


def normalize_usage(usage: dict[str, Any]) -> dict[str, int]:
    input_details = usage.get("input_tokens_details") or {}
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "cached_input_tokens": int(input_details.get("cached_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }


def add_usage(total: dict[str, int], current: dict[str, int]) -> None:
    for key in total:
        total[key] += int(current.get(key, 0))


def estimate_cost(
    usage: dict[str, int],
    provider_name: str,
    config: dict[str, Any],
) -> float | None:
    if provider_name == "mock":
        return 0.0
    names = {
        "input": "OPENAI_INPUT_PRICE_PER_1M_USD",
        "cached": "OPENAI_CACHED_INPUT_PRICE_PER_1M_USD",
        "output": "OPENAI_OUTPUT_PRICE_PER_1M_USD",
    }
    if all(os.environ.get(name, "").strip() for name in names.values()):
        input_price = float(os.environ[names["input"]])
        cached_price = float(os.environ[names["cached"]])
        output_price = float(os.environ[names["output"]])
    else:
        pricing = config.get("pricing_usd_per_1m") or {}
        if not all(key in pricing for key in ["input", "cached_input", "output"]):
            return None
        input_price = float(pricing["input"])
        cached_price = float(pricing["cached_input"])
        output_price = float(pricing["output"])
    uncached_input = max(
        0, usage["input_tokens"] - usage["cached_input_tokens"]
    )
    return round(
        (
            uncached_input * input_price
            + usage["cached_input_tokens"] * cached_price
            + usage["output_tokens"] * output_price
        )
        / 1_000_000,
        8,
    )


def read_completed_ids(output_path: Path) -> set[str]:
    completed: set[str] = set()
    if not output_path.exists():
        return completed
    with output_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                completed.add(record["review_id"])
            except (json.JSONDecodeError, KeyError) as error:
                raise RuntimeError(
                    f"Cannot resume: invalid JSONL at "
                    f"{output_path}:{line_number}"
                ) from error
    return completed


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def reconcile_error_file(
    error_path: Path,
    completed_ids: set[str],
) -> tuple[int, int]:
    """Keep only the latest unresolved error for each review."""

    if not error_path.exists():
        return 0, 0
    latest_by_id: dict[str, dict[str, Any]] = {}
    total_records = 0
    with error_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            total_records += 1
            try:
                record = json.loads(line)
                review_id = str(record["review_id"])
            except (json.JSONDecodeError, KeyError) as error:
                raise RuntimeError(
                    f"Invalid error JSONL at {error_path}:{line_number}"
                ) from error
            if review_id not in completed_ids:
                latest_by_id[review_id] = record
    with error_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in latest_by_id.values():
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return total_records - len(latest_by_id), len(latest_by_id)


def write_json(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_reviews(input_path: Path, limit: int | None) -> list[dict[str, str]]:
    with input_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        validate_input_columns(reader.fieldnames)
        try:
            reviews = normalize_reviews(reader)
        except ReviewContractError as error:
            raise ValueError(f"Invalid input review data: {error}") from error
    return reviews[:limit] if limit is not None else reviews


def build_blocked_log(
    *,
    config: dict[str, Any],
    input_path: Path,
    prompt_path: Path,
    run_log_path: Path,
) -> None:
    write_json(
        run_log_path,
        {
            "status": "blocked_missing_api_key",
            "provider": "openai",
            "model": config["model"],
            "base_url": config.get("base_url"),
            "responses_endpoint": responses_endpoint(config),
            "schema_version": SCHEMA_VERSION,
            "prompt_version": config["prompt_version"],
            "input_path": str(input_path),
            "prompt_path": str(prompt_path),
            "actual_api_calls": 0,
            "actual_cost_usd": 0.0,
            "message": (
                "OPENAI_API_KEY is not configured. No request was sent and "
                "no model predictions were created."
            ),
            "recorded_at": utc_now(),
        },
    )


def run_pipeline(
    *,
    provider: OpenAIResponsesProvider | MockResponsesProvider,
    config: dict[str, Any],
    input_path: Path,
    output_path: Path,
    error_path: Path,
    run_log_path: Path,
    prompt_path: Path,
    limit: int | None = None,
    resume: bool = True,
    max_retries: int | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    started_at = utc_now()
    prompt = prompt_path.read_text(encoding="utf-8")
    reviews = load_reviews(input_path, limit)
    completed_ids = read_completed_ids(output_path) if resume else set()
    if not resume:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("", encoding="utf-8")
        error_path.parent.mkdir(parents=True, exist_ok=True)
        error_path.write_text("", encoding="utf-8")
    elif not error_path.exists():
        error_path.parent.mkdir(parents=True, exist_ok=True)
        error_path.write_text("", encoding="utf-8")

    retries_allowed = (
        int(config["max_retries"]) if max_retries is None else max_retries
    )
    total_usage = normalize_usage({})
    success_count = 0
    failure_count = 0
    skipped_count = 0
    retry_count = 0
    attempted_calls = 0
    fatal_signature: tuple[int | None, str] | None = None
    consecutive_fatal_count = 0
    aborted_early = False
    abort_reason: str | None = None

    for review in reviews:
        review_id = review["review_id"]
        if review_id in completed_ids:
            skipped_count += 1
            continue

        last_error: Exception | None = None
        attempts_used = 0
        attempt_prompt = prompt
        record_usage = normalize_usage({})
        attempt_events: list[dict[str, Any]] = []
        record_started = time.perf_counter()
        for attempt in range(1, retries_allowed + 2):
            attempts_used = attempt
            attempted_calls += 1
            call_started = time.perf_counter()
            current_usage = normalize_usage({})
            current_normalizations: list[dict[str, Any]] = []
            try:
                result = provider.analyze(review, attempt_prompt, attempt)
                current_usage = result.metadata["usage"]
                add_usage(total_usage, result.metadata["usage"])
                add_usage(record_usage, result.metadata["usage"])
                source_text = review_source_text(review)
                normalized_payload, current_normalizations = (
                    normalize_analysis(
                        result.analysis,
                        source_text=source_text,
                    )
                )
                analysis = validate_analysis(
                    normalized_payload,
                    source_text=source_text,
                    expected_review_id=review_id,
                    expected_language=review["language"],
                )
                attempt_events.append(
                    {
                        "attempt": attempt,
                        "status": "success",
                        "usage": current_usage,
                        "normalizations": current_normalizations,
                        "latency_ms": round(
                            (time.perf_counter() - call_started) * 1000, 2
                        ),
                    }
                )
                record = {
                    "review_id": review_id,
                    "source": source_record(review),
                    "analysis": analysis,
                    "_run": {
                        **result.metadata,
                        "prompt_version": config["prompt_version"],
                        "schema_version": SCHEMA_VERSION,
                        "attempts": attempt,
                        "attempt_usage": record_usage,
                        "attempt_events": attempt_events,
                        "normalizations": current_normalizations,
                        "latency_ms": round(
                            (time.perf_counter() - call_started) * 1000, 2
                        ),
                        "record_latency_ms": round(
                            (time.perf_counter() - record_started) * 1000, 2
                        ),
                    },
                }
                append_jsonl(output_path, record)
                success_count += 1
                fatal_signature = None
                consecutive_fatal_count = 0
                last_error = None
                break
            except (AnalysisValidationError, ProviderError) as error:
                last_error = error
                if isinstance(error, AnalysisValidationError):
                    attempt_prompt = (
                        prompt
                        + "\n\n# Retry correction\n"
                        + "The previous result was rejected by the local "
                        + f"validator: {error}. Return a complete new object "
                        + "that fixes this exact error. Keep all evidence as "
                        + "separate exact contiguous source substrings and "
                        + "merge duplicate labels."
                    )
                retryable = (
                    True
                    if isinstance(error, AnalysisValidationError)
                    else error.retryable
                )
                attempt_events.append(
                    {
                        "attempt": attempt,
                        "status": "failed",
                        "error_type": type(error).__name__,
                        "error": str(error),
                        "retryable": retryable,
                        "usage": current_usage,
                        "normalizations": current_normalizations,
                        "latency_ms": round(
                            (time.perf_counter() - call_started) * 1000, 2
                        ),
                    }
                )
                if not retryable or attempt > retries_allowed:
                    break
                retry_count += 1
                if provider.name != "mock":
                    delay = (
                        float(config["retry_base_seconds"])
                        * (2 ** (attempt - 1))
                        + random.uniform(0, 0.25)
                    )
                    time.sleep(delay)

        if last_error is not None:
            failure_count += 1
            append_jsonl(
                error_path,
                {
                    "review_id": review_id,
                    "attempts": attempts_used,
                    "error_type": type(last_error).__name__,
                    "error": str(last_error),
                    "attempt_usage": record_usage,
                    "attempt_events": attempt_events,
                    "recorded_at": utc_now(),
                },
            )
            if (
                isinstance(last_error, ProviderError)
                and not last_error.retryable
            ):
                current_signature = (
                    last_error.status_code,
                    str(last_error),
                )
                if current_signature == fatal_signature:
                    consecutive_fatal_count += 1
                else:
                    fatal_signature = current_signature
                    consecutive_fatal_count = 1
                if consecutive_fatal_count >= 3:
                    aborted_early = True
                    abort_reason = (
                        "Stopped after 3 consecutive identical "
                        "non-retryable provider errors: "
                        f"{last_error}"
                    )
                    break
            else:
                fatal_signature = None
                consecutive_fatal_count = 0

    processed = success_count + failure_count
    unprocessed = max(len(reviews) - skipped_count - processed, 0)
    resolved_error_records_removed, unresolved_error_records = (
        reconcile_error_file(error_path, read_completed_ids(output_path))
    )
    parse_success_rate = success_count / processed if processed else None
    run_log = {
        "status": (
            "aborted_fatal_provider_error"
            if aborted_early
            else "completed"
            if failure_count == 0
            else "completed_with_errors"
        ),
        "provider": provider.name,
        "model": (
            config["model"]
            if provider.name == "openai"
            else "deterministic-mock-v1"
        ),
        "base_url": config.get("base_url"),
        "responses_endpoint": (
            responses_endpoint(config) if provider.name == "openai" else None
        ),
        "mock_disclaimer": (
            "Infrastructure test only; outputs are not model predictions."
            if provider.name == "mock"
            else None
        ),
        "schema_version": SCHEMA_VERSION,
        "schema_sha256": schema_hash(),
        "api_schema_sha256": api_schema_hash(),
        "prompt_version": config["prompt_version"],
        "prompt_path": str(prompt_path),
        "prompt_sha256": sha256_file(prompt_path),
        "input_path": str(input_path),
        "input_sha256": sha256_file(input_path),
        "output_path": str(output_path),
        "error_path": str(error_path),
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "requested_records": len(reviews),
        "processed_records": processed,
        "unprocessed_records": unprocessed,
        "skipped_existing_records": skipped_count,
        "successful_records": success_count,
        "failed_records": failure_count,
        "unresolved_error_records": unresolved_error_records,
        "resolved_error_records_removed": resolved_error_records_removed,
        "parse_success_rate": parse_success_rate,
        "retry_count": retry_count,
        "attempted_provider_calls": attempted_calls,
        "aborted_early": aborted_early,
        "abort_reason": abort_reason,
        "usage": total_usage,
        "estimated_cost_usd": estimate_cost(
            total_usage, provider.name, config
        ),
        "cost_note": (
            "Mock provider performs no paid API calls."
            if provider.name == "mock"
            else (
                "Standard model-list estimate from config or OPENAI_* price "
                "overrides; actual station group billing may differ."
            )
        ),
        "parameters": {
            "reasoning_effort": config["reasoning_effort"],
            "text_verbosity": config["text_verbosity"],
            "max_output_tokens": config["max_output_tokens"],
            "max_retries": retries_allowed,
            "store": bool(config.get("store", False)),
            "resume": resume,
        },
    }
    write_json(run_log_path, run_log)
    return run_log


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze reviews with strict structured outputs."
    )
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "config" / "analysis_config.json"),
    )
    parser.add_argument("--provider", choices=["openai", "mock"])
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--errors")
    parser.add_argument("--run-log")
    parser.add_argument("--prompt")
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--endpoint")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-retries", type=int)
    parser.add_argument("--no-resume", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = resolve_path(args.config)
    config = load_json(config_path)
    if args.provider:
        config["provider"] = args.provider
    if args.model:
        config["model"] = args.model
    elif os.environ.get("OPENAI_MODEL", "").strip():
        config["model"] = os.environ["OPENAI_MODEL"].strip()
    if args.base_url:
        config["base_url"] = args.base_url
        config.pop("endpoint", None)
    elif os.environ.get("OPENAI_BASE_URL", "").strip():
        config["base_url"] = os.environ["OPENAI_BASE_URL"].strip()
        config.pop("endpoint", None)
    if args.endpoint:
        config["endpoint"] = args.endpoint
    elif os.environ.get("OPENAI_RESPONSES_ENDPOINT", "").strip():
        config["endpoint"] = os.environ[
            "OPENAI_RESPONSES_ENDPOINT"
        ].strip()

    input_path = resolve_path(args.input or config["input_path"])
    output_path = resolve_path(args.output or config["output_path"])
    error_path = resolve_path(args.errors or config["error_path"])
    run_log_path = resolve_path(args.run_log or config["run_log_path"])
    prompt_path = resolve_path(args.prompt or config["prompt_path"])

    if config["provider"] == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            build_blocked_log(
                config=config,
                input_path=input_path,
                prompt_path=prompt_path,
                run_log_path=run_log_path,
            )
            print(
                "OPENAI_API_KEY is missing; no API request was sent. "
                f"Status: {run_log_path}",
                file=sys.stderr,
            )
            return 2
        provider: OpenAIResponsesProvider | MockResponsesProvider = (
            OpenAIResponsesProvider(config, api_key)
        )
    else:
        provider = MockResponsesProvider(config)

    run_log = run_pipeline(
        provider=provider,
        config=config,
        input_path=input_path,
        output_path=output_path,
        error_path=error_path,
        run_log_path=run_log_path,
        prompt_path=prompt_path,
        limit=args.limit,
        resume=not args.no_resume,
        max_retries=args.max_retries,
    )
    print(json.dumps(run_log, ensure_ascii=False, indent=2))
    return 0 if run_log["failed_records"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
