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
| Dashboard insight feedback | entered by a reviewer in the dashboard or JSONL store | at review time | status, owner, priority, due date, notes and quality flags | local browser storage / local JSONL by default; export is user-initiated | project-generated operational metadata; repository code is Apache-2.0, while exported user content keeps its own rights status |

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

No retention policy for future hosted uploads is implied. Before product upload
or hosted online-model support is added, the product must disclose and enforce:

1. accepted fields and prohibited sensitive data;
2. storage location, encryption, access roles and a specific deletion period;
3. model provider, processing region, training/retention settings and other
   subprocessors;
4. deletion/export controls and incident contact;
5. explicit consent before any review text leaves the user's environment.

## Maintainer AI pre-review privacy gate

The public Dashboard remains offline, but the optional maintainer-only AI
pre-review runner now enforces a separate request-time gate. `--execute` requires
an explicit public/internal/confidential/restricted classification, an asserted
OpenAI project data-control mode, and a transfer confirmation. Restricted data
is refused; confidential data is refused under default controls. Secret patterns
always block. Supported PII patterns and identifier fields must be removed or
transformed with `--redact-sensitive-data` before a request is built.

The scanner covers the frozen input, imported external review text and role
configuration. It stores detector kind/path/action and source/request hashes,
not the matched value or a redaction lookup table. AI output is restricted to a
`.private` path unless public data receives an explicit override. The same
privacy-context hash is bound to safe resume. This is a defense-in-depth filter,
not a data-discovery guarantee or proof of provider-side settings.

The runner sends `store=False`, but the project does not equate that parameter
with Zero Data Retention. OpenAI's current data-control documentation states
that default abuse-monitoring and Responses application-state retention rules
may still apply; MAM/ZDR declarations are recorded as maintainer asserted and
unverified. See
[OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data).

## Public-demo release checklist

- Publish only the curated sample and aggregates allowed above.
- Keep `.env`, credentials, relay/API logs and local feedback exports out of Git.
- Run traceability tests so every visible evidence ID resolves.
- Inspect text for direct identifiers and unusually identifying narratives.
- Label sampling, time period and source-term restrictions on every public view.
- Do not bundle the full corpus, private annotations or a real merchant corpus.
- Run `tools/audit_third_party_assets.py --check-installed`; retain the repository
  license/NOTICE and do not imply Apache-2.0 relicenses MARC-derived content.
