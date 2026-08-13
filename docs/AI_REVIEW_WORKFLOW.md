# Multi-model AI pre-review workflow

This workflow gives a solo maintainer repeatable pre-review coverage without
claiming that models are independent human annotators. AI results are stored
separately from the frozen human-gold protocol and cannot be promoted into
human-labelled challenge metrics.

## Roles

| Stage | Default model | Responsibility | Visibility |
|---|---|---|---|
| Mechanical screen | `gpt-5.6-luna` | Schema, exact evidence and obvious contradiction checks | Frozen item only |
| Semantic review | `gpt-5.6-terra` | Independent bilingual sentiment/aspect/issue and evidence judgment | Frozen item only |
| Risk review | `gpt-5.6-sol` | Independent hallucination, privacy, sampling and business-claim challenge | Frozen item only |
| Cross-provider adversarial review | DeepSeek V4 Pro through the maintainer's Claude Code local proxy | Independent workflow, evidence-boundary and correlated-blind-spot challenge | Frozen item/release diff only; no OpenAI review output |
| Adjudication | `gpt-5.6-sol` at `xhigh` | Evidence-based resolution of disagreements and high-risk findings | Frozen item plus completed OpenAI and imported external reviews |

The three first-stage model IDs must remain different. The adjudicator is not a
fourth vote: it runs only when independent decisions differ, a reviewer blocks,
a high/critical finding exists, or semantic/risk scores differ by at least two.
Any high/critical imported DeepSeek finding also forces adjudication. Missing
external results produce `external_review_pending`, never
`ai_pre_review_passed`. The external model is run in an isolated read-only
Claude Code session and its backend identity is recorded as
`maintainer_configured_unverified` unless the proxy exposes verifiable metadata.

## Safety and claim boundary

- Every request is hashed and every result records the role and model ID.
- A `running` manifest exists before model calls begin. Each validated stage is
  atomically persisted before the next aggregation step.
- Independent reviewers never receive another model's answer.
- The model may use only supplied references; missing knowledge is a limitation.
- Every result requires owner sign-off even when its status is
  `ai_pre_review_passed`.
- `human_evaluation_claim_allowed` is always `false`.
- The frozen 40-review human challenge set remains pending unless real people
  annotate it. A release may instead state that the prototype received
  multi-model AI pre-review and omit new human-evaluation claims.

All output goes under ignored `.private/ai_review/`. Review it before sharing;
API inputs and model comments may contain material that should stay private.

## Prepare input

Create one JSON object per line using
`data/sample/ai_review_input.demo.jsonl` as the contract. Each item requires:

- a safe unique `item_id`;
- `project: "crossborder-voice"`;
- the candidate review analysis;
- one or more references with unique IDs and complete source text;
- an explicit rubric;
- non-sensitive metadata only.

Do not put API keys, reviewer identities or unpublished full customer data in
the input.

### Freeze the actual release candidate

The demo JSONL above tests the contract only. The v0.2 release gate uses all 15
insights in `reports/consumer_insights.json`. Build the private frozen input with:

```powershell
python tools/prepare_release_candidate_review.py
```

The builder checks the candidate version against `release_manifest.json`,
reconstructs aggregation buckets from `review_analysis_v11.jsonl`, and rejects a
stale support count, source-ID set, language/rating breakdown or representative
quote. It writes deterministic `input.jsonl` and `freeze_manifest.json` under
`.private/ai_review/release-candidate/v0.2.0-rc.1/`. The manifest binds every
source file and item with SHA-256 and records zero model calls and no external
transfer authorization.

Validate that frozen input without spending API credit:

```powershell
python tools/ai_review_workflow.py `
  --config config/ai_review_roles.json `
  --input .private/ai_review/release-candidate/v0.2.0-rc.1/input.jsonl `
  --validate-only
```

Any change to the release manifest, insight artifact, review-level analysis,
methodology or data boundary requires rerunning the builder and discarding all
results for the old input hash.

## Validate without spending API credit

```powershell
python tools/ai_review_workflow.py `
  --config config/ai_review_roles.json `
  --input data/sample/ai_review_input.demo.jsonl `
  --validate-only
```

Validation checks the role separation, model assignments, item contract and
input hash. It also reports high-confidence secret/PII detector results without
echoing matched values. It makes no API calls.

