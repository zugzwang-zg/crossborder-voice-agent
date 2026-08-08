# Contributing

## Development setup

The Python pipeline and tests use the standard library on Python 3.11+.

```powershell
python -m unittest discover -s tests -q
```

Dashboard checks:

```powershell
cd dashboard
pnpm install --frozen-lockfile
pnpm lint
pnpm test
```

## Change requirements

1. Create a focused branch such as `feat/review-contract` or `fix/sample-scope`.
2. Do not commit private reviews, gold labels, API logs, `.env`, or API keys.
3. Add a regression test for every validator or aggregation behavior change.
4. Keep source metadata separate from model-generated analysis.
5. Update the relevant data contract, methodology, or evaluation report when a
   public metric or interpretation changes.
6. Run all Python and dashboard checks before opening a pull request.

## Data and claim boundaries

- Do not infer a country, culture, brand, product title, or subcategory when the
  source dataset does not provide it.
- Do not present stratified sample percentages as natural market prevalence.
- Do not add copyrighted or restricted full-review datasets to the repository.

The repository license is pending an explicit maintainer decision. Until a
`LICENSE` file is added, contribution does not imply a particular reuse grant.
