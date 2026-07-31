# OpenAI-compatible API configuration

The analyzer supports the OpenAI Responses API and compatible relay services. Configuration is read from environment variables; secrets must remain local.

## Required variables

```powershell
$env:OPENAI_API_KEY="your-api-key"
$env:OPENAI_BASE_URL="https://your-provider.example"
$env:OPENAI_RESPONSES_ENDPOINT="https://your-provider.example/v1/responses"
$env:OPENAI_MODEL="your-model-name"
```

`OPENAI_RESPONSES_ENDPOINT` takes precedence when set. Use the exact endpoint required by the provider and avoid appending `/v1` twice.

## Connectivity check

Run a single record before starting a batch:

```powershell
python -m src.llm_analyzer `
  --provider openai `
  --input data/sample/demo_reviews.csv `
  --limit 1 `
  --no-resume
```

If the request succeeds, run a small batch and inspect the output, error log and run log before scaling up.

## Reliability behavior

The pipeline supports:

- request timeouts and exponential-backoff retries;
- recovery from incomplete HTTP responses;
- record-level error isolation;
- resumable JSONL output keyed by `review_id`;
- prompt, schema, token and estimated-cost metadata in the run log.

When a long batch is interrupted, rerun the same command without `--no-resume`. The analyzer skips completed IDs and continues from the remaining records.

## Security

- Never commit API keys, account details, billing records or a populated `.env`.
- Prefer session-scoped environment variables or a local secret manager.
- Verify the provider's data-retention and logging policy before sending production data.
- Start with the public demo sample when testing an unfamiliar endpoint.
