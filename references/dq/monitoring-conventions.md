# Monitoring conventions

Loaded by `agents/monitor-reviewer.md`. Scope and operating rules for
recommending checks on dbt sources, curated models, and marts. This is a
project reference, not a substitute for the current Metaplane or dbt
documentation, or for what the active repository already does.

## Review requirements

- **Recommendation only:** identify and explain checks. Never create, update,
  or disable a monitor or test; never edit dbt files, warehouse objects, alert
  rules, or routing.
- **In-scope layers:** sources, curated models, and marts. Staging and
  intermediate models only when the finding is there or a downstream
  recommendation needs them.
- **Evidence:** the dbt project through the repo and the dbt MCP, and
  read-only, bounded, aggregated warehouse queries. Existing Metaplane
  monitors are read from monitors-as-code in the repo; there is no Metaplane
  API connection, so app-created monitors are invisible.
- **Coverage:** one check per distinct signal the evidence justifies; no cap
  per table. Explain any overlap between two checks on the same signal.
- **Alerting:** treat routing as already configured. Tags may route alerts;
  verify their effect before proposing one.

## Naming and tags

When the deployment profile carries a verified naming pattern or tag
vocabulary (`[checks]` in the profile), use it and cite the profile as the
source. Otherwise inspect the active repository and existing monitors for a
consistent current pattern and cite the files.

With neither, the following is a **proposed fallback**, never described as an
established team standard:

- Monitor name: `dbt_<layer>_<model>_<monitor_type>[_<column>]`
- Tags: `monitor_priority_<absolute_must_have|medium|good_to_have>`,
  `dbt_layer_<source|curated|mart>`, `monitor_type_<type>`,
  `dbt_model_<model_name>`

Confirm tag syntax and routing effects before recommending tags.

## Selection rules

- Base each check on dbt tests, contracts, documented rules (the
  domain-context reader's `rules`), lineage, observed failures, and warehouse
  profiles. Keep declared expectations apart from observed values.
- Never invent SLAs, business rules, keys, thresholds, expected row counts,
  or cadence.
- Prefer a native monitor or packaged test over custom SQL for the same
  signal.
- Priority groups stay separate: **Absolute must-have** (a documented SLA,
  contract, test, business-critical consumer, or observed high-impact
  failure), **Medium** (likely to catch a material issue, impact not fully
  established), **Good to have** (diagnostic, weaker evidence, needs owner
  validation). Generic best practice alone never makes a check must-have.

## Metaplane monitors as code

Monitors live in the model's properties YAML under
`meta.metaplane.createMonitors`; Metaplane syncs them from dbt about hourly.
Removing a block disables the monitor.

- Types: `ROW_COUNT`, `FRESHNESS`, `NULLNESS`, `UNIQUENESS`, `CARDINALITY`,
  `MIN`, `MAX`, `MEAN`, `STDDEV`, `SUM`, `PERCENT_ZERO`, `PERCENT_NEGATIVE`,
  `COLUMN_COUNT`, `CUSTOM`.
- Column monitors take `columnMatchers.includeColumns`, plus optional
  `configuration.where`, `groupBy`, `cronSchedule`, and fixed thresholds in
  `manualRules` (`GREATER_THAN`, `GREATER_THAN_EQUALS`, `LESS_THAN`,
  `LESS_THAN_EQUALS`).
- `CUSTOM` monitors need `name` and a unique integer `identifier`, and tune
  with `anomalyRule` (`sensitivity`, `modelBoundsOverride`).

```yaml
models:
  - name: {model}
    meta:
      metaplane:
        createMonitors:
          monitors:
            - PERCENT_ZERO:
                columnMatchers:
                  includeColumns: [{col}]
                configuration:
                  manualRules:
                    - LESS_THAN_EQUALS: { value: {threshold_from_normal_window} }
            - CUSTOM:
                name: "{model}: share of entity-days repeated from prior day"
                identifier: 1
                sql: "select ..."
                configuration:
                  anomalyRule: { sensitivity: 3.0 }
```

## dbt checks (no Metaplane)

- Freshness: a source `freshness` block with `loaded_at_field`,
  `warn_after` and `error_after` from the observed load cadence.
- Grain: `unique` and `not_null` on the key, or
  `dbt_utils.unique_combination_of_columns` for a compound key.
- Values: `accepted_values`, `dbt_utils.accepted_range`, or
  `dbt_expectations` tests when the package is installed.
- Volume and business rules: a singular test under `tests/` returning
  violating rows, with `severity` and `where` config.
- Only packages already in `packages.yml`; a new package is a separate
  recommendation, not a silent dependency.

## Documentation starting points

Re-check when web access is available; the claim-verifier owns that pass.
A review records these as unverified sources:

- Metaplane: monitor types, monitors as code, tags
  (`https://docs.metaplane.dev/docs/monitor-types`,
  `https://docs.metaplane.dev/docs/monitors-as-code`,
  `https://docs.metaplane.dev/docs/tags`)
- dbt: data tests and source freshness
  (`https://docs.getdbt.com/docs/build/data-tests`,
  `https://docs.getdbt.com/reference/resource-properties/freshness`)
