---
name: no-op-remover
version: 1.0.0
description: |
  Find and remove no-ops from instruction and prompt files — lines a model
  already obeys by default, so they burn context to say nothing. TRIGGER when
  the user says "remove no-ops", "strip no-ops", "hunt no-ops", "kill filler
  instructions", "tighten this prompt/skill", or asks to cut instructions that
  change no behavior. Scans SKILL.md, agent definitions, CLAUDE.md/AGENTS.md,
  prompt templates, and docs; proposes delete/strengthen fixes; applies only
  what the user approves. NOT for humanizing prose (use humanizer) or for
  dead code in source files (use code-review).
license: MIT
compatibility: claude-code opencode
allowed-tools:
  - Read
  - Edit
  - Grep
  - Glob
  - Bash
  - AskUserQuestion
---

# No-op Remover

Strip instructions a model already follows by default. Every such line costs
attention budget and buys nothing — deleting it makes the rules that DO change
behavior land harder.

## What a no-op is

A line whose presence versus absence produces the same model behavior. The
test for each line: **does it change what the model does versus the default?**
If not, it is a no-op.

| No-op (cut it) | Why it fails the test |
|---|---|
| "Be thorough." | The model is already thorough-ish; the word adds nothing. |
| "Think carefully before answering." | Default behavior. |
| "You are a helpful assistant." | Obeyed by default; states the obvious. |
| "Respond accurately and truthfully." | No model aims for the opposite. |
| "Please ensure high quality output." | Unfalsifiable, changes nothing. |
| "Use your best judgment." | Grants what the model already does. |

The fix is not always deletion. When a **weak leading word** is doing the
work, replace it with a stronger one rather than adding text:

- "be thorough" → "relentless"
- "try to be concise" → "one sentence, no preamble"
- "carefully review" → "re-read every changed line"

A line that names a concrete, non-default constraint is NOT a no-op — keep it:
"Cap the list at 5 items", "Output JSON only, no fences", "Never call the
network", "Ask before deleting files".

## Flow

### 1. Resolve scope

Determine what to scan:

- **User named a file** → that file.
- **User named a directory** → all in-scope files under it (recurse).
- **User named a repo / "this repo" / "everything"** → repo root, recurse.
- **User named a diff base** (`main`, a branch, "my changes") →
  `git diff <base> --name-only`, filter to in-scope types.
- **Bare invocation, no scope** → ask (AskUserQuestion): this file / this
  directory / whole repo / just my changes. Do not guess.

### 2. In-scope file types

Only instruction and prompt surfaces — where prose instructs a model or reader:

- `**/SKILL.md`, agent definitions (`agents/*.md`, `**/*.agent.md`)
- `CLAUDE.md`, `AGENTS.md`, hook-prompt files
- Prompt templates and inline model-instruction strings (`prompts/**`,
  `*.prompt`, `*.jinja`/`*.j2` used as prompts)
- `docs/**/*.md` and other instructional Markdown

Skip source logic, config, data, and lockfiles. List anything skipped with the
reason so scope is auditable.

### 3. Detect — sentence by sentence

Read each in-scope file in full. Run the no-op test on **each sentence in
isolation**, not just each line — no-ops hide mid-paragraph. For every hit
record: `file:line`, the verbatim sentence, the fix (delete, or the stronger
replacement word), and one clause on why it changes no behavior.

Be aggressive but honest: only flag a line you can argue the model already
obeys. A line you are unsure about is not a no-op — leave it.

### 4. Triage — propose, apply on approval

Deleting prose is destructive, so confirm before editing.

1. Present hits via AskUserQuestion, batched up to 4 per call, grouped by
   file. Each option shows `file:line`, the verbatim sentence, and the fix.
   Choices per hit:
   - **Delete** — remove the whole sentence (do not trim to fewer words).
   - **Strengthen** — apply the stronger-word replacement.
   - **Skip** — leave it.
   - **Edit** — user supplies their own replacement (via "Other"/notes).
2. Apply only approved edits, with the Edit tool. When deleting, remove the
   entire sentence and fix up surrounding whitespace/punctuation so the
   paragraph still reads. Never leave a dangling fragment.

### 5. Report

After applying, print a short summary: per file, how many no-ops found,
deleted, strengthened, skipped. Note the net line/character reduction. Show
the skipped list so nothing is silently dropped.

## Rules

1. Verbatim quote for every hit — never paraphrase what you are proposing to
   delete. If you cannot quote it from the file, it is not a real hit.
2. Delete whole sentences, not words. Trimming a no-op to a shorter no-op
   still pays load for nothing.
3. Strengthen weak leading words instead of adding qualifiers.
4. Concrete non-default constraints are never no-ops — keep every real rule.
5. Apply nothing without approval. This skill proposes; the user decides.
6. Stay in instruction/prompt files. Code comments and dead code are out of
   scope (route those to `code-review`).

## Reference

The no-op test comes from Matt Pocock's `writing-great-skills`
(github.com/mattpocock/skills): "a line the model already obeys by default,
so you pay load to say nothing." This skill applies that test to a chosen
scope and gates every edit behind user approval.
