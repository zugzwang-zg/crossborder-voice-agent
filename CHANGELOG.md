# Changelog

All notable changes will be documented in this file.

## [Unreleased]

### Added

- Canonical review source-data contract with product metadata aliases, explicit
  unknown values, duplicate-ID detection, and input validation.
- Traceable source metadata in each analysis JSONL record.
- Contract tests and Phase 1 baseline report.
- Contribution and security guidance.
- Product and subcategory scope selection in the aggregation layer.
- Sampling metadata, explicit unweighted prevalence boundary, stratum counts,
  and configurable small-sample warnings on reports, insights, and tables.
- GitHub Actions checks for the Python aggregation suite and Dashboard lint/tests.
- Canonical actionable-insight fields for scope, support rate, evidence IDs,
  action type, recommended action, and limitations.
- Dashboard product/subcategory scope controls, missing-scope guardrail, and
  persistent sampling boundary rail.
- README first-screen quick start, CI status, reproducible metrics, and data limits.
- Append-only insight feedback events with status, owner, priority, due date,
  notes and explicit quality flags, stored separately from model output.
- Dashboard human-decision ticket, local history and feedback export.
- Saved insight comparison baselines with added, removed and support-change
  deltas across filters or analysis versions.
- Consolidated data/privacy register and public-demo release checklist.
- Frozen 40-review bilingual challenge input spanning neutral/mixed candidates,
  long reviews, multi-topic reviews and implicit attributes, with zero overlap
  against the original gold set and prompt-development sample.
- Per-class sentiment metrics and confusion matrix, multilabel micro/macro
  scores, and confidence-calibration reporting with an uncalibrated UI policy.
- End-to-end regression from source contract through evaluation, traceable
  insight aggregation, dashboard compaction and append-only reviewer feedback.
- Common/advanced filter hierarchy, removable active-filter chips and resettable
  empty/error states in the analyst dashboard.
- Paginated evidence retrieval with relevance, star and intensity sorting,
  source highlighting and explicit unavailable-date behavior.
- v0.2.0 release-candidate architecture, demo and readiness documentation.

### Pending maintainer decision

- Select and add an explicit open-source `LICENSE`.
