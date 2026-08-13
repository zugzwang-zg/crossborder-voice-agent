# CrossBorder Voice v0.2.0

`v0.2.0` turns the prototype into a locally reproducible, audit-conscious
multilingual review-insight workflow. It remains a personal prototype and does
not claim production readiness or independently annotated human-evaluation
quality.

## Highlights

- Deterministic English/Spanish insight aggregation with traceable review IDs,
  representative evidence, explicit sampling boundaries and reproducible
  support-volume tiers.
- Remediated business recommendations that separate product, packaging,
  fulfillment, listing and content responsibilities and avoid unsupported
  causal or market claims.
- A five-view local Dashboard with scope filters, evidence highlighting,
  pagination, saved comparisons and append-only human feedback.
- A fail-closed multi-model AI pre-review runner with role separation, strict
  structured results, privacy gates, cumulative budget controls, crash-safe
  resume and hash-bound carry-forward.
- Apache License 2.0 for project-created code and documentation, with an
  explicit NOTICE and separate MARC-derived-data and third-party boundaries.

## Audit status

The frozen 15-item `remediation-4` candidate has input SHA-256
`6a14a10c77856e6878365449d7ed12421a43b3a326cc11d0a58040c0f803f7bc`.
The final multi-model AI pre-review recorded 15 pass decisions, no failed item
and no pending adjudication. This is AI pre-review evidence, not human ground
truth. See [`reports/ai_review_attestation.json`](../reports/ai_review_attestation.json)
for the public hash and scope attestation; raw inputs and model outputs remain
private.

During the final audit, automatic adjudication initially included three
unchanged candidates. The run was stopped, those results were excluded from the
formal result set, and one interrupted reservation was conservatively recorded
as unverified. The runner now supports exact-context adjudication carry-forward
to prevent that recurrence.

## Verification

- 118 Python tests
- Dashboard lint
- Dashboard production build and 4 tests
- installed dependency and third-party asset/license audit
- public Dashboard demo traceability and deprecated-confidence-field checks

## Remaining boundary

The frozen 40-review challenge set does not yet have two independent human
annotations. Do not describe the reported AI-review agreement as inter-annotator
agreement or use it to claim human-labelled model quality.