## Export and import the DeepSeek review

Export one frozen packet per item. The packet contains the exact input hash,
role identity, instructions and strict output contract:

```powershell
python tools/ai_review_workflow.py `
  --config config/ai_review_roles.json `
  --input .private/ai_review/release-candidate/v0.2.0-rc.1/input.jsonl `
  --data-classification internal `
  --export-external-packets .private/ai_review/release-candidate/v0.2.0-rc.1/deepseek-packets
```

Open each packet in the isolated Claude Code conversation and ask the configured
DeepSeek route to return only the JSON object required by `output_contract`.
Store one result per line in an ignored JSONL file such as
`.private/ai_review/deepseek-results.jsonl`. Do not change identity or hash
fields. The runner rejects a mismatched role, model, item hash, duplicate result
or evidence location that does not resolve to the exact frozen source slice.
Packet export applies the same secret/PII scan and requires a `.private` output
path. `--redact-sensitive-data` can replace supported PII before hashing and
export. Export only creates a local packet; it does not authorize sending that
packet to the manually configured external provider.

## Evidence location and bounded-quote contract

Output schema `1.1` requires every finding to bind `evidence_quote` with all of:

- `reference_id`: `candidate` or the unique ID of one supplied reference;
- `evidence_path`: an absolute RFC 6901 JSON Pointer to one string field;
- `evidence_start` and `evidence_end`: zero-based Unicode code-point offsets,
  with the end offset exclusive.

The exact source slice at that path and offset range must equal the quote. A
candidate finding must point under `/candidate/...`; a reference finding must
point to the named reference's `/content` field. JSON Pointer tokens escape `/`
as `~1` and `~` as `~0`. Explicit offsets disambiguate repeated text.

Quotes must have no leading or trailing whitespace and may contain at most 280
Unicode code points and three lines. These deterministic limits reject clearly
over-broad evidence but cannot prove semantic minimality; reviewers and the
owner must still decide whether every remaining word is necessary. Re-export
external packets after this schema upgrade; schema `1.0` results fail closed.

## Execute

```powershell
python -m pip install -r requirements-ai-review.txt
$env:OPENAI_API_KEY = "set-locally-do-not-commit"
python tools/ai_review_workflow.py `
  --config config/ai_review_roles.json `
  --input .private/ai_review/release-candidate/v0.2.0-rc.1/input.jsonl `
  --external-review .private/ai_review/release-candidate/v0.2.0-rc.1/deepseek-results.jsonl `
  --output .private/ai_review `
  --max-items 1 `
  --max-api-calls 12 `
  --max-total-tokens 60000 `
  --max-output-tokens 4096 `
  --max-cost-usd 2.00 `
  --data-classification internal `
  --api-data-controls default `
  --confirm-api-data-policy `
  --execute
```

Use this one-item paid smoke test before a full run. The runner retries
each failed structured response at most twice, runs the three blind stages in
parallel, imports the frozen external result before escalation, and records
response IDs, the provider-returned model, service tier, system fingerprint and
token usage when provided by the API. If the DeepSeek route is unavailable,
omit `--external-review`; the run remains explicitly pending.

For a route and strict-schema compatibility probe that must not trigger other
reviewers or adjudication, use the dedicated single-stage mode. This creates a
separate audit manifest with `claim_scope=api_schema_and_route_compatibility_only`:

```powershell
python tools/ai_review_workflow.py `
  --config config/ai_review_roles_nano.json `
  --input .private/ai_review/release-candidate/v0.2.0-rc.1/input.jsonl `
  --output .private/ai_review/nano-smoke `
  --max-items 1 `
  --smoke-stage mechanical_screen `
  --max-api-calls 3 `
  --max-total-tokens 100000 `
  --max-output-tokens 8192 `
  --max-cost-usd 0.50 `
  --data-classification internal `
  --api-data-controls default `
  --confirm-api-data-policy `
  --execute
```

## Privacy gate

Every `--execute` must declare `--data-classification` as `public`, `internal`,
`confidential` or `restricted`, declare the OpenAI project control as `default`,
`modified_abuse_monitoring` or `zero_data_retention`, and explicitly pass
`--confirm-api-data-policy`. This confirmation means the maintainer has authority
to transmit the selected content and has checked the project setting; the runner
records MAM/ZDR as `maintainer_asserted_unverified` because it cannot inspect the
account control plane.

