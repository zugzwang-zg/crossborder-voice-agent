# Third-party assets and license audit

This document separates the repository's Apache-2.0 code and project-created
media from external software, corpus-derived data and model services. The
machine-readable source of truth is
[`config/third_party_assets.json`](../config/third_party_assets.json).

## Copyright holder

CrossBorder Voice is a personal project. `NOTICE` uses the maintainer's public
Git identity, `zugzwang-zg`, rather than the inaccurate collective label
“contributors.” This is a public copyright notice, not a claim over third-party
packages, MARC records, platform names or provider models.

## Inventory scope

- 22 direct declarations cover the optional Python OpenAI client and every
  runtime/development dependency in `dashboard/package.json`.
- The optional OpenAI client is pinned to the `2.53.0` version recorded by the
  formal audit runtime rather than resolved from an open major-version range.
- `dashboard/pnpm-lock.yaml` is hash-bound to the reviewed transitive graph.
- Project-created slides, screenshots, favicon, social preview and label workbook
  are recorded separately from MARC-derived samples, aggregates and reports.
- Dashboard CSS uses system font names; no standalone font file is a project
  source asset.
- OpenAI and the maintainer-configured DeepSeek route are services. No provider
  model weights are bundled or licensed under this repository's Apache license.
- The public AI-review attestation contains project-created hashes and scope
  metadata only; raw model inputs and outputs remain private.
- Deleted unused starter SVGs are not shipped merely to preserve an unclear or
  unnecessary asset lineage.

The exact installed Node graph currently includes permissive, attribution,
file-level copyleft and public-domain-style expressions. In particular,
`@img/sharp-win32-x64` reports `Apache-2.0 AND LGPL-3.0-or-later`. The source
repository does not distribute `node_modules`; any container, desktop bundle or
other binary distribution must repeat the installed audit, preserve upstream
license/notice material and assess the artifact actually shipped.

## Data boundary

MARC is an external corpus, not an Apache-licensed project asset. The public
repository is limited to the documented small sample, aggregates, metrics and
short evidence excerpts; it does not grant permission to redistribute the full
corpus, gold data or complete model output. See the
[Amazon Science corpus description](https://www.amazon.science/publications/the-multilingual-amazon-reviews-corpus)
and [AWS Open Data entry](https://registry.opendata.aws/amazon-reviews-ml/).

## Offline audit

```powershell
python tools/audit_third_party_assets.py
python tools/audit_third_party_assets.py --check-installed
```

The first command fails on an unlisted direct dependency, changed lockfile,
uncovered repository asset, stale inventory entry, missing upstream URL or
ambiguous `NOTICE` holder. `--check-installed` additionally scans installed Node
package metadata and refuses a license expression outside the reviewed set.
The audit uses package metadata; it is not legal advice or proof of upstream
ownership.

Run both commands after any dependency, media, dataset, font, model-provider or
packaging change. Refresh the inventory date and lock hash only after reviewing
the new graph. The [npm package registry](https://www.npmjs.com/) and
[PyPI OpenAI package page](https://pypi.org/project/openai/) are the upstream
metadata references used for the current direct inventory.
