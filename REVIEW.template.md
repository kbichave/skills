# Review policy

Copy this to `REVIEW.md` in a repo's root to tune how `deep:code-review` reports
there. Every section is optional; delete what you do not need.

This file says **how this repo wants review reported**. It does not define what
counts as a defect — that lives in the plugin's rule packs, which are versioned
with the plugin and shared across repos.

## Exclusions

Paths that are never worth a finding. Generated code, vendored dependencies,
snapshots. Glob syntax; a leading `**/` matches at any depth.

- `**/generated/**`
- `**/*.pb.go`
- `vendor/**`

## Excluded rules

Rule IDs this repo does not want reported, because something else already
enforces them. Use sparingly and say why — a suppressed rule is invisible.

- `ENG-004`  <!-- line length: ruff enforces this in CI, don't double-report -->

## Nit cap

How many nits reach chat and a PR comment. The rest are summarized as a count
with a pointer to the full report, which always contains everything.

`none` disables the cap.

5
