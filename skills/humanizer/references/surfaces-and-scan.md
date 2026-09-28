# Surfaces and Mechanical Scan

## Non-Prose Surfaces

The patterns above assume paragraphs. Much AI-flavored writing is not paragraphs, and blanket fixes make it worse. A chart label with a finite verb is padding, not humanity.

Apply this instead, by surface:

| Surface | Fragments allowed | What to fix instead |
|---|---|---|
| Headings, deck standfirsts | Yes | Repetition of shape across sibling headings. Significance inflation. |
| Card and callout headers | Yes | Every header taking the form `adjective noun, qualifier`. Vary length and shape. |
| Chart labels, bar tags, legends | Yes | Tags that assert importance rather than state content. Prefer a number, a date or a noun. |
| Table cells | Yes | Judgment words where a value belongs. See §33 in `references/patterns.md`. |
| Bullet lists | Yes | Matched-length bullets. Real lists are ragged. Three bullets when there are two ideas. |
| Body paragraphs | No | Everything above. Restore the finite verb. |
| Commit messages, code comments | Yes | Leave conventional style alone. Do not humanize into prose. |

Two rules that apply everywhere:

1. **Vary shape across siblings.** Uniformity is the tell, not brevity. If six card headers are all noun-phrase-plus-comma-plus-qualifier, rewrite three of them into a different shape even if each one is fine alone.
2. **Do not humanize into vagueness.** A tag that says `0.50 price changes per item-site-year` beats a tag that says `sparse variation, measured`. Specificity is the most human thing available.

## Mechanical Scan

Do this before the subjective pass. A model grading its own prose is the weakest step in this skill, so start with things that can be counted.

Grep for these. Any hit is a candidate, not a verdict:

| What | Pattern |
|---|---|
| Em and en dashes | `—\|–\| -- ` |
| Negative parallelism | `not just\|isn't just\|not only\|rather than a\|not a .*, but a` |
| Copula avoidance | `serves as\|stands as\|functions as\|represents a\|marks a\|boasts\|features a` |
| Superficial -ing tails | `, (underscoring\|highlighting\|reflecting\|emphasizing\|showcasing\|demonstrating\|contributing)` |
| AI vocabulary | `delve\|tapestry\|pivotal\|intricate\|underscore\|meticulous\|seamless\|robust\|leverage\|crucial` |
| Persuasive authority | `the real question\|at its core\|what really matters\|fundamentally,` |
| Bold label openers | `^\*\*[A-Z][a-z]+[.:]\*\*` |
| Curly quotes | `[’“”]` |
| Rhetorical openers | `^(Honestly\?\|Look,\|Here's the thing\|The thing is\|Real talk)` |
| Aphorism formulas | `is the (language\|currency\|architecture) of\|becomes a trap` |
| Speculative gap-fill | `maintains a low profile\|not publicly available\|it is believed that\|likely (grew up\|studied)` |
| Numeral anaphora | `\bone \w+ and one \w+\|\bno \w+ and no \w+` |

Then count four things by hand or by script:

- **Mean words per sentence.** Over about 22 in body prose is dense.
- **Standard deviation of sentence length.** This is the important one. Under about 6 means the rhythm is flat, which no amount of word-swapping will fix. Human writing mixes 4-word sentences with 40-word ones.
- **Nominalization rate.** Words ending in `-tion, -ment, -ness, -ity, -ance` per 1,000 words. A spike means the verbs have been turned into nouns.
- **Verbless line share.** Lines in body prose with no finite verb. In paragraphs this should be near zero.

Report before and after numbers when you finish. If sentence-length deviation did not move, the rewrite was cosmetic.
