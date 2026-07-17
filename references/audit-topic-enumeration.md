# Audit Topic Enumeration

Generates the research coverage manifest (`research-topics.yaml`) that acts as the topic contract for all subsequent research agents. Done after Quick Scan, before Deep Research.

## Purpose

Without a topic contract, research agents write what they find interesting rather than what the audit needs. STORM research showed that outline-first enumeration improves topic breadth coverage by 25%. This step is that outline.

## Step 1: Read scan-summary.md

Read `{planning_dir}/scan-summary.md` (written by Quick Scan). Extract:
- Project type and domain
- Primary language(s) and framework(s)
- Rough scale (files, lines, services)
- Any obviously missing areas flagged by the scan

Also check `{planning_dir}/objective.md` if it exists (from inline prompt auto-spec).

## Step 2: Read Empirical Data

Read `{planning_dir}/analysis-data.yaml` if it exists. This file is produced by the `empirical-data-collection` step. **If the file is missing, skip this step entirely** — no error, no warning. Topic enumeration works without it (fallback to perspective-only mode).

Extract empirical signals and generate targeted questions:

| Signal | Condition | Priority | Example Questions |
|--------|-----------|----------|-------------------|
| Dependency vulnerabilities | audit tool finds issues | 1 (highest) | "What known vulnerabilities exist in dependencies?" / "Is there a dependency update policy?" |
| Zero tests | test inventory returns 0 items | 2 | "Why are there no tests?" / "What is the testing strategy?" |
| Low test-to-code ratio | ratio < 0.3 | 3 | "What areas lack test coverage?" / "What is the test-writing convention?" |
| High file churn | Any file with >20 changes in window | 4 | "Why does `<file>` change so frequently? Is it a god module?" |
| Contributor concentration | Top contributor >80% of commits | 5 | "What is the bus factor for this project?" / "Is knowledge siloed?" |
| High lint violations | >=50 total violations | 6 | "What code quality patterns are most prevalent?" / "Is there a linting policy?" |
| Type errors | mypy/tsc reports errors | 7 | "How is type safety enforced?" / "Are type errors tracked or ignored?" |

**Rules:**
- Generate 3-8 empirical questions when data is available
- Each signal produces at most 2-3 questions
- Cap at 8 total empirical questions (stop after cap even if more signals fire)
- Process signals in priority order above
- Tag every empirical question with `source: empirical`
- Thresholds are guidance, not hard rules — use judgment for borderline cases

## Step 3: Detect Project Domain

Using data from Steps 1-2, classify the project domain to select appropriate expert perspectives.

### Signal Table

| Signal | Domain | Example Indicators |
|--------|--------|--------------------|
| ML frameworks in dependencies | `ml-pipeline` | torch, tensorflow, sklearn, xgboost, mlflow, wandb |
| dbt project structure | `data-warehouse` | `dbt_project.yml`, `models/*.sql`, Snowflake/BigQuery refs |
| Frontend framework in package.json | `web-frontend` | react, vue, angular, svelte, next |
| HTTP server framework | `web-api` | FastAPI, Flask, Django, Express, route definitions |
| Infrastructure-as-Code files | `infrastructure` | `.tf` files, `k8s/`, `terraform/`, Pulumi, CloudFormation |
| CLI entry point with arg parsing | `cli-tool` | argparse, click, clap, `console_scripts`, `bin/` |
| CI/CD pipelines as primary artifacts | `devops-platform` | `.github/workflows/`, `Jenkinsfile`, minimal app code |

### Detection Algorithm

1. Parse signals from `scan-summary.md` and `analysis-data.yaml`
2. Match against the signal table — each match votes for a domain
3. 2+ matching signals → select domain with `confidence: high`
4. 1 matching signal → select with `confidence: medium`
5. No matches or tie → fall back to `default` with `confidence: low`
6. Record `detected_domain` and `domain_confidence` for Steps 4 and 6

## Step 3.5: Quality-family lenses

Resolve the quality rule-packs active for this target and emit one mandatory
audit topic per active family. This guarantees discovery covers the same quality
dimensions the implement phase will gate on (no blind spots).

```python
from lib.pack_router import detect_signals, resolve_packs
signals = detect_signals(Path(target_root), spec_text=objective_text)
resolution = resolve_packs(signals, Path(plugin_root) / "references" / "quality")
```

For each active pack, read `references/quality/<pack>/index.md` `provides_rules`
and add a coverage topic per family (tag `source: quality-lens`):

| Family | Lens topic |
|--------|-----------|
| ENG | "Where is complexity/dead-code/duplication concentrated?" |
| SEC | "What are the authn/authz, injection, and secret-handling risks?" |
| TEST | "What is failure-path + diff coverage; where are the gaps?" |
| ERR | "How are errors handled — fail-closed, swallowed, or silent?" |
| API | "What public contracts exist; what would a breaking change hit?" |
| DATA | "Migration reversibility, transactions, N+1 hot paths?" |
| OBS | "Logging/metrics/correlation coverage on critical paths?" |
| CONC | "Shared-state, timeout/retry, idempotency risks?" |
| DEP/SUPPLY | "Dependency CVEs, license, provenance, CI-action pinning?" |
| CFG/IAC | "Config/secret handling; container/IaC misconfig?" |
| LLM | "Prompt-injection, tool-call allowlisting, output handling?" |

