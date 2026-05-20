# Resuming After Compaction

After `/clear`, context compaction, or a new session targeting an existing planning dir:

1. **Restore plugin root.** Re-run `bash ${DEEP_PLUGIN_ROOT}/scripts/checks/validate-env.sh`. If `DEEP_PLUGIN_ROOT` is unset, locate it via the SessionStart hook context.

2. **Locate planning dir.**
   - If user provided `@path`, use it (or its parent if a file).
   - Otherwise read `~/.claude/.deep-plan-active`.

3. **Prime status.** Call `tracker.prime()`, then read `{planning_dir}/.deepstate/prime.md` for a compact summary of what's done, what's ready, what's blocked.

4. **Find next step.** Call `tracker.ready()` — returns the next unblocked step.

5. **Implement mode only:** read `impl-progress.md` for current section status, `impl-findings.md` for caveats, `impl-mutations.md` for plan changes.

6. **Reference files** live at `{plugin_root}/references/`.

If `tracker.prime()` shows the workflow complete: print completion summary and stop.

If state.json is corrupted (parse error): tell the user, do not auto-recreate. Reinitialization is destructive and should be a deliberate user action.
