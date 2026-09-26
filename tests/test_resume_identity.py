"""Regression tests for stale-output reuse; no model calls or private data."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.llm_analyzer import MockResponsesProvider, run_pipeline


class ResumeIdentityTests(unittest.TestCase):
    def test_changed_experiment_is_rejected_without_touching_artifacts(self):
        for change in ("prompt_version", "prompt_text", "model", "reasoning_effort", "input", "schema", "legacy"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config = dict(model="mock-model", prompt_version="v1", reasoning_effort="low", text_verbosity="low", max_output_tokens=2500, max_retries=2, retry_base_seconds=0, store=False)
                input_path = root / "input.csv"
                with input_path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=["review_id", "language", "stars", "review_title", "review_body"])
                    writer.writeheader()
                    writer.writerow(dict(review_id="r1", language="en", stars=5, review_title="Good", review_body="Works well."))
                prompt = root / "prompt.md"
                prompt.write_text("First prompt", encoding="utf-8")
                kwargs = dict(config=config, input_path=input_path, output_path=root/"output.jsonl", error_path=root/"errors.jsonl", run_log_path=root/"run.json", prompt_path=prompt)
                run_pipeline(provider=MockResponsesProvider(config), resume=False, **kwargs)
                if change in ("prompt_version", "model", "reasoning_effort"):
                    config[change] = "changed"
                elif change == "prompt_text":
                    prompt.write_text("Second prompt", encoding="utf-8")
                elif change == "input":
                    input_path.write_text(input_path.read_text(encoding="utf-8").replace("Works well.", "Stopped working."), encoding="utf-8")
                elif change == "legacy":
                    record = json.loads(kwargs["output_path"].read_text(encoding="utf-8"))
                    del record["_run"]["fingerprint"]
                    kwargs["output_path"].write_text(json.dumps(record)+"\n", encoding="utf-8")
                artifacts = [kwargs[key] for key in ("output_path", "error_path", "run_log_path")]
                before = [path.read_bytes() for path in artifacts]
                provider = MockResponsesProvider(config)
                with patch.object(provider, "analyze", side_effect=AssertionError("Provider must not be called")):
                    if change == "schema":
                        with patch("src.llm_analyzer.schema_hash", return_value="new-schema"), self.assertRaisesRegex(RuntimeError, "fingerprint mismatch"):
                            run_pipeline(provider=provider, resume=True, **kwargs)
                    else:
                        with self.assertRaisesRegex(RuntimeError, "fingerprint mismatch"):
                            run_pipeline(provider=provider, resume=True, **kwargs)
                self.assertEqual(before, [path.read_bytes() for path in artifacts])
                # Explicit replacement is supported, including legacy files.
                replacement = run_pipeline(provider=MockResponsesProvider(config), resume=False, **kwargs)
                self.assertEqual(replacement["successful_records"], 1)


if __name__ == "__main__":
    unittest.main()
