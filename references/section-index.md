# Section Index Creation

Create `<planning_dir>/sections/index.md` to define implementation sections.

## Input Files

- `<planning_dir>/claude-plan.md` - implementation plan
- `<planning_dir>/claude-plan-tdd.md` - test stubs mirroring plan structure

## Output

```
<planning_dir>/sections/
└── index.md
```

## Required Blocks

index.md MUST contain two blocks at the top:

1. **PROJECT_CONFIG** - Project-level settings for implementation
2. **SECTION_MANIFEST** - List of section files to implement

---

## PROJECT_CONFIG Block

**index.md MUST start with a PROJECT_CONFIG block:**

```markdown
<!-- PROJECT_CONFIG
runtime: python-uv
test_command: uv run pytest
END_PROJECT_CONFIG -->
```

### PROJECT_CONFIG Fields

| Field | Required | Description | Examples |
|-------|----------|-------------|----------|
| `runtime` | Yes | Language and tooling | `python-uv`, `python-pip`, `typescript-npm`, `typescript-pnpm`, `rust-cargo`, `go` |
| `test_command` | Yes | Command to run tests | `uv run pytest`, `npm test`, `cargo test`, `go test ./...` |

### PROJECT_CONFIG Rules

- Must be at the TOP of index.md (before SECTION_MANIFEST)
- One field per line, format: `key: value`
- Keys are lowercase with underscores
- Values can contain spaces (e.g., `uv run pytest -v`)
- This block is parsed by setup scripts

### Common Runtime Values

| Runtime | Test Command |
|---------|--------------|
| `python-uv` | `uv run pytest` |
| `python-pip` | `pytest` or `python -m pytest` |
| `typescript-npm` | `npm test` |
| `typescript-pnpm` | `pnpm test` |
| `rust-cargo` | `cargo test` |
| `go` | `go test ./...` |

---

## SECTION_MANIFEST Block

**index.md MUST start with a SECTION_MANIFEST block:**

```markdown
<!-- SECTION_MANIFEST
section-01-foundation
section-02-config
section-03-parser
section-04-api
END_MANIFEST -->

# Implementation Sections Index

... rest of human-readable content ...
```

### SECTION_MANIFEST Rules

- Must be at the TOP of index.md (before any other content)
- One section per line, format: `section-NN-name` (e.g., `section-01-foundation`)
- Section numbers must be two digits with leading zero (01, 02, ... 12)
- Section names use lowercase with hyphens (no spaces or underscores)
- Numbers should be sequential (01, 02, 03...)
- This block is parsed by scripts - the rest of index.md is for humans
- Optional `depends_on:` suffix declares dependencies (see below)

### Dependency Syntax (`depends_on:`)

Sections can declare dependencies on other sections using the `depends_on:` suffix.

**Format:**

```
section-name                           # no dependencies
section-name  depends_on:other-section           # single dependency
section-name  depends_on:dep-one,dep-two         # multiple dependencies
```

**Rules:**
- The `depends_on:` keyword is separated from the section name by whitespace (spaces or tabs)
- Multiple dependencies are comma-separated with NO spaces after commas
- Dependency targets must be valid section names that exist in the same manifest
- Self-dependencies are not allowed
- Circular dependencies are not allowed (A depends on B depends on A)

**Example:**

```markdown
<!-- SECTION_MANIFEST
section-01-foundation
section-02-config              depends_on:section-01-foundation
section-03-parser              depends_on:section-01-foundation
section-04-api                 depends_on:section-02-config,section-03-parser
section-05-integration         depends_on:section-04-api
END_MANIFEST -->
```

In this example:
- `section-01-foundation` is ready immediately (no dependencies)
- `section-02-config` and `section-03-parser` become ready when `section-01-foundation` is complete
- `section-04-api` becomes ready only when BOTH `section-02-config` AND `section-03-parser` are complete
- `section-05-integration` waits for `section-04-api`

**Backward compatibility:** Manifests without any `depends_on:` suffixes continue to work exactly as before.

### Validation

If the manifest is invalid (missing, malformed, or has errors), `check-sections.py` returns `state: "invalid_index"` with error details.

## Human-Readable Content

After the manifest block, include an **Execution Order** (which sections run in parallel) and **Section Summaries** (one line each). See the minimal example below.

## Guidelines

- **Dependency direction**: Earlier sections should not depend on later sections

## Minimal Example

```markdown
<!-- PROJECT_CONFIG
runtime: python-uv
test_command: uv run pytest
END_PROJECT_CONFIG -->

<!-- SECTION_MANIFEST
section-01-foundation
section-02-config              depends_on:section-01-foundation
section-03-parser              depends_on:section-01-foundation
section-04-api                 depends_on:section-02-config,section-03-parser
END_MANIFEST -->

# Implementation Sections Index

## Execution Order
1. section-01-foundation (no dependencies)
2. section-02-config, section-03-parser (parallel after 01)
3. section-04-api (after 02 AND 03)

## Section Summaries
### section-01-foundation — Project setup, config, test fixtures.
### section-02-config — Configuration loading and validation.
### section-03-parser — Input parsing and transformation.
### section-04-api — API endpoints and integration.
```
