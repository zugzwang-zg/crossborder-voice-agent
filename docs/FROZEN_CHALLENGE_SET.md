# Frozen challenge-set extension

The original 100-review human gold set contains 36 `mixed` records but only one
`neutral` record and no `uncertain` record. It also cannot be changed after
prompt/model development without invalidating the original comparison.

`scripts/prepare_frozen_challenge.py` therefore freezes a separate 40-review
challenge input set from the local MARC sample. It selects four English and four
Spanish candidates for each of five stress categories:

- neutral candidates;
- mixed candidates;
- long reviews;
- multi-topic reviews;
- implicit-attribute/context reviews.

The category names describe deterministic selection heuristics, not gold
labels. The script excludes every review ID in the current 100-review gold set
and the prompt-development sample, then records hashes and overlap counts in
`reports/frozen_challenge_manifest.json`.

## Promotion gate

The challenge set is frozen but not included in headline metrics until:

1. two independent reviewers label sentiment, aspects and issues;
2. reviewer identities and timestamps are recorded outside the public corpus;
3. disagreements are adjudicated without looking at model predictions;
4. the completed annotation file is hashed and marked immutable;
5. predictions are generated only after the gold file is frozen;
6. the evaluation report clearly separates the original 100-set result from the
   new challenge result.

This process expands held-out coverage without presenting model-generated or
single-agent labels as human gold.

## Human evidence-review rules

- Reviewers must judge whether every extracted label is supported by an exact,
  minimal source span; star rating alone is not evidence for a text label.
- Reviewers must flag hallucinated, overly broad or context-stripped evidence,
  and may not repair a prediction while scoring it.
- The two annotation passes remain independent. Reviewers may not inspect model
  outputs, evaluation results or one another's labels before adjudication.
- Prompt, schema or normalization changes are always compared on the same
  immutable challenge hash. A changed challenge input starts a new named set
  and cannot replace an earlier result silently.
- Headline reporting must state sample size, class support, language split and
  any classes that remain too small for a reliable interpretation.
