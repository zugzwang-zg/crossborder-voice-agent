# v0.2.0 release readiness

Candidate `v0.2.0-rc.1` completed its release gate and was published from branch
`phase-7-license-and-review-plan` as the annotated Git tag `v0.2.0`.

## Ready

- Source review, analysis and insight contracts have regression coverage.
- Evaluation reports expose per-class metrics, calibration limits and frozen
  challenge-set status.
- Dashboard filters distinguish common and advanced controls, expose active
  filters and support paginated, sortable, highlighted evidence review.
- Loading, empty and retry paths are implemented.
- Architecture, demo, privacy, contribution and security documentation exist.
- The repository is licensed under Apache License 2.0 and includes a NOTICE.
- Direct dependencies, repository media, MARC-derived data, fonts and model
  services have a machine-audited inventory with a hash-bound Node lockfile.
- A multi-model AI pre-review path exists for solo-maintainer quality control,
  while preserving the boundary between AI review and uncollected human evidence.
- All 15 release insights can be deterministically frozen after their support
  counts, source IDs, breakdowns, quotes and support-rate denominator are checked
  against the review-level aggregation source.
- The formal audit run `20260812T072313649196Z-4eddf183f10c` completed all 15
  items. Its final decisions were 5 pass, 9 revise and 1 block. The owner accepted
  those findings as remediation input; this is not a release approval.
- The 9 revise findings and 1 blocked provenance finding were remediated in the
  generator. The report now uses cause-neutral routing, narrower evidence-bound
  wording, an explicit selected-record denominator and no released mean model
  confidence. The resulting `remediation-3` input was frozen and validated with
  zero model calls.
- DeepSeek completed the 15-item `remediation-3` external adversarial review.
  Strict offline validation accepted all 15 hash-bound results; all decisions
  were pass. Two pass results retain low-severity label/evidence-fit findings
  for repurchase intent and positive price-value evidence, which remain visible
  to the independent OpenAI stages and any later adjudication.
- The hash-bound OpenAI formal audit then completed all 15 items using the
  configured GPT-5.4, Terra and Sol roles plus necessary Sol adjudication. Final
  decisions were 11 pass and 4 revise, with no block, failed item or pending
  adjudication. Usage was 63 API calls, 588,371 tokens and USD 3.0859485.
- The four final revise findings were implemented in the generator and frozen as
  `remediation-4`. Its exact input hash is
  `6a14a10c77856e6878365449d7ed12421a43b3a326cc11d0a58040c0f803f7bc`.
  Hash comparison confirms that only items 03, 06, 09 and 10 changed; the other
  11 item hashes are identical to `remediation-3`.
- DeepSeek re-reviewed the four changed items and passed all four. The merge
  retained 11 old results only where the item hash still matched, discarded the
  four stale results, inserted the four new results, and strictly validated the
  resulting 15-item file. One low-severity repurchase-intent note and one
  informational price-value wording note remain visible but do not change the
  external pass decisions.
- The `remediation-4` OpenAI audit run
  `20260813T075034450135Z-6a14a10c7785` completed all 15 items on the exact
  frozen hash. It carried 33 hash-compatible primary reviews and 7 prior
  adjudications whose complete review context was unchanged, generated 12 new
  primary results for items 03, 06, 09 and 10, and used necessary Sol
  adjudication for all four. Final decisions were 15 pass, with no failed or
  pending item. Cumulative usage was 23 calls, 238,479 tokens and USD 1.4106930.
- The first execution began adjudicating unchanged items before its scope guard
  stopped the process. Three persisted results for items 01, 02 and 07 were
  removed from the formal result set and retained under
  `reviews/out_of_scope_replaced/`; one interrupted reservation is conservatively
  recorded as unverified. The hash-bound correction record is
  `scope_correction_manifest.json`. The final runtime observation contains new
  accepted results only for items 03, 06, 09 and 10.
- The runner now permits explicitly seeded adjudications, skips missing optional
  source adjudications, and revalidates every carried adjudication against the
  complete current primary and external review context before use. An actual
  remediation-3 to remediation-4 preflight carries 40 compatible reviews and
  skips 20 changed or missing results without an API call.
- A public hash-only attestation is available at
  `reports/ai_review_attestation.json`; raw inputs, review packets and model
  outputs remain ignored under `.private/`.
- Local verification after remediation passed 118 Python tests, Dashboard lint,
  production build and 4 Dashboard tests, plus the installed asset/license audit.

## Release gate completed

- The maintainer accepted the exact `remediation-4` formal AI review and recorded
  scope correction on 2026-08-13.
- The local release diff was reviewed. Private audit material is excluded,
  the public Dashboard demo was regenerated, optional SDK resolution was pinned,
  release metadata was aligned to `v0.2.0`, and the adjudication seed defect was
  fixed with regression coverage.
- The release scope was committed, the existing branch and annotated `v0.2.0`
  tag were pushed to `origin`, and no GitHub Release was created.

## Deferred evidence upgrade

The frozen 40-review challenge set still requires two real independent human
annotations before it can produce human-labelled metrics. This is not required
for a personal prototype release if the release is explicitly described as
multi-model AI pre-reviewed and makes no new human-evaluation claim.

## Local verification

```powershell
python tools/audit_third_party_assets.py --check-installed
python -m unittest discover -s tests -q
cd dashboard
pnpm lint
pnpm test
```

The `v0.2.0` release scope is preserved by its annotated Git tag. A GitHub
Release can be created separately later if desired.
