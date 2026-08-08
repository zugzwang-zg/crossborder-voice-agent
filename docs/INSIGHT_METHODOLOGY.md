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

## Actionable insight contract

Each generated insight retains the legacy report fields and also exposes a
stable decision contract:

```text
insight_id
scope
finding
support_count
support_rate
representative_review_ids
confidence_or_evidence_grade
recommended_action
action_type
limitations
```

`support_rate` always uses the selected scope's unique review records as its
denominator. `action_type` is limited to product, listing, advertising, content,
or FAQ work. Recommendations identify a concrete next step; the limitations
continue to state that review associations do not prove causality.

The public repository contains aggregate tables and a small demo sample. Full review-level outputs remain local under the rules in [PUBLIC_DATA_POLICY.md](../data/PUBLIC_DATA_POLICY.md).
