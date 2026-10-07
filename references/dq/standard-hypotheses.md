# Standard hypotheses

Tested by `dq-prover` on every relation in scope (the changed or investigated
models and their lineage), before any model-specific suspicion. Each is written to be
disproven: the query returns the one number that settles it. A hypothesis that
survives is a finding to verify; one that is disproven is reported as checked
and found fine. `{relation}`, `{parent}`, `{key_cols}`, `{date_col}`,
`{entity_key}`, `{col}` and `{cadence_days}` are placeholders; the cadence comes
from the model's `meta`, its freshness block, the domain context, or the observed
gap between loads.

| # | Hypothesis | Query that could disprove it | Survives when |
|---|---|---|---|
| H1 | The table has not loaded within its cadence | `INFORMATION_SCHEMA.TABLES` for `last_altered`; for a view, `max({date_col})` | Older than `{cadence_days}` allows |
| H2 | Today's volume is off from usual | rows per `{date_col}` for the last 14 days | The latest day is 0, or outside 3 times the median absolute deviation of the others |
| H3 | The key has duplicates | `count(*) - count(distinct {key_cols})` per month over the last 365 days | Any month above zero |
| H4 | Key columns hold nulls or placeholder values | rows per month where any of `{key_cols}` is null or in `('', 'UNKNOWN', 'N/A', '-1', '0')`, last 365 days | Above zero |
| H5 | Recent builds failed | `model_health`, then the build-history recipe in `patterns.md` | Any failed build in 7 days, or the same error on several days |
| H6 | An incremental model disagrees with its parent | the frozen-history recipe in `patterns.md`, last 30 days | Above 1% of rows differ |
| H7 | A description's rule is broken | the rule as an invariant query that returns violating rows | Any row |
| H8 | The series has gaps | the series-gap recipe in `patterns.md`: expected (entity, period) pairs left-joined to the table, last 90 days | Any missing pair |
| H9 | The child does not reconcile with its parent | per day for 30 days: rows and distinct keys in `{parent}` against `{relation}`, joined on `{date_col}` | Any day where the child has more keys than the parent, or fewer by more than the model's filters explain |
| H10 | Child keys have no parent | `{relation}` left-joined to `{parent}` on `{entity_key}`, last 30 days: orphan count and share | Above zero |
| H11 | Values are out of range or frozen | `min`, `max` and the count outside the documented bounds of `{col}`; the run-length recipe in `patterns.md` | Any row out of bounds, or a run longer than the p99 |

One prover per relation runs H1 to H4, H8, H10 and H11 (plus H6 where
incremental); H9 runs per lineage edge; fan-out runs per join. H5 runs on
changed models. H7 applies when a model or column description, or a `Rules`
line in the domain context, states a rule ("one row per site per day",
"never negative", "equals the sum of X"); each rule is an invariant to test.
H10 takes `{entity_key}` and `{parent}` from the model's YAML, its lineage, its
domain context, or its keys and joins. H11 takes the documented
bounds of `{col}`, or a KPI's expected value from the domain context with the
threshold it carries (such as more than 3 times off,
or the wrong sign); the run-length recipe applies where no bounds exist.
Tables above a billion rows take a 14 or 30 day filter or `SAMPLE`.

## Suspicions from data-eng-reviewer

Each suspicion arrives with its own disproof shape. These are the common ones:

| Suspicion | Query that could disprove it |
|---|---|
| This join makes duplicate rows | on the right-hand table: `count(*)` and `count(distinct {join_key})`; on the output: rows against the driving side |
| This filter drops rows it should keep | on the parent: count rows that match the dropped condition |
| The incremental load misses late rows | on the parent: rows with `{date_col}` inside the window that differ from the model, or arrived after the model's cutoff |
| This column has nulls it should not | on the parent: count rows where the column is null |
| This value is out of range | on the parent: `min`, `max`, count outside the range |
| The snapshot has duplicate current rows | keys with more than one row where `dbt_valid_to is null` |
| The lookback window is shorter than the source's lag | on the source: for each day in the last 60, the last time its rows changed; the gap's p99 against the window |
| A test cannot fire | the dead-test recipe in `patterns.md`: last run per test from build history |

## Claims in a pull request

A pull request's text is the author's account. Each claim that names data
("wrong since 2026-03-04", "the source fills in later") becomes a hypothesis
with the number it implies, and gets the same treatment: one query, one
verdict. A contradicted claim is a finding; a supported claim is reported for
`review-verifier` to tag `confirms-pr-claim`.

## Rule for every hypothesis

Write it as a claim with a number and a threshold, run one query with the
`query` role (`references/dq/warehouse-tools.md`), and return proven, not
proven, inconclusive or not applicable. When CI built the pull request into a
PR schema, run the query on the PR relation and the production relation both,
and report the difference (the PR-schema-drift recipe in `patterns.md`).