- `core` families (ENG/SEC/TEST/ERR) are always added.
- Triggered families are added only when their pack is active for the target.
- These topics are mandatory — merge with, do not replace, perspective topics.

## Step 4: Load Domain Perspectives

1. Using `detected_domain` from Step 3.5, load `{plugin_root}/references/perspectives/{detected_domain}.md`
2. The file contains 3 expert perspectives, each with 8-12 domain-specific questions
3. Generate topic questions from the loaded perspectives — each perspective's questions feed into Step 5's manifest building
4. If the perspective file is missing, fall back to `{plugin_root}/references/perspectives/default.md`

The `default.md` file contains the original Security Auditor, New Engineer, and Product Manager perspectives, so projects that don't match a specific domain get identical behavior to the previous version.

## Step 5: Build the Manifest

1. Collect all questions from all three perspectives
2. Group similar questions under a single topic (dedup)
3. Assign each topic:
   - `id`: `rt-NN` (two-digit, e.g. `rt-01`)
   - `topic`: short descriptive name (3–6 words)
   - `category`: one of `architecture | data-model | api | security | performance | testing | observability | dependencies | deployment | ubiquitous-language`
   - `priority`: `high` (core to identifying gaps), `medium` (supporting), `low` (nice-to-know)
   - `questions`: 2–4 specific questions the research agent must answer
   - `status`: `pending`
   - `findings_file`: `null`

Target **12–20 topics** for a typical project. Fewer for tiny projects, more for large distributed systems.

### Always-on: ubiquitous-language

Every audit run includes a topic with `category: ubiquitous-language`.
This is not gated on domain detection — it is cheap and the value
compounds across runs. The topic glues to:

* The global `domain-modeling` skill (successor to the formerly vendored
  `ubiquitous-language`) for the extraction approach
* `scripts/lib/glossary.py` (`extract_terms`, `diff_merge`) for the
  mechanical scan and merge
* The `vault-curator` subagent for persistence (`<vault>/glossary/<slug>/`
  when the vault is configured, otherwise
  `~/.claude/projects/<slug>/memory/ubiquitous-language.md`)

Topic shape:

```yaml
- id: rt-NN
  topic: "Ubiquitous Language"
  category: ubiquitous-language
  priority: medium
  questions:
    - "What domain nouns appear repeatedly in code, dbt models, schema YAML, and class names?"
    - "Which terms have multiple definitions in different parts of the codebase (conflict candidates)?"
    - "Which terms are likely shared with other projects in this user's portfolio (promotion candidates)?"
  status: pending
  findings_file: null
```

The `audit-doc-writer` agent assigned to this topic must call
`scripts.lib.glossary.extract_terms` (via Bash) on the repository, then
diff-merge into the destination chosen by the curator. Do not rewrite
existing definitions — flag conflicts and let the user resolve them.

## Step 6: Write research-topics.yaml

Write to `{planning_dir}/research-topics.yaml`:

```yaml
metadata:
  project: <project name from scan-summary>
  generated: <ISO date>
  detected_domain: <domain from Step 3.5, e.g. "ml-pipeline" or "default">
  domain_confidence: <"high", "medium", or "low">
  perspectives:
    - <perspective_1_name from loaded file>
    - <perspective_2_name from loaded file>
    - <perspective_3_name from loaded file>
  empirical_signals: 0    # number of signals that fired, 0 if no data
  total: <N>
  covered: 0
  coverage_pct: 0

topics:
  - id: rt-01
    topic: "Authentication & Authorization"
    category: security
    priority: high
    questions:
      - "What authentication mechanism is used (JWT, sessions, OAuth)?"
      - "How are permissions enforced? Is there RBAC or ABAC?"
      - "What happens when a token expires or is revoked?"
    status: pending
    findings_file: null

  - id: rt-02
    topic: "Database Schema & Migrations"
    category: data-model
    priority: high
    questions:
      - "What is the primary data store? What is the schema structure?"
      - "How are migrations managed? Is there a rollback strategy?"
      - "Are there N+1 query risks or missing indexes?"
    status: pending
    findings_file: null

  # ... continue for all topics
```

## Rules

1. **Do not skip categories** — every category should have at least one topic unless the project genuinely has nothing in that area (e.g. a CLI tool has no deployment category — mark it explicitly as N/A in metadata).
2. **Questions must be specific and answerable** — not "How does security work?" but "What input validation exists at API boundaries?".
3. **Priority is about gap-finding impact**, not importance to the project. Security topics are often high priority even for small projects because they're commonly missed.
