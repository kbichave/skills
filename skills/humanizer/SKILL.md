---
name: humanizer
version: 3.0.0
description: |
  Remove signs of AI-generated writing from text. TRIGGER when user says "humanize",
  "make this sound human", "remove AI writing", "de-slop", or asks to edit/review text
  to sound more natural. Also triggers on slide decks, roadmap docs, card headers and
  chart labels, blog posts and landing pages, not only prose. Other skills call it as
  an embedded step (review comments, PR text). Based on Wikipedia's "Signs of AI
  writing" plus the stylometric findings in Reinhart et al. (PNAS 2025). Detects and
  fixes: inflated symbolism, promotional language, superficial -ing analyses, vague
  attributions, em dashes, rule of three and balanced doublets, verbless nominal
  decks, bold label openers, AI vocabulary words, passive voice, negative
  parallelisms, staccato punchlines, aphorism formulas, and filler phrases. Never
  invents facts to make a sentence sound more specific.
license: MIT
compatibility: claude-code opencode
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
---

# Humanizer: Remove AI Writing Patterns

Detail loads on demand from `references/`. Read the files the task needs (see Reference Files) rather than working from memory.

## Why the tells cluster

Most of the 37 patterns are symptoms of one habit. Reinhart et al. scored LLM output against human corpora on Biber's feature set and found instruction-tuned models sit far along the informational end of the involved-versus-informational dimension. They write noun-heavy, information-dense text **even when prompted to write casually**. Nominalizations go up, verbs and hedges and asides go down, and clause length flattens toward a uniform middle.

Copula avoidance, verbless decks, nominalization, balanced parallelism and label openers all pack more nouns per clause and fewer finite verbs. Ask one question of any suspect sentence:

> Where did the verb go, and why is every clause the same length?

- **Prefer the finite verb.** If a sentence has no verb, or the verb does no work ("serves as", "represents", "constitutes"), fix that first. Several other tells fall away once the verb is back.
- **Rhythm is measurable.** Uniform sentence length is the most reliable machine signature. The Mechanical Scan in `references/surfaces-and-scan.md` checks it.

## Your Task

1. **Check the surface.** Body prose, or a non-prose surface (headings, card headers, chart labels, table cells, bullets, commit messages). Fragments are a defect in the first and correct in the second. See `references/surfaces-and-scan.md`.
2. **Pick the content type** (below). It changes how nine patterns apply.
3. **Identify patterns** from `references/patterns.md`. Check `references/detection.md` before calling a passage a tell. Look for clusters, not isolated hits.
4. **Preserve the information, not the shape.** Every claim in the source survives, but depth need not be uniform: compress the dull parts, dwell where a human would, merge or split paragraphs freely. When keeping information and mirroring structure conflict, information wins.
5. **Never invent facts.** The rewrite contains no fact, name, number, date, quote or citation absent from the source or the user. Swap a vague claim for a specific one only when the specific comes from there. If a sentence needs real-world detail to work, ask for it or write the plain version. Opinions and reactions are voice, not facts, and may be added where `references/voice.md` says voice applies. (Fiction is exempt.)
6. **Match the voice.** A writing sample beats everything. Without one, use the Default Voice Profile in `references/voice.md` for the user's own messages and comments, and plain neutral prose for reference and technical docs.

## Content Types

- **Reference / technical / legal / internal docs** (wikis, specs, policies, BU-facing write-ups): plain, neutral and factual *is* the human voice. Apply every pattern at full strength. Default when unclear.
- **Long-form marketing** (blog posts, landing pages, product pages, marketing emails): the copy must still persuade, stay scannable, carry keywords and end on a call to action. Detect it from the content (hero headline plus CTA, or intro plus H2s plus a repeated keyword); the user can override. Nine patterns switch from "delete" to "make it concrete and keep the sell": §1, §2, §4, §10, §15, §16, §17, §18, §25, each with an "In marketing copy" note. The no-fabrication rule is *stricter* here: never invent a stat, testimonial, customer, logo, count or capability. Also apply `references/seo-preservation.md`.

## Invocation Modes

- **Pasted text (default).** Run the full loop and deliver per Output.
- **File mode.** The user points at a file. Run the loop internally, then rewrite the file in place with only the final text. Humanize prose only: leave code blocks, frontmatter, data and link targets untouched. Report a short summary of changes plus the scan numbers, not the whole rewrite.
- **Embedded mode.** Another skill or agent calls this as one step (review-panel comments, a PR description, a commit body). Run the loop internally and return only the final text: no draft, no audit, no scan numbers. Never return something longer than the input unless the caller asked for it; review-panel re-cuts to its own budget.

## Reference Files

Paths are relative to this file.

- **`references/patterns.md`**: the catalog of 37 numbered tells with before/after examples and the marketing carve-outs. Read before any rewrite. `§N` points here.
- **`references/surfaces-and-scan.md`**: Non-Prose Surfaces rules and the Mechanical Scan (greps plus four counts). Read before any rewrite over about five sentences, and for any deck, card, chart or table.
- **`references/detection.md`**: false positives and signs of human writing to preserve. Read before deciding a passage is a tell.
- **`references/voice.md`**: voice calibration from a sample, the Default Voice Profile, and when to add personality.
- **`references/seo-preservation.md`**: keyword, heading, link, image and CTA constraints. Read in marketing mode.

## Process

1. Read the input in full. Decide surface, content type and invocation mode.
2. Run the Mechanical Scan and record the numbers before reading for style, so the counts are not coloured by what you expect. Skip the four counts for inputs under about five sentences; the greps still apply.
3. Identify every pattern instance, checked against `references/detection.md`.
4. Write a **draft rewrite**. It reads naturally aloud, varies sentence length on purpose, prefers simple constructions (is/are/has), and keeps a finite verb in every body-prose sentence.
5. Audit the draft with two questions, answered briefly:
   - "What makes the below so obviously AI generated?"
   - "Does the rewrite state any fact, name, number, date, quote or citation that isn't in the source?" A fabrication is a defect even when it sounds more human than the vague original.
6. Revise into the **final rewrite**. Scan it for `—` and `–` and replace every one (§14), unless a voice sample uses them. In marketing mode run the integrity check in `references/seo-preservation.md`.
7. Re-run the scan. If sentence-length deviation did not move, go back to step 4: the edit was cosmetic.

## Output

Pasted-text mode delivers:

1. Scan numbers before
2. Draft rewrite
3. Audit bullets (still-AI tells, plus any fabrication found)
4. Final rewrite
5. Scan numbers after, next to the before numbers
6. Short summary of changes (optional)

File and embedded modes deliver only what their mode says.

## Source

Patterns 1 to 29 come from [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup, drawn from thousands of observed instances. Key insight from that page: "LLMs use statistical algorithms to guess what should come next. The result tends toward the most statistically likely result that applies to the widest variety of cases."

Patterns 30 to 33, Non-Prose Surfaces and the Mechanical Scan rest on Reinhart, Markey, Laudenbach, Pantusen, Yurko, Weinberg and Brown, ["Do LLMs write like humans? Variation in grammatical and rhetorical styles"](https://www.pnas.org/doi/10.1073/pnas.2422455122), PNAS 122(8), 2025 ([arXiv:2410.16107](https://arxiv.org/abs/2410.16107)).

Patterns 34 to 37, the no-fabrication rule, content types, invocation modes, detection guidance and SEO preservation are adapted from [content-humanizer](https://github.com/Matt-Payne/content-humanizer) 2.12.1 (MIT, derived from blader/humanizer by Siqi Chen).
