# Audit Data Collection Protocol

This step runs between Quick Scan and Topic Enumeration. Its purpose is to collect empirical codebase data that grounds research questions in evidence rather than speculation. The output is `analysis-data.yaml` in the planning directory.

## Anti-Goals

- Do NOT install tools not already present in the project environment.
- Do NOT run test suites — only `pytest --co -q` for inventory.
- Do NOT modify project code. This step is read-only.
- Do NOT block discovery if collection fails. Partial results are acceptable.

---

## Step 1: Read scan-summary.md for Language Detection

Read `{planning_dir}/scan-summary.md`. Extract the primary language from the "Primary Language & Framework" section. Normalize to lowercase (`python`, `javascript`, `typescript`, `go`, `rust`). If detection fails or the file is missing, set `language_detected: unknown` and proceed with git analysis only.

---

## Step 2: Git Analysis (Always Runs)

All commands operate within the target repository root. Git is assumed available.

| Analysis | Command | Parsing |
|----------|---------|---------|
| File churn | `git log --since="6 months" --name-only --pretty="" \| sort \| uniq -c \| sort -rn \| head -30` | `<count> <filepath>` per line. Top 30. |
| Contributors | `git shortlog -sn --since="6 months" \| head -10` | `<count>\t<name>` per line. Top 10. Compute `concentration` = top contributor commits / total commits. |
| Commit frequency | `git log --format="%ai" --since="6 months" \| wc -l` | Single integer. `avg_per_week` = total / 26. |
| Repo age | `git log --reverse --format="%ai" \| head -1` | Parse date. |
| Test-to-code ratio | See below | `ratio` = test_files / source_files |

**Young repo handling:** If the first commit is less than 6 months old, replace `--since="6 months"` with full history. Record `git_window: "full history"`.

**If repo age check times out:** Default to full history.

**Test file detection patterns:**
- Python: `test_*.py`, `*_test.py`
- JS/TS: `*.spec.ts`, `*.spec.js`, `*.test.ts`, `*.test.js`
- Go: `*_test.go`
- Rust: files in `tests/` directory

**Timeout:** 30 seconds per command. Record partial results if timeout.

---

## Step 3: Language-Specific Tool Execution (Conditional)

Skip if `language_detected` is `unknown`. For polyglot repos, run tools for up to 2 detected languages.

### Python

| Tool | Command |
|------|---------|
| ruff | `ruff check --output-format json . 2>&1` |
| mypy | `mypy . --no-error-summary 2>&1` |
| pytest inventory | `pytest --co -q 2>&1` |
| pip-audit | `pip-audit --format json 2>&1` |

### JavaScript / TypeScript

| Tool | Command |
|------|---------|
| eslint | `npx eslint --format json . 2>&1` |
| tsc | `npx tsc --noEmit 2>&1` |
| npm audit | `npm audit --json 2>&1` |

### Go

| Tool | Command |
|------|---------|
| go vet | `go vet ./... 2>&1` |
| staticcheck | `staticcheck ./... 2>&1` |

### Rust

| Tool | Command |
|------|---------|
| cargo clippy | `cargo clippy --message-format json 2>&1` |

### Execution Protocol (per tool)

1. Run with 30-second timeout.
2. **Exit 127** (command not found) → `unavailable_tools` with `not_installed`.
3. **Timeout** → kill, `unavailable_tools` with `timeout`.
4. **Non-zero exit WITH parseable output** → **success** (violations ARE the data). Parse and record in `tool_results`. Exception: `mypy` exit 2 = fatal error → record in `unavailable_tools`.
5. **Non-zero exit, no parseable output** → `unavailable_tools` with `error`.

### Parsing Flexibility

Try JSON parsing first. Fall back to line counting. Fall back to `total_issues: <line count>`. Truncate raw output to 100KB before parsing.

---

## Step 4: Write analysis-data.yaml

Write to `{planning_dir}/analysis-data.yaml`:

```yaml
metadata:
  generated: "<ISO 8601 timestamp>"
  git_window: "6 months"           # or "full history"
  repo_age_days: <int>
  primary_language: "<detected>"
  collection_duration_seconds: <float>

language_detected: "<python|javascript|typescript|go|rust|unknown>"

git_analysis:
  file_churn:
    top_files:
      - path: "<relative path>"
        changes: <int>
    total_files_changed: <int>
  contributors:
    - name: "<name>"
      commits: <int>
    concentration: <float>           # 0.0 to 1.0
  commit_frequency:
    total_commits: <int>
    avg_per_week: <float>
  test_to_code_ratio:
    test_files: <int>
    source_files: <int>
    ratio: <float>

tool_results:
  <tool_name>:
    exit_code: <int>
    duration_seconds: <float>
    summary:
      total_violations: <int>
      by_category: {}

unavailable_tools:
  - name: "<tool>"
    reason: "<not_installed|timeout|error>"
```

**Size constraint:** Under 200 lines.

---

## Step 5: Failure Handling

If the entire step fails (not a git repository), write a minimal `analysis-data.yaml` with metadata only and empty sections. Discovery must not be blocked.
