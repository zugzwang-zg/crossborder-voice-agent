# Insight aggregation methodology

The aggregation layer consumes only schema-valid, evidence-checked review analyses. It does not call a model to invent summaries.

## Counting rules

- The unit of analysis is a unique `review_id`.
- A review contributes at most once to a metric for the same label.
- Language and star-rating breakdowns are retained.
- Product, packaging and fulfillment issues remain separate.
- Cross-language differences are descriptive and are not treated as cultural causes.

## Insight requirements

Every published insight includes:

- the number of supporting reviews;
- the language and rating distribution;
- source review IDs;
- representative verbatim evidence;
- a bounded interpretation;
- product, marketing or content actions that remain linked to evidence.

Recommendations are hypotheses for validation, not proof of causality.

## Outputs

The deterministic aggregator produces:

- `reports/consumer_insights.md`
- `reports/consumer_insights.json`
- summary tables under `data/aggregated/`

Run it with:

```powershell
python scripts/aggregate_insights.py
```

The public repository contains aggregate tables and a small demo sample. Full review-level outputs remain local under the rules in [PUBLIC_DATA_POLICY.md](../data/PUBLIC_DATA_POLICY.md).
