# Build vs Buy Evaluation Protocol

Defines how deep-discovery step 9 evaluates build-vs-buy for each capability. Every recommendation must be backed by real package research.

## Core Principle

**Never recommend "build from scratch" without first evaluating what already exists.**

For every capability gap identified in the audit, search for:
1. Open-source packages (pip, npm, cargo, etc.)
2. Managed services / SaaS
3. Framework-native features already available but not used

---

## Research Protocol Per Capability

For each capability in the build-vs-buy list from step 6:

### 1. Search for Existing Solutions

**Early-exit rule: Stop searching when you have 2-4 viable options with verified names and version numbers.**

```
Search categories (use CURRENT YEAR in all queries, search in priority order):

1. Package registry for the project's language (ALWAYS):
   - PyPI/npm/crates.io/Go modules: "{capability keywords}"
   - GitHub: "{capability} {language} library" — sort by stars

2. Framework-native (ALWAYS — check before building custom):
   - "{framework} built-in {capability}"

3. Managed services (IF cloud-hosted):
   - "{capability} as a service {current_year}"
   - "{capability} managed {cloud_provider}"

4. Academic (IF domain has active research — ML, NLP, optimization):
   - "arxiv {capability} {technique}"
```

### 1b. VERIFICATION — Confirm each candidate exists and is maintained

For each candidate found in Step 1:
- Visit the PyPI/npm/crates.io page (WebFetch the registry URL)
- Confirm GitHub/repository URL resolves
- Check last release date (must be within 18 months for "maintained" status)
- Confirm license compatibility with the project

If a package cannot be verified, label it with **UNVERIFIED** in the evaluation heading.

### 1c. ALTERNATIVES — Ensure breadth of evaluation

- `"{primary_candidate} vs alternatives {current_year}"`
- `"{capability} comparison {language} {current_year}"`
- Minimum 2 verified alternatives before making a recommendation

### 1d. Document Search Queries

Every build-vs-buy file must end with a `### Search Queries Used` section listing all WebSearch queries executed during research.

### 2. Evaluate Each Option

For every viable option found (aim for 2-4 options + build-custom):

```markdown
### {Option Name}

**Install:** `pip install {name}=={version}` (or npm, cargo, etc.)
**Repository:** {GitHub URL}
**Stars:** {count} | **Last release:** {date} | **License:** {license}
**Downloads:** {monthly downloads if available}
**Maintained:** {Yes — active commits / Stale — last commit 6+ months ago / Archived}

**What it does:**
{1-2 sentence feature description relevant to our need}

**Feature match:**
- {needed capability 1}: ✅ supported / ⚠️ partial / ❌ missing
- {needed capability 2}: ✅ / ⚠️ / ❌
- {needed capability 3}: ✅ / ⚠️ / ❌

**Integration effort:** {hours / days / weeks}
{What specifically needs to be done to integrate}

**Risks:**
- {dependency risk, breaking changes, vendor lock-in, license compatibility}

**Fits our stack:** {Yes / Partial / No} — {why}

#### Verification Checklist
- [ ] Package exists on registry: {registry_url}
- [ ] Repository URL verified: {github_url}
- [ ] Last release date: {YYYY-MM-DD} (within 18 months: Yes/No)
- [ ] License: {license_name} (compatible: Yes/No)
- [ ] Monthly downloads: {count or "not available"}
- [ ] Search queries documented in "Search Queries Used" section
```

### 3. Evaluate Build Custom

```markdown
### Build Custom

**Effort:** {weeks estimate}
**What to build:**
{Specific description of what custom code would do}

**Maintenance burden:**
{Ongoing: updates, bug fixes, documentation, onboarding new developers}

**Advantages:**
- {Full control over behavior}
- {Perfect fit to existing architecture}
- {No external dependency}

**Disadvantages:**
- {Development time}
- {Maintenance cost}
- {Testing burden}
- {Knowledge concentration risk — what if the author leaves?}
```

### 4. Make a Recommendation

```markdown
## Recommendation

**Use:** {option name}
**Why:** {2-3 sentences — concrete reasoning}
**What to build on top:** {thin integration layer, configuration, tests}
**What this saves:** {estimated effort saved vs build-custom}
**Risk mitigation:** {how to handle the main risk of this choice}
```

---

## Output Format

Each `build-vs-buy/{capability}.md` follows this structure:

```markdown
# {Capability Name}

## Need

{What this capability does and why it's needed}
{Reference: See ../gaps/{relevant-gap}.md}

## Options Evaluated

### 1. {Package/Service Name}
{evaluation per template above}

### 2. {Another Package/Service}
{evaluation}

### 3. Build Custom
{evaluation}

## Recommendation

{recommendation with reasoning}

## Decision Impact

- **Phase affected:** P{NN}-{name} (../phases/{file}.md)
- **Effort if recommended option:** {time}
- **Effort if build custom:** {time}
- **Savings:** {delta}
```

---

## When to Include Build-vs-Buy

Not every capability needs a build-vs-buy file. Create one when:

- The gap requires significant implementation effort (>2 days)
- Multiple viable alternatives exist in the ecosystem
- The capability is commoditized (auth, caching, queuing, monitoring, etc.)
- A pip/npm package with >1K stars exists that solves the problem

Skip build-vs-buy when:
- The capability is trivially small (add one function)
- It's deeply tied to the specific domain (no generic package could help)
- The "build" option is literally 10 lines of code

---

## Common Capability Categories

These are EXAMPLES of capabilities that often have build-vs-buy options. The actual list is derived from the audit findings — not this template.

| Category | Typical Options |
|----------|----------------|
| Authentication | Auth0, Clerk, Firebase Auth, AWS Cognito, custom JWT |
| Caching | Redis, Memcached, framework cache, custom in-memory |
| Job queues | Celery, Dramatiq, APScheduler, AWS SQS, custom |
| Event bus | Redis Streams, Kafka, RabbitMQ, Postgres LISTEN/NOTIFY |
| Search | Elasticsearch, Meilisearch, Typesense, Postgres full-text |
| Guardrails | NeMo Guardrails, Galileo, Guardrails AI, custom |
| Eval/testing | Langfuse, Braintrust, DeepEval, custom |
| UI framework | React, Svelte, Streamlit, Retool, custom |
| Database | Postgres, MySQL, SQLite, managed RDS/Cloud SQL |
| Monitoring | Prometheus+Grafana, Datadog, CloudWatch, custom |
| CI/CD | GitHub Actions, GitLab CI, Jenkins, custom |
| Deployment | Docker Compose, ECS, K8s, serverless |

---

## Quality Check

After generating all build-vs-buy files:

1. **Are package names real?** Verify at least the top recommendation exists (WebSearch check)
2. **Are version numbers current?** Don't cite a 2-year-old version if a newer one exists
3. **Are stars/downloads plausible?** Cross-check if numbers seem off
4. **Is the recommendation justified?** Recommendation text names at least one concrete factor (feature match, effort, license, maintenance).
5. **Does the phase spec reference this file?** Cross-link must exist
