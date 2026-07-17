# deep-plan-enhanced (plugin: `deep`)

A Claude Code plugin for discovering, planning, and implementing complex systems — one unified `/deep` skill with four modes.

```
/deep discovery @path               → system audit + phase specs
/deep plan @spec.md                 → implementation blueprint
/deep implement [@plan-dir/]        → execute sections
/deep auto @phases/                 → autonomous end-to-end (multi-phase plan + implement)
```

Also accepts **inline text** or **no argument** — the plugin synthesizes a spec or objective from git history + codebase context before proceeding.

## Installation

### As a Plugin (Recommended)

```bash
claude plugin marketplace add github:kbichave/skills
claude plugin install deep
```

This registers the `/deep` skill and all hooks automatically.

### As Local Skills

```bash
# Clone
git clone https://github.com/kbichave/skills.git ~/.claude/plugins/deep

# Install Python dependencies
cd ~/.claude/plugins/deep-plan-enhanced && uv sync

# Enable the plugin
# Add to ~/.claude/settings.json:
# "enabledPlugins": { "deep@kbichave-skills": true }
```

### Required Integrations

- **[Beads](https://github.com/plastic-labs/beads)** (`bd`) — issue tracking + multi-agent coordination. Mirrored from the built-in deepstate tracker.
  - macOS: `brew install beads`
  - Linux: `go install github.com/plastic-labs/beads/cmd/bd@latest`
  - Or run the bundled helper: `bash scripts/checks/install-beads.sh`
  - Releases: https://github.com/plastic-labs/beads/releases

## The Workflow

```
/deep discovery    Scan → Topic Enumeration → Research → Coverage Validation → Gaps → Interview → Audit Docs → Build-vs-Buy → Phase Specs
                   (produces system discovery + migration roadmap)

/deep plan         Research → Interview → Spec → Plan → Review → TDD → Sections
                   (produces implementation blueprint for one phase)

/deep implement    Reads sections → Implements in dependency order with quality gates
                   (writes code, tracks progress, enforces standards)

/deep auto         Multi-phase plan + implement loop (parses phasing-overview.md,
                   plans each phase in dependency order then implements before
                   the next phase plans, fully autonomous)
```

## What's Inside

### /deep discovery

A general-purpose system discovery that works on any project — existing codebase, greenfield, or hybrid. Uses a STORM-inspired topic enumeration pattern for guaranteed research coverage.

| Step | What Happens |
|------|-------------|
| Quick Scan | Detect tech stack, structure, domain, codebase size. Write `scan-summary.md` |
| Topic Enumeration | Simulate 3 perspectives (security auditor, new engineer, PM). Generate 12–20 research topics in `research-topics.yaml` with categories, priorities, and questions |
| Deep Research | Parallel agents assigned specific topics from the manifest (2–3 topics each). Each writes `findings/<topic-id>-<slug>.md` |
| Coverage Validation | Run `validate-coverage.py`, spawn gap agents for uncovered topics, loop until ≥80% coverage |
| Auto Gap ID | Identify structural problems, missing capabilities, infrastructure gaps from per-topic findings |
| Stakeholder Interview | Present coverage map (`research-topics.yaml`), expand scope, extract priorities |
| Generate Audit Docs | Parallel subagents write focused per-topic files (one topic per file) |
| Build-vs-Buy Analysis | Per-capability evaluation: pip install vs SaaS vs build custom |
| Phase Specs | Dynamic phases named from gaps (not hardcoded), with dependency graph |
| External Review | Multi-LLM review focused on missing gaps and wrong recommendations |

**Key features:**
- **Topic-driven research** — agents are assigned specific topics, not open-ended missions (STORM-inspired, 25% better coverage breadth)
- **3-perspective enumeration** — security auditor + new engineer + PM viewpoints ensure comprehensive topic coverage
- **Coverage validation loop** — automated gap agents fill uncovered topics until ≥80% threshold
- **Per-topic findings files** — `findings/<topic-id>-<slug>.md` instead of monolithic output
- **Dynamic research depth** — 2 agents for a small CLI, 10+ for a large platform
- **Interview expands scope** — suggests capabilities user didn't ask for based on ecosystem research
- **Build-vs-buy is granular** — real package names with real version numbers per capability
- **Eval-on-write** — auto-scores each generated file, regenerates if below quality threshold

### /deep plan

A multi-step planning pipeline that produces a complete implementation blueprint before any code is written.

| Step | What Happens |
|------|-------------|
| Research | Codebase exploration + web research via subagents |
| Interview | Structured stakeholder Q&A to surface hidden requirements |
| Spec | Synthesized specification from input + research + interview |
| Plan | Detailed implementation plan (prose, not code) |
| External Review | Parallel review by Gemini + OpenAI (or Opus fallback) |
| TDD | Test stub plan mirroring the implementation sections |
| Sections | Self-contained implementation units with dependency graph |

**Inline prompt support:** No spec file required. Run `/deep plan "add OAuth2 login"` and the plugin synthesizes a spec from git history + codebase context, confirms with you, then proceeds.

### /deep implement

Executes the blueprint section by section with strict quality gates.

| Feature | Description |
|---------|-------------|
| **Dependency-aware execution** | Reads `sections/index.md` and implements in the right order |
| **Coding standards** | Reads `references/coding-standards.md` before each section (type-first, security-aware) |
| **Python code reviewer** | 7-criterion reviewer agent: anti-patterns, security, correctness, design, spec-compliance, type-coverage, documentation |
| **Quality gates** | `ruff check`, `mypy --strict`, `bandit -r`, `pytest --cov ≥85%` must pass per section |
| **3-file tracking** | `impl-task-plan.md`, `impl-findings.md`, `impl-progress.md` persist across `/clear` |
| **3-strike error rule** | Same error 3 times with different approaches → escalate to user |
| **Exit summary** | Stop hook requires `impl-summary.md` before allowing exit |

### /deep auto

Fully autonomous multi-phase pipeline. Parses `phasing-overview.md`, plans each phase in dependency order, and implements immediately before the next dependent phase plans. No user interaction required — interviews replaced by self-interview subagents, user reviews auto-closed.

| Feature | Description |
|---------|-------------|
| **Dependency graph parsing** | Reads `## Dependency Graph` section from phasing-overview.md |
| **Parallel phase detection** | Independent phases (e.g. P02 and P03 both depending on P01) not mutually blocked |
| **Discovery bridge** | Later phases read discovery findings (max 5 per phase), only research phase-specific gaps via `references/discovery-bridge.md` |
| **Interview passthrough** | Discovery interview transcript passed to all phases as context |
| **Plan-then-implement chain** | Each phase implements before its dependents plan, so later specs reflect actual codebase |

## Session Storage

All session state is written to `~/.claude/marketplace/deep-plan-enhanced/sessions/` — project working trees stay clean. No `.deepstate/`, `sessions/`, or `audit/` directories are created in your project.

```
~/.claude/marketplace/deep-plan-enhanced/sessions/
  <project-slug>/                    ← e.g. my-api-a3f9c1
    index.json                       ← lists all sessions for this project
    <session-prefix>/                ← first 8 chars of DEEP_SESSION_ID
      .deepstate/state.json
      deep_plan_config.json
      claude-plan.md
      sections/
      findings/
      research-topics.yaml
      ...
```

Legacy sessions that already exist inside project directories are detected via file markers and left in place — existing work is never lost.

## Hooks

| Hook | When | What |
|------|------|------|
| **SessionStart** | Session begins | Captures session ID + plugin root for task isolation |
| **PostToolUse** | After Write/Edit | Nudges agent to update progress files |
| **Stop** | Agent tries to exit | Requires implementation summary; blocks exit if sections incomplete |
| **SubagentStop** | Section/audit-doc writer finishes | Extracts content and writes file to disk |

## Architecture

### State Management

| Concern | Storage | System |
|---------|---------|--------|
| Workflow step progress | `.deepstate/state.json` | `DeepStateTracker` |
| Workflow steps → Beads CLI (optional) | Beads CLI (`bd`) | `BeadsSyncTracker` |
| Research topics + coverage + findings | `research-topics.yaml` | `ResearchTopicStore` |
| Session index across projects | `index.json` | `ResearchTopicStore` |

### Library Modules (`scripts/lib/`)

| Module | Purpose |
|--------|---------|
| `deepstate.py` | JSON dependency graph tracker with atomic writes |
| `beads_sync.py` | Write-through wrapper that mirrors to Beads CLI |
| `research_topics.py` | `ResearchTopicStore` — flat-file backend for research topics |
| `workflow.py` | Workflow issue factory — creates task graphs for each mode |
| `tasks.py` | Task definitions, IDs, and dependency edges for all workflow modes |
| `config.py` | Session config (read/write `deep_plan_config.json`) |
| `sections.py` | Section manifest parser (`index.md` → section list with dependencies) |
| `prompts.py` | External review prompt templates (Gemini, OpenAI, Opus fallback) |

### Reference Files (`references/`)

| File | Used By |
|------|---------|
| `audit-research-protocol.md` | Discovery: scan + deep research waves |
| `audit-topic-enumeration.md` | Discovery: STORM-inspired 3-perspective topic generation |
| `audit-coverage-validation.md` | Discovery: coverage gap detection + targeted gap agents |
| `audit-interview-protocol.md` | Discovery: stakeholder interview |
| `audit-doc-writing.md` | Discovery: parallel audit document generation |
| `audit-build-vs-buy.md` | Discovery: build-vs-buy evaluation per capability |
| `audit-phasing.md` | Discovery: dynamic phase spec generation |
| `auto-spec-synthesis.md` | All modes: inline prompt → spec/objective synthesis |
| `coding-standards.md` | Implement: Python quality standards (types, security, testing) |
| `research-protocol.md` | Plan: codebase + web research protocol |
| `interview-protocol.md` | Plan: stakeholder interview |
| `plan-writing.md` | Plan: plan document generation |
| `external-review.md` | Plan + Discovery: multi-LLM review orchestration |
| `tdd-approach.md` | Plan: TDD stub generation |
| `section-index.md` | Plan: section index creation |
| `section-splitting.md` | Plan: section splitting with dependency graph |
| `context-check.md` | Plan: context window management |
| `discovery-bridge.md` | Auto/Plan: reuse discovery research + interview for non-first phases |

### Agent Definitions (`agents/`)

| Agent | Purpose |
|-------|---------|
| `code-reviewer.md` | Sole multi-language reviewer (Python/TS/Go): pack-scoped rule families, 4-phase workflow, cross-cutting + language reference library, report-only dead-code. Absorbed `python-code-reviewer` |
| `opus-plan-reviewer.md` | Plan review fallback when external LLMs unavailable |
| `audit-doc-writer.md` | Focused audit document generation per topic |
| `section-writer.md` | Self-contained section content generation |

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Python 3.11+
- (Optional) Gemini API key or OpenAI API key for external plan review
- [Beads](https://github.com/plastic-labs/beads) (`bd`) — required. Install: `brew install beads` (macOS) / `go install github.com/plastic-labs/beads/cmd/bd@latest` (Linux) / `bash scripts/checks/install-beads.sh` (bundled helper)

## Tests

```bash
uv run pytest tests/ -q
```

437 tests covering deepstate tracker, beads sync, workflow factory, session setup, section generation, hook behavior, research topic store, skill structure, integration lifecycle, and transcript parsing.

## What's Different From the Originals

This project combines patterns from [deep-plan](https://github.com/piercelamb/deep-plan), [planning-with-files](https://github.com/OthmanAdi/planning-with-files), and research from [STORM](https://arxiv.org/abs/2402.14207) (Stanford), [Deep-Research-skills](https://github.com/Weizhena/Deep-Research-skills), and [python-skills](https://github.com/wdm0006/python-skills).

| Feature | Source |
|---------|--------|
| Unified `/deep` skill replacing 5 separate skills | New (v1.5.0) |
| Inline prompt → spec synthesis (no file required) | New (v1.5.0) |
| STORM-inspired topic enumeration + coverage validation | STORM paper + Deep-Research-skills |
| Per-topic findings files with coverage tracking | New (v1.5.0) |
| Python coding standards + 7-criterion code reviewer | python-skills patterns |
| Quality gates: ruff + mypy --strict + bandit + pytest --cov ≥85% | python-skills patterns |
| Session storage isolation (`~/.claude/marketplace/...`) | New (v1.5.0) |
| Session isolation (concurrent sessions don't overwrite) | New |
| PostToolUse progress nudge hooks | planning-with-files pattern |
| Stop hook with exit summary requirement | planning-with-files pattern |
| Section-by-section execution in dependency order | deep-plan sections + plan-cascade pattern |
| 3-file disk tracking (task plan, findings, progress) | planning-with-files pattern |
| Quality gates per section (tests, no stubs) | plan-cascade pattern |
| 3-strike error escalation | planning-with-files pattern |

## Bundled Skills

This plugin vendors a curated subset of [mattpocock/skills](https://github.com/mattpocock/skills) (MIT). Full attribution is in [`NOTICE`](NOTICE).

**Bundled in this plugin (`deep:*` namespace):**

| Skill | Slash command | Use |
|-------|--------------|-----|
| `deep` | `/deep` | The discovery/plan/implement/auto pipeline. |
| `code-review` | `/code-review` | Standalone pack-scoped review via the `code-reviewer` agent. |
| `humanizer` | `/humanizer` | Strips AI-writing tells from prose outputs. |

**Installed from [mattpocock/skills](https://github.com/mattpocock/skills)** — run `uv run scripts/checks/install-mattpocock-skills.py` once (re-run to update):

| Skill | Use |
|-------|-----|
| `grilling` | Sequential decision-tree interview with recommended answers. Default style for `/deep plan` interviews. |
| `grill-me` | Standalone grill entry point. |
| `handoff` | Session-handoff summary skill. |

**Global skills `/deep` invokes opportunistically (inline fallbacks when missing):**

| Skill | Use |
|-------|-----|
| `tdd` | Tracer-bullet test-driven development. Cited from `references/coding-standards.md`. |
| `domain-modeling` | Domain glossary extraction. Always-on topic in `/deep discovery`. |
| `codebase-design` | Shallow-vs-deep module audit. Auto-prompts during `/deep plan` and `/deep implement`. |
| `obsidian-vault` | Note management. Backing store for the knowledge vault below. |
| `write-a-skill` | Standalone meta-skill for extending the plugin. |

See [`docs/skills-bundled.md`](docs/skills-bundled.md) for the full table including when each is auto-invoked vs. manually invocable.

## Knowledge Vault

`/deep` persists long-lived knowledge (ubiquitous-language glossary, architecture decision records, curated discovery findings) into an Obsidian vault. The vault path resolves in this order:

1. `$DEEP_OBSIDIAN_VAULT` if set
2. `~/Obsidian/deep-plan/` if it already exists
3. The first `/deep` run otherwise prompts once: *create vault at `~/Obsidian/deep-plan/`?* (yes / specify path / no). The "no" answer is remembered for the session.

When no vault is configured, glossary terms and ADRs land in `~/.claude/projects/<slug>/memory/` instead — graceful degrade. A `vault-curator` subagent runs at the end of every mode to decide which artifacts deserve long-lived storage and which stay local. See [`docs/vault.md`](docs/vault.md).

## Skill-aware Routing

Between major workflow phases, `/deep` consults a `skill-router` subagent that enumerates other skills installed on the machine (user, plugin, or project scope) and decides which ones are relevant to the current step. High-confidence matches auto-invoke (e.g., `claude-api` when a file imports `anthropic`); medium-confidence matches surface a single multi-select prompt; low-confidence matches log only. Side-effect skills (`pr-reply`, `schedule`, `pptx`, `internal-comms`, etc.) never auto-invoke. See [`docs/skill-routing.md`](docs/skill-routing.md).

## Acknowledgments

- [deep-plan](https://github.com/piercelamb/deep-plan) by Pierce Lamb — the planning pipeline this project extends (MIT License)
- [planning-with-files](https://github.com/OthmanAdi/planning-with-files) by Ahmad Adi — discipline patterns (attention manipulation, filesystem-as-memory, completion verification)
- [plan-cascade](https://github.com/Taoidle/plan-cascade) by Taoidle — quality gate and dependency-aware execution patterns
- [STORM](https://arxiv.org/abs/2402.14207) by Stanford — outline-first research enumeration for coverage breadth
- [Deep-Research-skills](https://github.com/Weizhena/Deep-Research-skills) by Weizhena — research skill patterns for discovery agents
- [python-skills](https://github.com/wdm0006/python-skills) by wdm0006 — Python coding standards and advanced quality gates
- [mattpocock/skills](https://github.com/mattpocock/skills) by Matt Pocock — grilling / grill-me / handoff installed verbatim from upstream by `scripts/checks/install-mattpocock-skills.py` (MIT License, see [`NOTICE`](NOTICE))

## License

MIT
