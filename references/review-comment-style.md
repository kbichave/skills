# Review comment voice and length

Loaded by `review-panel` SKILL.md step 8, before any finding text is humanized
into a marker or posted to a PR. Governs externalized comment lines only: the
report file under `~/.claude/code-reviews/` and the chat render keep the full
`issue`, `fix`, `prediction`, `evidence` and `teach` wording.

**Comment voice.** Severity sets the register, and the humanizer applies it:

- **Blocking (`high`)**: direct and unhedged. State the defect, then the fix.
  No riddles on correctness or security, no softening a real bug into a
  suggestion.
- **Non-blocking (`medium`/`low`/improvements)**: phrase as a question that
  carries its own reasoning, so the author can answer with a constraint you
  did not know about. "Any reason not to `X` here?" / "Could this use `Y`?" /
  "Why the second `COALESCE`, can this return NULL?" A reviewer who cannot be
  wrong is not reviewing. Pair the question with `teach.why` in one line.
  Never stack hedges: one "I think" or one question mark, not both plus
  "maybe".

**Length budget (hard cap).** A long comment is an unread comment. Every
externalized comment fits:

| Comment | Budget |
|---|---|
| Blocking (`high`) | 2 sentences max, then the suggestion block |
| Non-blocking (`medium`/`low`/improvement) | 1 sentence, then the block |
| Summary comment | verdict line + 1 bullet per blocking issue, ≤15 words each |

Write to the cap, do not trim to it. Compressed style:

- **Lead with the defect, not the setup.** No "I noticed that", "It looks like",
  "One thing I wanted to flag". First words name the thing that is wrong.
- **Drop every adverb and intensifier**: "slightly", "really", "quite",
  "currently", "simply", "just", "potentially", "unnecessarily".
- **Cut the verbs you can.** Noun phrase beats a clause: "Off-by-one on the
  upper bound" not "It appears that this is off by one on the upper bound".
- **Never restate what the code does.** The author wrote it; the diff is on
  screen. State only what is wrong with it.
- **No praise sandwich, no closing pleasantry.** "Nice work otherwise" is
  noise in a review.
- **The suggestion block carries the fix**, so the prose never describes the
  same change in words as well.

Yes: "Off-by-one: `range(n)` skips the last row." / "Any reason not to
`USING (site_id)` here? The `ON` clause duplicates the join key."
No: "I noticed that the loop here is currently using `range(n)`, which
potentially means the very last row might not actually get processed."

This is a rendering cap only. Never shorten the report file or the panel JSON
to satisfy it, and never drop a finding to stay inside it: the cap trims words
per comment, not the finding count.
