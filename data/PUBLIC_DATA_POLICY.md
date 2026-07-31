# Public data policy

The project uses the Multilingual Amazon Reviews Corpus (MARC) for research and
method demonstration. Full review-level data, gold annotations, model
predictions, API logs, and human-review workbooks remain local and are excluded
by `.gitignore`.

The public repository may contain:

- a minimal deterministic sample in `data/sample/` for offline smoke testing;
- aggregate tables that do not reproduce complete review texts;
- derived metrics and short evidence excerpts needed to explain evaluation.

The public repository should not contain:

- API keys, relay-station account details, or `.env` files;
- the full raw/cleaned corpus;
- frozen gold annotations or manual-review workbooks;
- full model outputs with all review texts;
- local run logs or station billing records.

The source dataset dates from 2015–2019. Results demonstrate a method and a
product prototype; they must not be presented as current-market trends.
