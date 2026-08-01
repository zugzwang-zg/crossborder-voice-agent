# CrossBorder Voice Dashboard

Interactive consumer-insight dashboard built with Next.js, React, TypeScript and vinext.

[Open the public demo](https://crossborder-voice-86182.reidmozzie.chatgpt.site). The hosted demo uses static sample data and does not require an API key.

## Views

- Overview: dataset size, sentiment and star-rating distributions
- Aspect analysis: product attributes and cross-language comparisons
- Issue analysis: low-star problems, support counts and evidence
- Context and language: motivations, scenarios, expectation gaps and speech acts
- Insight library: traceable insight cards with source evidence
- Review explorer: filtering by language, rating, aspect and issue

## Local development

Requires Node.js 22.13+ and pnpm.

```bash
pnpm install
pnpm dev
```

## Validation

```bash
pnpm lint
pnpm test
```

`pnpm test` runs a production build and validates the public demo bundle, analysis views and rendered structure. When the full local data bundle is available, it also runs traceability checks against all 1,000 analyzed reviews.

## Data modes

The dashboard loads `dashboard-data.json` when a full local bundle exists. That review-level file is excluded from Git. A clean clone falls back to `dashboard-data.demo.json`, generated from 10 balanced public samples.

Regenerate the demo bundle after preparing local aggregate outputs:

```bash
python ../scripts/prepare_dashboard_demo.py
```

The public bundle retains aggregate support counts while exposing only evidence that can be traced to the 10 included samples. The interface identifies this state as `PUBLIC DEMO`.
