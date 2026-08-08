# Sampling and product-scope contract

## Current sampling design

The formal MARC dataset is deliberately stratified by language and star rating:
100 reviews are selected for each `language × stars` combination. Consequently,
all rates are descriptive statistics for the selected sample. They do not
estimate natural Amazon Beauty prevalence, current market prevalence, or a
country's consumer behavior.

Every aggregation report now includes:

- the selected denominator;
- language × star stratum counts;
- `is_weighted = false`;
- `population_prevalence_supported = false`;
- a warning when fewer than 30 reviews remain.

## Supported scopes

The aggregation layer supports:

```text
global
product_id=<known source ID>
product_subcategory=<known source value>
```

Unknown values cannot be used as a product scope. Product title, brand,
subcategory, market, country, or culture must not be inferred from the review
text or language.

Example:

```powershell
python scripts/aggregate_insights.py `
  --scope-field product_id `
  --scope-value P1 `
  --small-sample-threshold 30
```

Product-scoped reports retain the selected scope and sample boundary on every
insight and exported table row. The Dashboard can consume these fields in the
next UI phase without re-deriving the denominator.
