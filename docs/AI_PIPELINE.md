# AI analysis pipeline

CrossBorder Voice turns bilingual review records into validated, traceable JSONL outputs. The design favors evidence preservation and recoverability over unconstrained generation.

## Processing stages

1. Load normalized review records and reject duplicate IDs.
2. Build a versioned prompt containing the label dictionary and output contract.
3. Call an OpenAI-compatible Responses endpoint.
4. Parse the response and validate it against the schema.
5. Verify that cited evidence is present in the source review.
6. Normalize unsupported or conflicting labels.
7. Retry transient failures with exponential backoff.
8. Append successful records to resumable JSONL output and record run metadata.

## Output contract

Each result contains:

- review identity and language;
- sentiment, intensity and confidence;
- aspect-level polarity and evidence;
- explicit issues, motivations and usage scenarios;
- speech acts and expectation gaps;
- evidence-backed actions.

Missing evidence results in sparse output rather than inferred labels.

## Reproducibility and auditability

Prompt and schema versions are written into run metadata. JSONL output is append-only during processing, and completed review IDs are reused only after every existing record matches the current run fingerprint. The fingerprint binds the full input file, prompt text/version, provider endpoint, model parameters, schema and local validator. Changing only the row limit is supported; changing the dataset requires a new output path. Legacy outputs without a fingerprint are rejected. Validation happens before any request or artifact modification. Use a new output path to preserve an earlier experiment; `--no-resume` explicitly replaces the output. Errors are isolated per record so one malformed response does not discard the batch.

The core implementation is in:

- `src/llm_analyzer.py`
- `src/schema.py`
- `prompts/`
- `tests/test_llm_analyzer.py`

API configuration and operational safeguards are documented in [API_CONFIGURATION.md](API_CONFIGURATION.md).
