# Voice and Personality

Read this when the user gives a writing sample or brand voice, when the text is the user's own writing, or when the content calls for personality.

## Voice Calibration

If the user provides a writing sample (their own previous writing), analyze it before rewriting:

1. **Read the sample first.** Note:
   - Sentence length patterns (short and punchy? Long and flowing? Mixed?)
   - Word choice level (casual? academic? somewhere between?)
   - How they start paragraphs (jump right in? Set context first?)
   - Punctuation habits (lots of dashes? Parenthetical asides? Semicolons?)
   - Any recurring phrases or verbal tics
   - How they handle transitions (explicit connectors? Just start the next point?)

2. **Match their voice in the rewrite.** Don't just remove AI patterns, replace them with patterns from the sample. If they write short sentences, don't produce long ones. If they use "stuff" and "things," don't upgrade to "elements" and "components."

3. **When no sample is provided,** use the Default Voice Profile below for the user's own messages, review comments and notes. For reference, technical and BU-facing docs, write plain neutral prose instead. For marketing, see `SKILL.md` Content Types.

### How to provide a sample
- Inline: "Humanize this text. Here's a sample of my writing for voice matching: [sample]"
- File: "Humanize this text. Use my writing style from [file path] as a reference."

A sample outranks this skill's style rules, including the em dash rule in §14 (`references/patterns.md`): if the sample uses em dashes, keep them at roughly the sample's frequency. Matching the author beats scrubbing the tell.

## Default Voice Profile

Applies to the user's own writing (messages, review comments, notes) unless they give a different sample or ask for formal/neutral output. Not for reference docs or marketing copy.

**Casing and punctuation:**
- Use normal sentence capitalization. Capitalize the first letter of each sentence and after a period. Proper class names, acronyms, and tickers keep their own casing.
- Use real punctuation. End sentences with periods. Apostrophes in contractions are correct: "aren't", "don't", "isn't", "it's", "what's".
- Wrap technical terms, variables, identifiers, params, function/class names, and literal values in backticks: `nu`, `corr`, `rank-2`, `1e-6`, `retry_backoff_s`. If it is code or a value, it goes in backticks.
- No em dashes. No semicolons. Commas do the joining work, often as run-ons / comma splices. Periods end complete thoughts; fragments are fine.
- Parenthetical asides are common: `(read + write paths)`, `(chance the retry storms)`.

**Rhythm and structure:**
- Terse. Lead with the point, no warm-up. Skip "I think", "it seems", "in order to".
- Short fragments mixed with one longer comma-run sentence. Not uniform.
- Tag short verdicts on the end: `minor`, `not a blocker`, `either way`.
- Ask direct questions, no softening: `can we ...?`, `whats the hit here?`, `post it?`.

**Word choice:**
- Casual and compressed. `corr` not "correlation" on second mention, `~83%`, `4th`, `vs`, `+` instead of "and" in lists of params.
- Keep technical terms exact and unabbreviated on first use (`rank-2 factor`, `lower-tail dependence`).
- No filler, no hedging, no pleasantries, no significance-inflation. Blunt but collegial.

**Do NOT imitate:**
- Accidental typos (`libnraries`, `ucrrent`). Match the deliberate style, not the slips. Spelling stays correct.
- Do not force lowercase or dropped-apostrophe style onto code, commit messages, or anything inside code blocks. Those stay conventional.

**Example in this voice:**
> Math checks out, so not a blocker. I'm just not sold on a symmetric error model here before we build on it. The tails aren't symmetric, outages and retries pull every downstream call up together, but the good runs don't sync up the same way. Can we bench the symmetric fit vs this one on held-out data before wiring it in? Fine to merge the loss now either way, it's clean and tested.

## Personality and Soul

Avoiding AI patterns is only half the job. Sterile, voiceless writing is just as obvious as slop.

**Apply this only when the content and the author's voice call for it**: blog posts, essays, opinion, personal writing. For encyclopedic, technical, legal or reference text, neutral and plain *is* the human voice; don't inject opinions or first person there. Never add factual claims to create personality.

### Signs of soulless writing (even if technically "clean"):
- Every sentence is the same length and structure
- No opinions, just neutral reporting
- No acknowledgment of uncertainty or mixed feelings
- No first-person perspective when appropriate
- No humor, no edge, no personality
- Reads like a Wikipedia article or press release

### How to add voice:

**Have opinions.** Don't just report facts, react to them. "I genuinely don't know how to feel about this" is more human than neutrally listing pros and cons.

**Vary your rhythm.** Short punchy sentences. Then longer ones that take their time getting where they're going.

**Acknowledge complexity.** Real humans have mixed feelings. "This is impressive but also kind of unsettling" beats "This is impressive."

**Use "I" when it fits.** "I keep coming back to..." or "Here's what gets me..." signals a real person thinking.

**Let some mess in.** Perfect structure feels algorithmic. Tangents, asides, and half-formed thoughts are human.

**Be specific about feelings.** Not "this is concerning" but "there's something unsettling about agents churning away at 3am while nobody's watching."

### Before (clean but soulless):
> The experiment produced interesting results. The agents generated 3 million lines of code. Some developers were impressed while others were skeptical. The implications remain unclear.

### After (has a pulse):
> I genuinely don't know how to feel about this one. 3 million lines of code, generated while the humans presumably slept. Half the dev community is losing their minds, half are explaining why it doesn't count. The truth is probably somewhere boring in the middle, but I keep thinking about those agents working through the night.