`restricted` input is always refused. `confidential` input is refused under
`default` controls and requires a maintainer-asserted MAM or ZDR project. These
labels do not make unsafe content safe: API keys, bearer tokens, private keys and
secret-bearing fields always block execution and must be removed at source.
High-confidence email, phone, IP/SSN patterns and named identifier fields block
unless `--redact-sensitive-data` is used. Redaction operates on an in-memory copy,
uses stable `<REDACTED:kind>` tokens, revalidates the transformed contract and
never writes a lookup table or matched value to the manifest. Free-text scanning
is defense in depth, not proof that all personal or confidential information was
found.

The input, imported external reviews and the role configuration are scanned
before the API key is required. `run_manifest.json` records source/request hashes,
detector paths and actions, classification, asserted project control and the
privacy-context hash. Changing the privacy context blocks `--resume-run`; adding
a newly scanned external review remains allowed under the same context.

Outputs must be under a path component named `.private`. A non-private path is
rejected unless the data is declared `public` and
`--allow-non-private-output` is supplied, which emits a warning. `store=False`
continues to be sent, but it is not described as Zero Data Retention. Official
OpenAI documentation says API data is not used for training unless the customer
opts in, while default abuse-monitoring and Responses application-state retention
rules may still apply. Review the current
[OpenAI data controls documentation](https://developers.openai.com/api/docs/guides/your-data)
before confirming a paid run.

## Runtime identity and reproducibility

Every paid run binds a versioned runtime identity into `run_manifest.json`
before the first request. It includes the OpenAI SDK version, Responses endpoint
category (`official_openai` or `custom_or_proxy`), runner and strict review-schema
SHA-256 hashes, plus the requested model, reasoning effort and system-prompt hash
for every role. Custom endpoint hostnames and URLs are deliberately not written
to the manifest. Injected fake clients are labelled separately in tests.

Each saved OpenAI review repeats those static fields and adds the response ID,
provider-returned model, request-message hash, returned service tier, system
fingerprint, creation time and usage when available. A returned model that differs
from the requested ID is recorded as a provider-resolved model, not silently
rewritten or automatically rejected: the official model guide documents that an
alias such as `gpt-5.6` can route to another model. Missing response ID or actual
model fails closed. The manifest aggregates observed models by stage so release
notes can distinguish configured IDs from returned IDs.

Runtime identity is part of the resume boundary. A runner, schema, system prompt,
SDK, endpoint category, model or reasoning-effort change blocks `--resume-run`
before any new API call; start a new run or restore the exact runtime instead.
Saved OpenAI stages are revalidated against the bound identity. Provider-returned
model and fingerprint fields improve traceability but are not independent
cryptographic proof of the backend, especially behind a custom proxy. Review the
current [OpenAI model guide](https://developers.openai.com/api/docs/guides/latest-model)
and [Responses API reference](https://platform.openai.com/docs/api-reference/responses)
before changing model routing or response metadata handling.

## Hard budget gates

`--execute` refuses to start unless all four limits are supplied. The call,
total-token and calculated USD limits cover the primary stages, adjudication
and every retry. `--max-output-tokens` is also sent to the Responses API for
each request. The runner uses the standard service tier and does not enable
paid tools.

Before a new run, the runner reserves enough calls, estimated input tokens,
maximum output tokens and cost for one attempt of all three primary stages. A
thread-safe reservation occurs again before every request, so parallel stages
cannot each spend the same remaining budget. The input estimate uses serialized
UTF-8 bytes plus framing headroom; costs conservatively charge all input at the
uncached rate and apply each model's configured documented long-context rule.
If response usage is absent, the complete worst-case reservation
is committed rather than treated as free.

Pricing lives in `config/ai_review_pricing.json`, including its verification
date, official source URL and model output limits. Snapshots older than 30 days
block execution by default. Refresh the file against the official model pricing
before raising that age threshold. This is a runner-side cap calculated from
the pinned tariff; maintain an account/project spend limit as a separate
billing backstop. Manually executed DeepSeek/Claude Code cost is outside this
OpenAI API budget.

Every reservation and settlement is atomically reflected in
`run_manifest.json`, including exact decimal USD strings and the pricing hash.
On resume, prior committed usage is cumulative. Any reservation left outstanding
by an interrupted process is converted to committed unverified usage, so
restarting cannot make a possibly billed request disappear. A budget-exhausted
stage fails closed, is recorded under `errors/`, and causes a non-zero CLI exit.

## Failure records and safe resume

A stage failure no longer discards successful sibling reviews. The runner writes
an immutable timestamped record under `errors/`, gives the item
`ai_pre_review_failed`, and finishes the run manifest as `partial` or `failed`.
Each record includes a bounded exception chain and root-cause type/message,
without response bodies. After three consecutive item failures by default, the
stage circuit opens and later items fail locally without spending API calls.
Use `--stage-failure-circuit-breaker N` to set a stricter positive threshold.
Runs without stage failures finish as `completed`; this execution status does
not override `external_review_pending` or owner sign-off.

Resume with the exact run ID printed by the failed or interrupted run:

```powershell
python tools/ai_review_workflow.py `
  --config config/ai_review_roles.json `
  --input .private/ai_review/release-candidate/v0.2.0-rc.1/input.jsonl `
  --external-review .private/ai_review/release-candidate/v0.2.0-rc.1/deepseek-results.jsonl `
  --output .private/ai_review `
  --resume-run RUN_ID `
  --max-api-calls 12 `
  --max-total-tokens 60000 `
  --max-output-tokens 4096 `
  --max-cost-usd 2.00 `
  --data-classification internal `
  --api-data-controls default `
  --confirm-api-data-policy `
  --execute
```

Before any new API call, resume validates the run ID, project, item count, input
hash, config hash, privacy context, complete runtime identity and every saved
review. Valid completed stages are skipped;
only missing stages run again. A saved external result cannot be replaced with
different content inside the same run. Adjudication records include a hash of
their complete review context. If a newly imported external result changes that
context, the old adjudication is retained under `reviews/history/` and a new
adjudication is required. Temporary `.tmp` files are never treated as completed
results.

The resume limits are cumulative for the same run. Reusing the original values
does not reset usage; raising a cap is an explicit maintainer spending decision.

## Audited model-replacement fork

Changing a model changes the config and runtime identity, so it must create a
new run rather than resume the old run. Compatible review results may be carried
forward only when the frozen item, role ID, requested model, reasoning effort
and complete system-prompt hash match. The new review embeds the source run ID,
source manifest hash and original review hash. Seeded adjudications receive an
additional check: the complete current primary and external review context must
reproduce the saved adjudication-context hash before the result can be used.
Mechanical reviews from a replaced model and every adjudication that depended
on changed context must be rerun. When only some frozen item hashes change, the
seed loader carries matching item-stage reviews, records every hash-mismatched
review or missing optional adjudication as skipped, and reruns only required
stages. A mismatched review is never coerced onto new content.

```powershell
python tools/ai_review_workflow.py `
  --config config/ai_review_roles_nano.json `
  --input .private/ai_review/release-candidate/v0.2.0-rc.1/input.jsonl `
  --external-review .private/ai_review/release-candidate/v0.2.0-rc.1/deepseek-results.jsonl `
  --output .private/ai_review/nano-full `
  --seed-run-dir .private/ai_review/OLD_RUN_ID `
  --seed-stage semantic_review `
  --seed-stage risk_review `
  --seed-stage adjudication `
  --stage-failure-circuit-breaker 1 `
  --max-api-calls 90 `
  --max-total-tokens 2000000 `
  --max-output-tokens 8192 `
  --max-cost-usd 3.00 `
  --data-classification internal `
  --api-data-controls default `
  --confirm-api-data-policy `
  --execute
```

## Owner release gate

1. No item may remain `external_review_pending`, `revision_required` or
   `owner_review_required`.
2. Inspect every high/critical finding and every adjudicated item personally.
3. Confirm input and config hashes match the intended frozen versions.
4. Run the normal Python and Dashboard checks.
5. Describe results as AI pre-review, including model IDs and limitations.
6. Do not report inter-model agreement as inter-annotator human agreement.

Model defaults follow the current OpenAI model guide. Pin or update model IDs in
the config only after a representative regression comparison; availability and
pricing can change independently of this repository.
