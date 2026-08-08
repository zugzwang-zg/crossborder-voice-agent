# Data and privacy register

This document defines what data CrossBorder Voice uses, what may be published,
and what the current demo does with user information. It complements
[`data/DATA_SOURCE.md`](../data/DATA_SOURCE.md) and
[`data/PUBLIC_DATA_POLICY.md`](../data/PUBLIC_DATA_POLICY.md).

## Dataset register

| Asset | Source and period | Collected / verified | Purpose | Public scope | License / terms status |
|---|---|---|---|---|---|
| MARC English and Spanish `beauty` reviews | Multilingual Amazon Reviews Corpus; reviews dated 2015-11-01 to 2019-11-01 | deterministic project sample created 2026-07-28 | method development, frozen evaluation and evidence-trace demo | 10 curated review rows plus aggregate tables; the 1,000-row analysis corpus stays local | Amazon publishes MARC for research use; the project must follow the source terms and does not treat the corpus as unrestricted commercial data |
| Gold annotations and model predictions | derived locally from MARC | project evaluation runs | model evaluation and regression | not public | derived data inherits source-data restrictions; redistribution permission has not been established |
| Dashboard insight feedback | entered by a reviewer in the dashboard or JSONL store | at review time | status, owner, priority, due date, notes and quality flags | local browser storage / local JSONL by default; export is user-initiated | project-generated operational metadata; repository code license is still pending maintainer decision |

The source pages and deterministic sampling procedure are recorded in
[`data/DATA_SOURCE.md`](../data/DATA_SOURCE.md). The 2015–2019 review period means
the results are a capability demonstration, not a statement about the current
market.

## Review text and identifiers

- The public repository may show the 10 rows in `data/sample/demo_reviews.csv`,
  short evidence excerpts required to audit a conclusion, and aggregates that
  do not reproduce the full corpus.
- Full raw/cleaned reviews, frozen evaluation sets, full prediction outputs,
  API logs and review workbooks remain local and are excluded by `.gitignore`.
- MARC reviewer identifiers are dropped before project sampling. Source review
  identifiers are anonymous corpus IDs; they are retained only where needed to
  resolve an insight back to evidence. Product IDs are not guessed when absent.
- A future import pipeline for first-party reviews must remove direct
  identifiers and replace external customer/order IDs with a project-scoped
  hash before analysis. Free text must be screened for contact, payment,
  address, account and health information before publication.

## Upload, retention and third parties

The current public Dashboard has no file-upload control and calls no model API.
It fetches packaged local JSON data. Reviewer feedback is stored separately in
the browser under `crossborder-voice.insight-feedback.v1`; clearing site storage
removes that browser copy. Export occurs only when the reviewer chooses
“导出反馈”. The Python feedback store appends to a caller-selected local JSONL
path and never overwrites model output.

No retention policy for future hosted uploads is implied. Before upload or
online-model support is added, the product must disclose and enforce:

1. accepted fields and prohibited sensitive data;
2. storage location, encryption, access roles and a specific deletion period;
3. model provider, processing region, training/retention settings and other
   subprocessors;
4. deletion/export controls and incident contact;
5. explicit consent before any review text leaves the user's environment.

## Public-demo release checklist

- Publish only the curated sample and aggregates allowed above.
- Keep `.env`, credentials, relay/API logs and local feedback exports out of Git.
- Run traceability tests so every visible evidence ID resolves.
- Inspect text for direct identifiers and unusually identifying narratives.
- Label sampling, time period and source-term restrictions on every public view.
- Do not bundle the full corpus, private annotations or a real merchant corpus.
- Do not add a repository or data license until the maintainer has selected one
  and verified compatibility with the source-data terms.
