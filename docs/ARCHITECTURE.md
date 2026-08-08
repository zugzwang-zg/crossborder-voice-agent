# Architecture

CrossBorder Voice is an evidence pipeline with a read-only decision interface.
The dashboard does not create analysis results; it renders validated artifacts
and keeps human workflow data separate from model output.

```text
source review CSV
  -> review contract and deterministic validation
  -> structured model analysis (or offline mock)
  -> schema and evidence validation
  -> evaluation / calibration reports
  -> scoped insight aggregation
  -> compact dashboard bundle
  -> evidence review and append-only human feedback
```

## Boundaries

- `src/review_contract.py` is the source-data boundary. Missing product scope is
  represented as `unknown`; it is never inferred from review language or text.
- `src/llm_analyzer.py` writes one traceable analysis record per review. Invalid
  output is rejected before aggregation.
- Evaluation reads frozen gold or challenge artifacts and never reads dashboard
  feedback as ground truth.
- Aggregation reports observed sample support, not market prevalence.
- `scripts/prepare_dashboard_data.py` compacts validated results for the UI and
  preserves source IDs, scope, evidence and review date availability.
- The dashboard stores reviewer decisions and comparison baselines under
  versioned local-storage keys. They do not mutate model artifacts.

## Public and private data

The public demo contains ten approved reviews and aggregated insights. Full
source text, gold annotations, API logs and reviewer workbooks remain outside
the public repository. See `DATA_AND_PRIVACY.md` for the release checklist.

## Failure behavior

Contract, traceability and scope failures stop the pipeline. The UI exposes
empty, loading and retry states. Date sorting remains disabled when dates are
absent instead of inventing chronology.
