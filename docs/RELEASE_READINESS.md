# v0.2.0 release readiness

Candidate `v0.2.0-rc.1` is locally testable but has not been released, tagged or
pushed by this workflow.

## Ready

- Source review, analysis and insight contracts have regression coverage.
- Evaluation reports expose per-class metrics, calibration limits and frozen
  challenge-set status.
- Dashboard filters distinguish common and advanced controls, expose active
  filters and support paginated, sortable, highlighted evidence review.
- Loading, empty and retry paths are implemented.
- Architecture, demo, privacy, contribution and security documentation exist.

## Blocking maintainer decisions

- Select and add an explicit repository license.
- Decide when the frozen 40-review challenge set has two independent annotations
  and is eligible for reported metrics.
- Review the local release diff before creating a tag, push or GitHub release.

## Local verification

```powershell
python -m unittest discover -s tests -q
cd dashboard
pnpm lint
pnpm test
```

Only after blockers are resolved should the maintainer update
`release_manifest.json`, create signed release notes and tag `v0.2.0`.
