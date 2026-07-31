# Gold Evaluation Annotation Report

## 1. Deliverables

- Machine-readable gold set: `data/annotation/gold_sample.csv`
- Human-review workbook: `data/annotation/gold_sample_review.xlsx`
- Records: 100
- Role: frozen held-out final evaluation set

## 2. Sampling controls

- English: 50; Spanish: 50
- Each language × star stratum: 10 records
- Length buckets: short 20, regular 60, long 20
- Taxonomy-design sample overlap: 0
- Deterministic seed: `crossborder-voice-gold-eval-v1`

## 3. Annotation coverage

- Sentiment counts: positive=32, neutral=1, negative=31, mixed=36, uncertain=0
- Ambiguous records: 2
- All records include sentiment, intensity, experience status, star-text alignment, exact-text evidence, confidence and review status.
- Aspect, issue and scenario fields are left blank when the review provides no explicit evidence.

## 4. Review protocol and limitation

Two complete passes were performed in different record orders during this session. This report does not claim that a literal 24-hour interval occurred. The requested one-day recheck can be repeated later as an optional temporal-stability audit without changing the frozen split.

The second pass revised 6 records where the first pass had over-inferred a scenario, used an overly specific issue code, or treated a resolved concession as a substantive negative.

## 5. Leakage prevention

The 100 records used during exploratory manual reading were excluded because they informed the taxonomy. The present 100 review IDs, their labels and their error cases must not be used in prompt development or any model-selection decision. Development examples must be selected from the remaining non-gold records.
