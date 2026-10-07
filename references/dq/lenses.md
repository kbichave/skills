# Lenses

Look at the node through every lens. A lens yields a hypothesis when the code,
the context, or a preview gives a reason; otherwise record "n/a" and why. The
patterns under each lens are what a data quality engineer checks; they are
questions, not known answers.

## 1. Grain and uniqueness
- Declared key not unique, or null in part of the key.
- Semantic grain differs from the dbt key.
- Fan-out: a join to a non-unique right side, a union of overlapping sets, or a
  lateral flatten multiplies rows.
- Dedupe with a weak tie-break (`row_number` ordered by a non-unique column)
  keeps an arbitrary row.

## 2. Identity, mapping, and referential integrity
- Keys that fail to map (to a site, product, location) and are dropped by an
  inner join or kept as null or a default ('UNDEFINED', -1, 0).
- Orphans: child keys with no parent, parent keys never used.
- One key mapped to several targets, or several keys to one.
- Identifier formats that differ across systems (leading zeros, prefixes, case,
  padding, ZIP+4 versus 5-digit).

## 3. Time, freshness, and incremental logic
- Stale or frozen: the latest date stops advancing, or the table's last change
  is older than its schedule.
- Frozen history: old rows never change though the source corrects them.
- Late-arriving or revised rows that the incremental filter never re-reads.
- Lookback windows shorter than how late data really arrives.
- Partial periods: the newest day or hour loaded before it was complete.
- Gaps: missing days or hours for an active entity; duplicate days.
- Timezone: UTC dates used as local business days, or the reverse; DST hours.
- Observed and forecast rows overlapping, or a gap at the boundary.
- Hard-coded dates, years, or filters that silently age out.

## 4. Completeness and volume
- Row count per day dropping, spiking, or stopping.
- Entities (sites, locations) disappearing or appearing in bulk.
- A filter (`where`, inner join, `qualify`) removing more rows than expected.
- Soft-deleted source rows kept, or live rows removed.

## 5. Values and distributions
- Nulls where the meaning requires a value; null rate changing over time.
- Nulls turned into zero or a default (`COALESCE(x, 0)`), or zero meaning both
  "none" and "missing".
- Sentinel values (0, -1, 9999, 1900-01-01, empty string) standing in for
  missing data.
- Out-of-range or physically impossible values; wrong sign.
- Unit or scale changes (cents and dollars, F and C, percent and fraction).
- Constant or near-constant columns; a column suddenly all one value.
- Forward-fill or interpolation hiding gaps (long runs of an identical value).
- Distribution drift: mean, spread, or category mix shifting after a date.
- Outliers that are errors rather than real events.

## 6. Categories and logic
- Category strings, codes, or flags that the logic matches exactly; a new,
  renamed, or differently cased value falls through a `CASE` or string match.
- `CASE` without `ELSE`, or an `ELSE` that hides unknowns.
- Flags that disagree with the values they summarise (a "has_x" flag versus
  the measure of x).
- Cross-column rules broken (min greater than max, end before start, total less
  than its parts).

## 7. Aggregation and consistency
- Measures summed, averaged, or maxed against their meaning; averaging ratios.
- Totals at this grain disagreeing with the finer grain they come from.
- Two relations of the same object (V1 and V2, business-logic layer and mart, dev and prod)
  disagreeing at a matched grain.
- Mixed populations (different entity universes) combined in one measure.

## 8. Schema and types
- Columns added, dropped, or renamed upstream without the model following.
- Casts that truncate, round, or fail silently (`TRY_CAST` to null).
- Numeric precision or string length too small for real values.

## 9. Upstream propagation and reconciliation
- A problem seen here that already exists in the parent or raw source.
- This node adding, hiding, or amplifying a parent's problem.
- Reconciliation: for the same key and date, this node holds a null, a
  different value, or no row where its parent or raw source holds a value. Test
  it by joining the two relations on the key over a bounded window, and split
  the result by age of the row (recent versus older) and by column.
- Reconcile against the raw source, not only the direct parent, when the parent
  loads the same way (the same incremental filter, lookback, or dedupe): both
  can be wrong together, and a parent-to-child check then passes while the bug
  is real.

## 10. Guards and environment
- No test on the key, on mapping coverage, or on freshness.
- Tests at `warn` severity, with `where` filters, or that cannot fail.
- A check that passes on today's data but would miss the failure mode above.
- Wrong environment: a prod model reading a dev or UAT relation, or the reverse.

## Onset and breadth

For any symptom (a null rate, a mismatch, a freeze, a value shift):
- **Onset**: find when it started, with one query by month or day (null rate,
  mismatch rate, or the first bad date), and set that date against the node's
  git history and job history. A start date that matches a code change, a job
  change, or a source change points to the cause.
- **Breadth**: name every measure the same logic touches (all the columns built
  by the same filter, join, or pivot, not only the first one noticed) and test
  them together in one query, split by column.

## Competing causes

When one symptom (a null regression, a freeze, a count drop) has more than one
plausible cause in the code or lineage, write each cause as its own hypothesis,
link them to each other and to the symptom, and give each a test whose result
tells the causes apart (for example: is the value present in the parent for the
same key? did it change after the first load? does the miss follow the join
key or the load date?). Do not settle on one cause from code reading alone.

Rank by impact on the consumers in the context times how strongly the evidence
points to it.
