# Secondary Repository Freshness

Use this protocol whenever a workflow consults a project other than the
current target repository, whether that project is already local or is cloned
for the run. Cross-project evidence must not silently come from a stale local
checkout.

## Freshness gate

Before reading code, history, or documentation from the secondary repository:

1. Resolve its root with `git -C <path> rev-parse --show-toplevel` and identify
   the remote's default branch with
   `git -C <path> symbolic-ref --quiet --short refs/remotes/origin/HEAD`.
   Strip the `origin/` prefix. If that is unavailable, use `main` only when
   `origin/main` exists; otherwise use the repository's checked-out branch and
   record that no `main` branch was available.
2. If `origin` exists, fetch the selected branch immediately before using the
   repository:

   ```bash
   git -C <path> fetch --prune origin <default-branch>
   ```

   For a newly cloned repository, clone the default branch with its remote
   tracking data and still run the fetch gate above before analysis. A clone's
   creation time is not evidence that its refs are current.
3. Use `origin/<default-branch>` (or the fetched commit ID) as the comparison
   point for the secondary repository. Do not use a local branch merely
   because it has the expected name.
4. Record the repository path, remote, branch, fetched commit, and fetch time
   in the working notes or report. If fetching fails, say so before using the
   repository, include the local commit and its age, and label conclusions
   based on it as potentially stale. Do not claim freshness from a successful
   local checkout alone.

Fetching remote refs only changes Git metadata in the secondary repository; it
must never modify the target working tree. Do not reset, pull, merge, rebase,
checkout, or otherwise alter either repository while gathering context. If the
workflow is explicitly read-only, stop at fetch plus inspection and keep all
analysis read-only. If no remote is configured, use the local history only and
record that limitation.
