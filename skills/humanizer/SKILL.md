---
name: humanizer
version: 2.6.0
description: |
  Remove signs of AI-generated writing from text. TRIGGER when user says "humanize",
  "make this sound human", "remove AI writing", "de-slop", or asks to edit/review text
  to sound more natural. Also triggers on slide decks, roadmap docs, card headers and
  chart labels, not only prose. Based on Wikipedia's "Signs of AI writing" plus the
  stylometric findings in Reinhart et al. (PNAS 2025). Detects and fixes: inflated
  symbolism, promotional language, superficial -ing analyses, vague attributions,
  em dash overuse, rule of three and balanced doublets, verbless nominal decks,
  bold label openers, AI vocabulary words, passive voice, negative parallelisms,
  and filler phrases.
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

This guide is based on Wikipedia's "Signs of AI writing" page, maintained by WikiProject AI Cleanup, plus the measured findings in Reinhart et al., "Do LLMs write like humans? Variation in grammatical and rhetorical styles," PNAS 122(8), 2025.

## Why the tells cluster

Most of the 33 patterns below are symptoms of one underlying habit. Reinhart et al. measured LLM output against human corpora on Biber's feature set and found instruction-tuned models sit far along the informational end of the involved-versus-informational dimension. They are noun-heavy and information-dense **even when prompted to write casually**. Nominalizations go up, verbs and hedges and asides go down, and clause length flattens toward a uniform middle.

That is the root cause. Copula avoidance, verbless decks, nominalization, balanced parallelism and label openers are all ways of packing more nouns per clause and fewer finite verbs. Fixing them one at a time works, but it is faster to ask a single question of any suspect sentence:

> Where did the verb go, and why is every clause the same length?

Two consequences for how you edit:

- **Prefer the finite verb.** If a sentence has no verb, or the verb is doing no work ("serves as", "represents", "constitutes"), that is usually the thing to fix first. Several other tells fall away once the verb is back.
- **Rhythm is a measurable tell, not a matter of taste.** Uniform sentence length is the most reliable machine signature. See the Mechanical Scan below for the check.

## Your Task

When given text to humanize:

1. **Check the surface** - Body prose, or one of the cases in Non-Prose Surfaces. Fragments are a defect in the first and correct in the second
2. **Count before you read** - Run the Mechanical Scan and note the four numbers
3. **Identify AI patterns** - Scan for the patterns listed below
4. **Rewrite problematic sections** - Replace AI-isms with natural alternatives
5. **Preserve meaning** - Keep the core message intact
6. **Maintain voice** - Match the intended tone (formal, casual, technical, etc.)
7. **Add soul** - Don't just remove bad patterns; inject actual personality
8. **Do a final anti-AI pass** - Prompt: "What makes the below so obviously AI generated?" Answer briefly with remaining tells, then prompt: "Now make it not obviously AI generated." and revise
9. **Count again** - Re-run the scan. Flat sentence-length deviation means the edit was cosmetic


## Voice Calibration (Optional)

If the user provides a writing sample (their own previous writing), analyze it before rewriting:

1. **Read the sample first.** Note:
   - Sentence length patterns (short and punchy? Long and flowing? Mixed?)
   - Word choice level (casual? academic? somewhere between?)
   - How they start paragraphs (jump right in? Set context first?)
   - Punctuation habits (lots of dashes? Parenthetical asides? Semicolons?)
   - Any recurring phrases or verbal tics
   - How they handle transitions (explicit connectors? Just start the next point?)

2. **Match their voice in the rewrite.** Don't just remove AI patterns - replace them with patterns from the sample. If they write short sentences, don't produce long ones. If they use "stuff" and "things," don't upgrade to "elements" and "components."

3. **When no sample is provided,** default to the Default Personal Voice Profile (Kshitij) section below. Use the generic PERSONALITY AND SOUL voice only if the user asks for formal/neutral output or a different audience.

### How to provide a sample
- Inline: "Humanize this text. Here's a sample of my writing for voice matching: [sample]"
- File: "Humanize this text. Use my writing style from [file path] as a reference."


## Default Personal Voice Profile (Kshitij)

Unless the user provides a different sample or explicitly asks for formal/neutral output, default to this voice.

**Casing and punctuation:**
- Use normal sentence capitalization. Capitalize the first letter of each sentence and after a period. Proper class names, acronyms, and tickers keep their own casing.
- Use real punctuation. End sentences with periods. Apostrophes in contractions are correct: "aren't", "don't", "isn't", "it's", "what's".
- Wrap technical terms, variables, identifiers, params, function/class names, and literal values in backticks: `nu`, `corr`, `betainc/icdf`, `rank-2`, `MultivariateNormalDistributionLoss`, `1e-6`, `_PIT_EPS`. If it is code or a value, it goes in backticks.
- No em dashes. No semicolons. Commas do the joining work, often as run-ons / comma splices. Periods end complete thoughts; fragments are fine.
- Parenthetical asides are common: `(gasoline + diesel)`, `(chance total margin drops)`.

**Rhythm and structure:**
- Terse. Lead with the point, no warm-up. Skip "I think", "it seems", "in order to".
- Short fragments mixed with one longer comma-run sentence. Not uniform.
- Tag short verdicts on the end: `minor`, `not a blocker`, `either way`.
- Ask direct questions, no softening: `can we ...?`, `whats the hit here?`, `post it?`.

**Word choice:**
- Casual and compressed. `corr` not "correlation" on second mention, `~83%`, `4th`, `vs`, `+` instead of "and" in lists of params.
- Keep technical terms exact and unabbreviated on first use (`betainc/icdf`, `rank-2 factor`, `lower-tail dependence`).
- No filler, no hedging, no pleasantries, no significance-inflation. Blunt but collegial.

**Do NOT imitate:**
- Accidental typos (`libnraries`, `ucrrent`). Match the deliberate style, not the slips. Spelling stays correct.
- Do not force lowercase or dropped-apostrophe style onto code, commit messages, or anything inside code blocks. Those stay conventional.

**Example in this voice:**
> Math checks out, so not a blocker. I'm just not sold on symmetric `student-t` for fuel before we build the model on it. Our tails aren't symmetric: closures, storms, and holidays pull every grade down together, but good days don't sync up the same way. Can we bench `gaussian` vs this `t` on held-out joint metrics before wiring up the model? Fine to merge the loss now either way, it's clean and tested.


## PERSONALITY AND SOUL

Avoiding AI patterns is only half the job. Sterile, voiceless writing is just as obvious as slop.

### Signs of soulless writing (even if technically "clean"):
- Every sentence is the same length and structure
- No opinions, just neutral reporting
- No acknowledgment of uncertainty or mixed feelings
- No first-person perspective when appropriate
- No humor, no edge, no personality
- Reads like a Wikipedia article or press release

### How to add voice:

**Have opinions.** Don't just report facts - react to them. "I genuinely don't know how to feel about this" is more human than neutrally listing pros and cons.

**Vary your rhythm.** Short punchy sentences. Then longer ones that take their time getting where they're going.

**Acknowledge complexity.** Real humans have mixed feelings. "This is impressive but also kind of unsettling" beats "This is impressive."

**Use "I" when it fits.** "I keep coming back to..." or "Here's what gets me..." signals a real person thinking.

**Let some mess in.** Perfect structure feels algorithmic. Tangents, asides, and half-formed thoughts are human.

**Be specific about feelings.** Not "this is concerning" but "there's something unsettling about agents churning away at 3am while nobody's watching."

### Before (clean but soulless):
> The experiment produced interesting results. The agents generated 3 million lines of code. Some developers were impressed while others were skeptical. The implications remain unclear.

### After (has a pulse):
> I genuinely don't know how to feel about this one. 3 million lines of code, generated while the humans presumably slept. Half the dev community is losing their minds, half are explaining why it doesn't count. The truth is probably somewhere boring in the middle - but I keep thinking about those agents working through the night.


## CONTENT PATTERNS

### 1. Undue Emphasis on Significance, Legacy, and Broader Trends

**Words to watch:** stands/serves as, is a testament/reminder, a vital/significant/crucial/pivotal/key role/moment, underscores/highlights its importance/significance, reflects broader, symbolizing its ongoing/enduring/lasting, contributing to the, setting the stage for, marking/shaping the, represents/marks a shift, key turning point, evolving landscape, focal point, indelible mark, deeply rooted

**Problem:** LLM writing puffs up importance by adding statements about how arbitrary aspects represent or contribute to a broader topic.

**Before:**
> The Statistical Institute of Catalonia was officially established in 1989, marking a pivotal moment in the evolution of regional statistics in Spain. This initiative was part of a broader movement across Spain to decentralize administrative functions and enhance regional governance.

**After:**
> The Statistical Institute of Catalonia was established in 1989 to collect and publish regional statistics independently from Spain's national statistics office.


### 2. Undue Emphasis on Notability and Media Coverage

**Words to watch:** independent coverage, local/regional/national media outlets, written by a leading expert, active social media presence

**Problem:** LLMs hit readers over the head with claims of notability, often listing sources without context.

**Before:**
> Her views have been cited in The New York Times, BBC, Financial Times, and The Hindu. She maintains an active social media presence with over 500,000 followers.

**After:**
> In a 2024 New York Times interview, she argued that AI regulation should focus on outcomes rather than methods.


### 3. Superficial Analyses with -ing Endings

**Words to watch:** highlighting/underscoring/emphasizing..., ensuring..., reflecting/symbolizing..., contributing to..., cultivating/fostering..., encompassing..., showcasing...

**Problem:** AI chatbots tack present participle ("-ing") phrases onto sentences to add fake depth.

**Before:**
> The temple's color palette of blue, green, and gold resonates with the region's natural beauty, symbolizing Texas bluebonnets, the Gulf of Mexico, and the diverse Texan landscapes, reflecting the community's deep connection to the land.

**After:**
> The temple uses blue, green, and gold colors. The architect said these were chosen to reference local bluebonnets and the Gulf coast.


### 4. Promotional and Advertisement-like Language

**Words to watch:** boasts a, vibrant, rich (figurative), profound, enhancing its, showcasing, exemplifies, commitment to, natural beauty, nestled, in the heart of, groundbreaking (figurative), renowned, breathtaking, must-visit, stunning

**Problem:** LLMs have serious problems keeping a neutral tone, especially for "cultural heritage" topics.

**Before:**
> Nestled within the breathtaking region of Gonder in Ethiopia, Alamata Raya Kobo stands as a vibrant town with a rich cultural heritage and stunning natural beauty.

**After:**
> Alamata Raya Kobo is a town in the Gonder region of Ethiopia, known for its weekly market and 18th-century church.


### 5. Vague Attributions and Weasel Words

**Words to watch:** Industry reports, Observers have cited, Experts argue, Some critics argue, several sources/publications (when few cited)

**Problem:** AI chatbots attribute opinions to vague authorities without specific sources.

**Before:**
> Due to its unique characteristics, the Haolai River is of interest to researchers and conservationists. Experts believe it plays a crucial role in the regional ecosystem.

**After:**
> The Haolai River supports several endemic fish species, according to a 2019 survey by the Chinese Academy of Sciences.


### 6. Outline-like "Challenges and Future Prospects" Sections

**Words to watch:** Despite its... faces several challenges..., Despite these challenges, Challenges and Legacy, Future Outlook

**Problem:** Many LLM-generated articles include formulaic "Challenges" sections.

**Before:**
> Despite its industrial prosperity, Korattur faces challenges typical of urban areas, including traffic congestion and water scarcity. Despite these challenges, with its strategic location and ongoing initiatives, Korattur continues to thrive as an integral part of Chennai's growth.

**After:**
> Traffic congestion increased after 2015 when three new IT parks opened. The municipal corporation began a stormwater drainage project in 2022 to address recurring floods.


## LANGUAGE AND GRAMMAR PATTERNS

### 7. Overused "AI Vocabulary" Words

**High-frequency AI words:** Actually, additionally, align with, crucial, delve, emphasizing, enduring, enhance, fostering, garner, highlight (verb), interplay, intricate/intricacies, key (adjective), landscape (abstract noun), pivotal, showcase, tapestry (abstract noun), testament, underscore (verb), valuable, vibrant

**Problem:** These words appear far more frequently in post-2023 text. They often co-occur.

**Before:**
> Additionally, a distinctive feature of Somali cuisine is the incorporation of camel meat. An enduring testament to Italian colonial influence is the widespread adoption of pasta in the local culinary landscape, showcasing how these dishes have integrated into the traditional diet.

**After:**
> Somali cuisine also includes camel meat, which is considered a delicacy. Pasta dishes, introduced during Italian colonization, remain common, especially in the south.


### 8. Avoidance of "is"/"are" (Copula Avoidance)

**Words to watch:** serves as/stands as/marks/represents [a], boasts/features/offers [a]

**Problem:** LLMs substitute elaborate constructions for simple copulas.

**Before:**
> Gallery 825 serves as LAAA's exhibition space for contemporary art. The gallery features four separate spaces and boasts over 3,000 square feet.

**After:**
> Gallery 825 is LAAA's exhibition space for contemporary art. The gallery has four rooms totaling 3,000 square feet.

Related: this pattern covers replacing "is" with something fancier. For dropping the verb altogether, see #30.


### 9. Negative Parallelisms and Tailing Negations

**Problem:** Constructions like "Not only...but..." or "It's not just about..., it's..." are overused. So are clipped tailing-negation fragments such as "no guessing" or "no wasted motion" tacked onto the end of a sentence instead of written as a real clause.

**Before:**
> It's not just about the beat riding under the vocals; it's part of the aggression and atmosphere. It's not merely a song, it's a statement.

**After:**
> The heavy beat adds to the aggressive tone.

**Before (tailing negation):**
> The options come from the selected item, no guessing.

**After:**
> The options come from the selected item without forcing the user to guess.


### 10. Rule of Three Overuse

**Problem:** LLMs force ideas into groups of three to appear comprehensive.

**Before:**
> The event features keynote sessions, panel discussions, and networking opportunities. Attendees can expect innovation, inspiration, and industry insights.

**After:**
> The event includes talks and panels. There's also time for informal networking between sessions.

The three-part version is the loudest, but the underlying habit is matched clause shape at any length. See #31 for the two-part case, which slips past most readers and most detectors.


### 11. Elegant Variation (Synonym Cycling)

**Problem:** AI has repetition-penalty code causing excessive synonym substitution.

**Before:**
> The protagonist faces many challenges. The main character must overcome obstacles. The central figure eventually triumphs. The hero returns home.

**After:**
> The protagonist faces many challenges but eventually triumphs and returns home.


### 12. False Ranges

**Problem:** LLMs use "from X to Y" constructions where X and Y aren't on a meaningful scale.

**Before:**
> Our journey through the universe has taken us from the singularity of the Big Bang to the grand cosmic web, from the birth and death of stars to the enigmatic dance of dark matter.

**After:**
> The book covers the Big Bang, star formation, and current theories about dark matter.


### 13. Passive Voice and Subjectless Fragments

**Problem:** LLMs often hide the actor or drop the subject entirely with lines like "No configuration file needed" or "The results are preserved automatically." Rewrite these when active voice makes the sentence clearer and more direct.

**Before:**
> No configuration file needed. The results are preserved automatically.

**After:**
> You do not need a configuration file. The system preserves the results automatically.


## STYLE PATTERNS

### 14. Em Dash Overuse

**Problem:** LLMs use em dashes more than humans, mimicking "punchy" sales writing. In practice, most of these can be rewritten more cleanly with commas, periods, or parentheses.

**Before:**
> The term is primarily promoted by Dutch institutions—not by the people themselves. You don't say "Netherlands, Europe" as an address—yet this mislabeling continues—even in official documents.

**After:**
> The term is primarily promoted by Dutch institutions, not by the people themselves. You don't say "Netherlands, Europe" as an address, yet this mislabeling continues in official documents.


### 15. Overuse of Boldface

**Problem:** AI chatbots emphasize phrases in boldface mechanically.

**Before:**
> It blends **OKRs (Objectives and Key Results)**, **KPIs (Key Performance Indicators)**, and visual strategy tools such as the **Business Model Canvas (BMC)** and **Balanced Scorecard (BSC)**.

**After:**
> It blends OKRs, KPIs, and visual strategy tools like the Business Model Canvas and Balanced Scorecard.


### 16. Inline-Header Vertical Lists

**Problem:** AI outputs lists where items start with bolded headers followed by colons.

**Before:**
> - **User Experience:** The user experience has been significantly improved with a new interface.
> - **Performance:** Performance has been enhanced through optimized algorithms.
> - **Security:** Security has been strengthened with end-to-end encryption.

**After:**
> The update improves the interface, speeds up load times through optimized algorithms, and adds end-to-end encryption.


### 17. Title Case in Headings

**Problem:** AI chatbots capitalize all main words in headings.

**Before:**
> ## Strategic Negotiations And Global Partnerships

**After:**
> ## Strategic negotiations and global partnerships


### 18. Emojis

**Problem:** AI chatbots often decorate headings or bullet points with emojis.

**Before:**
> 🚀 **Launch Phase:** The product launches in Q3
> 💡 **Key Insight:** Users prefer simplicity
> ✅ **Next Steps:** Schedule follow-up meeting

**After:**
> The product launches in Q3. User research showed a preference for simplicity. Next step: schedule a follow-up meeting.


### 19. Curly Quotation Marks

**Problem:** ChatGPT uses curly quotes ("...") instead of straight quotes ("...").

**Before:**
> He said "the project is on track" but others disagreed.

**After:**
> He said "the project is on track" but others disagreed.


## COMMUNICATION PATTERNS

### 20. Collaborative Communication Artifacts

**Words to watch:** I hope this helps, Of course!, Certainly!, You're absolutely right!, Would you like..., let me know, here is a...

**Problem:** Text meant as chatbot correspondence gets pasted as content.

**Before:**
> Here is an overview of the French Revolution. I hope this helps! Let me know if you'd like me to expand on any section.

**After:**
> The French Revolution began in 1789 when financial crisis and food shortages led to widespread unrest.


### 21. Knowledge-Cutoff Disclaimers

**Words to watch:** as of [date], Up to my last training update, While specific details are limited/scarce..., based on available information...

**Problem:** AI disclaimers about incomplete information get left in text.

**Before:**
> While specific details about the company's founding are not extensively documented in readily available sources, it appears to have been established sometime in the 1990s.

**After:**
> The company was founded in 1994, according to its registration documents.


### 22. Sycophantic/Servile Tone

**Problem:** Overly positive, people-pleasing language.

**Before:**
> Great question! You're absolutely right that this is a complex topic. That's an excellent point about the economic factors.

**After:**
> The economic factors you mentioned are relevant here.


## FILLER AND HEDGING

### 23. Filler Phrases

**Before → After:**
- "In order to achieve this goal" → "To achieve this"
- "Due to the fact that it was raining" → "Because it was raining"
- "At this point in time" → "Now"
- "In the event that you need help" → "If you need help"
- "The system has the ability to process" → "The system can process"
- "It is important to note that the data shows" → "The data shows"


### 24. Excessive Hedging

**Problem:** Over-qualifying statements.

**Before:**
> It could potentially possibly be argued that the policy might have some effect on outcomes.

**After:**
> The policy may affect outcomes.


### 25. Generic Positive Conclusions

**Problem:** Vague upbeat endings.

**Before:**
> The future looks bright for the company. Exciting times lie ahead as they continue their journey toward excellence. This represents a major step in the right direction.

**After:**
> The company plans to open two more locations next year.


### 26. Hyphenated Word Pair Overuse

**Words to watch:** third-party, cross-functional, client-facing, data-driven, decision-making, well-known, high-quality, real-time, long-term, end-to-end

**Problem:** AI hyphenates common word pairs with perfect consistency. Humans rarely hyphenate these uniformly, and when they do, it's inconsistent. Less common or technical compound modifiers are fine to hyphenate.

**Before:**
> The cross-functional team delivered a high-quality, data-driven report on our client-facing tools. Their decision-making process was well-known for being thorough and detail-oriented.

**After:**
> The cross functional team delivered a high quality, data driven report on our client facing tools. Their decision making process was known for being thorough and detail oriented.


### 27. Persuasive Authority Tropes

**Phrases to watch:** The real question is, at its core, in reality, what really matters, fundamentally, the deeper issue, the heart of the matter

**Problem:** LLMs use these phrases to pretend they are cutting through noise to some deeper truth, when the sentence that follows usually just restates an ordinary point with extra ceremony.

**Before:**
> The real question is whether teams can adapt. At its core, what really matters is organizational readiness.

**After:**
> The question is whether teams can adapt. That mostly depends on whether the organization is ready to change its habits.


### 28. Signposting and Announcements

**Phrases to watch:** Let's dive in, let's explore, let's break this down, here's what you need to know, now let's look at, without further ado

**Problem:** LLMs announce what they are about to do instead of doing it. This meta-commentary slows the writing down and gives it a tutorial-script feel.

**Before:**
> Let's dive into how caching works in Next.js. Here's what you need to know.

**After:**
> Next.js caches data at multiple layers, including request memoization, the data cache, and the router cache.


### 29. Fragmented Headers

**Signs to watch:** A heading followed by a one-line paragraph that simply restates the heading before the real content begins.

**Problem:** LLMs often add a generic sentence after a heading as a rhetorical warm-up. It usually adds nothing and makes the prose feel padded.

**Before:**
> ## Performance
>
> Speed matters.
>
> When users hit a slow page, they leave.

**After:**
> ## Performance
>
> When users hit a slow page, they leave.

---

## NOMINAL STYLE PATTERNS

These four are the 2.6.0 additions. They come from the noun-density finding described at the top, and they survive most cleanups because none of them use a flagged word. The sentences are plain. The shape is the problem.

### 30. Verbless Nominal Decks and Tag Lines

**Signs to watch:** A sentence with no finite verb, usually a noun phrase plus a trailing modifier. Common under headings, in card headers, in chart labels, and as the summary line under a title.

**Problem:** Dropping the copula is a headline convention, and it is fine in a headline. LLMs carry it into body text, captions and bullet lines until every line reads like a brochure. Grammatically this is a nominal sentence with zero copula. It sounds authoritative because nothing is asserted, so nothing can be checked.

Compare with #8. There the verb is replaced with something ornate. Here it is deleted.

**Before:**
> One roadmap covering merchandise and tobacco, on one calendar and one gate ladder.

**After:**
> Merchandise and tobacco are planned together, on the same calendar and the same gate ladder.

**Before:**
> A governed brand asset, versioned and testable.

**After:**
> We version the brand mapping and test it, and one team owns it.

**When to leave it alone:** genuine headlines, deck standfirsts, chart labels and table cells, where a finite verb would be padding. See Non-Prose Surfaces below. Even there, do not let every label take the same shape.

### 31. Balanced Doublets and Numeral Anaphora

**Signs to watch:** Two clauses of matching length and shape joined by "and", often with a word repeated at the front of each: "one calendar and one gate ladder", "no model and no platform", "what we claim and what we can prove".

**Problem:** #10 catches the three-part version. The two-part version does the same thing and reads as elegant rather than mechanical, so it survives editing. The giveaway is that the repetition is carrying the argument. If the point is that there is only one of something, an LLM will repeat "one" instead of saying why one matters.

**Before:**
> First value needs no model and no platform.

**After:**
> The first dollars come out of arithmetic on data we already have. Nothing has to be built.

**Before:**
> One roadmap, one calendar, one owner.

**After:**
> It is one roadmap now. Same calendar, and the same person signs off.

**Fix:** keep at most one balanced pair per section, and break the symmetry when you keep it. Different lengths, different shapes, or turn the second half into its own sentence.

### 32. Bold Label Openers

**Signs to watch:** Most paragraphs starting with a bolded label and a period or colon. **Position.** **Read:** **Correction.** **Why:** **The finding that matters.**

**Problem:** One or two are a useful signpost. Every paragraph is a tic, and it lets the writer skip transitions entirely, which is why models like it. The labels also inflate: ordinary observations get announced as findings, positions and corrections.

This differs from #15 (boldface overuse), which is about emphasis inside sentences, and #16 (inline-header lists), which is about list items. This is about paragraph openers in running prose.

**Before:**
> **Position.** The engine is built in house.
>
> **Correction.** The earlier claim was wrong.

**After:**
> We build the engine in house.
>
> That reverses what we said in the last version, which was wrong about vendor coverage.

**Fix:** keep labels where a reader genuinely scans for them, such as **Acceptance** or **Escalation** in a spec. Delete them where prose should carry the connection, and write the transition instead.

### 33. Prose-to-Table Reflex

**Signs to watch:** A three-column table where two sentences would do. Tables whose third column is commentary rather than data. Every section ending in a comparison grid.

**Problem:** Tables look rigorous, so models reach for them to signal rigor. A table earns its place when a reader needs to look one row up, compare across rows, or scan for a value. If the cells are prose fragments, it is prose wearing a grid.

**Before:**
> | Aspect | Merchandise | Tobacco |
> |---|---|---|
> | Variation | Sparse | Abundant |
> | Direction | Both ways | One way |
> | Implication | Hard to measure | Easy to measure, hard to use |

**After:**
> Tobacco has plenty of price variation, unlike merchandise. It is nearly all in one direction, which is why it is still hard to use.

**Fix:** keep the table when the cells are values, dates, owners or counts. Convert to prose when the cells are judgments.

---

## Non-Prose Surfaces

The patterns above assume paragraphs. Much AI-flavored writing is not paragraphs, and blanket fixes make it worse. A chart label with a finite verb is padding, not humanity.

Apply this instead, by surface:

| Surface | Fragments allowed | What to fix instead |
|---|---|---|
| Headings, deck standfirsts | Yes | Repetition of shape across sibling headings. Significance inflation. |
| Card and callout headers | Yes | Every header taking the form `adjective noun, qualifier`. Vary length and shape. |
| Chart labels, bar tags, legends | Yes | Tags that assert importance rather than state content. Prefer a number, a date or a noun. |
| Table cells | Yes | Judgment words where a value belongs. See #33. |
| Bullet lists | Yes | Matched-length bullets. Real lists are ragged. Three bullets when there are two ideas. |
| Body paragraphs | No | Everything above. Restore the finite verb. |
| Commit messages, code comments | Yes | Leave conventional style alone. Do not humanize into prose. |

Two rules that apply everywhere:

1. **Vary shape across siblings.** Uniformity is the tell, not brevity. If six card headers are all noun-phrase-plus-comma-plus-qualifier, rewrite three of them into a different shape even if each one is fine alone.
2. **Do not humanize into vagueness.** A tag that says `0.50 price changes per item-site-year` beats a tag that says `sparse variation, measured`. Specificity is the most human thing available.

---

## Mechanical Scan

Do this before the subjective pass. A model grading its own prose is the weakest step in this skill, so start with things that can be counted.

Grep for these. Any hit is a candidate, not a verdict:

| What | Pattern |
|---|---|
| Em dashes | `—` |
| Negative parallelism | `not just\|isn't just\|not only\|rather than a\|not a .*, but a` |
| Copula avoidance | `serves as\|stands as\|functions as\|represents a\|marks a\|boasts\|features a` |
| Superficial -ing tails | `, (underscoring\|highlighting\|reflecting\|emphasizing\|showcasing\|demonstrating\|contributing)` |
| AI vocabulary | `delve\|tapestry\|pivotal\|intricate\|underscore\|meticulous\|seamless\|robust\|leverage\|crucial` |
| Persuasive authority | `the real question\|at its core\|what really matters\|fundamentally,` |
| Bold label openers | `^\*\*[A-Z][a-z]+[.:]\*\*` |
| Curly quotes | `[’“”]` |
| Numeral anaphora | `\bone \w+ and one \w+\|\bno \w+ and no \w+` |

Then count four things by hand or by script:

- **Mean words per sentence.** Over about 22 in body prose is dense.
- **Standard deviation of sentence length.** This is the important one. Under about 6 means the rhythm is flat, which no amount of word-swapping will fix. Human writing mixes 4-word sentences with 40-word ones.
- **Nominalization rate.** Words ending in `-tion, -ment, -ness, -ity, -ance` per 1,000 words. A spike means the verbs have been turned into nouns.
- **Verbless line share.** Lines in body prose with no finite verb. In paragraphs this should be near zero.

Report before and after numbers when you finish. If sentence-length deviation did not move, the rewrite was cosmetic.

---

## Process

1. Read the input text in full before rewriting
2. Decide which surface you are editing. Body prose, or one of the cases in Non-Prose Surfaces. This changes what counts as a defect
3. Run the Mechanical Scan and record the four numbers. Do this before reading for style, so the counts are not coloured by what you expect to find
4. Identify all instances of the patterns above
5. Rewrite each problematic section
6. Ensure the revised text:
   - Sounds natural when read aloud
   - Varies sentence length deliberately, not just structure
   - Uses specific details over vague claims
   - Uses simple constructions (is/are/has) where appropriate
   - Keeps a finite verb in every body-prose sentence
7. Present a draft humanized version
8. Prompt: "What makes the below so obviously AI generated?"
9. Answer briefly with the remaining tells (if any)
10. Prompt: "Now make it not obviously AI generated."
11. Present the final version (revised after the audit)
12. Re-run the Mechanical Scan. If sentence-length deviation did not move, go back to step 5, because the edit was cosmetic

## Output Format

Provide:
1. Scan numbers before
2. Draft rewrite
3. "What makes the below so obviously AI generated?" (brief bullets)
4. Final rewrite
5. Scan numbers after, next to the before numbers
6. A brief summary of changes made (optional)


## Full Example

**Before (AI-sounding):**
> Great question! Here is an essay on this topic. I hope this helps!
>
> AI-assisted coding serves as an enduring testament to the transformative potential of large language models, marking a pivotal moment in the evolution of software development. In today's rapidly evolving technological landscape, these groundbreaking tools—nestled at the intersection of research and practice—are reshaping how engineers ideate, iterate, and deliver, underscoring their vital role in modern workflows.
>
> At its core, the value proposition is clear: streamlining processes, enhancing collaboration, and fostering alignment. It's not just about autocomplete; it's about unlocking creativity at scale, ensuring that organizations can remain agile while delivering seamless, intuitive, and powerful experiences to users. The tool serves as a catalyst. The assistant functions as a partner. The system stands as a foundation for innovation.
>
> Industry observers have noted that adoption has accelerated from hobbyist experiments to enterprise-wide rollouts, from solo developers to cross-functional teams. The technology has been featured in The New York Times, Wired, and The Verge. Additionally, the ability to generate documentation, tests, and refactors showcases how AI can contribute to better outcomes, highlighting the intricate interplay between automation and human judgment.
>
> - 💡 **Speed:** Code generation is significantly faster, reducing friction and empowering developers.
> - 🚀 **Quality:** Output quality has been enhanced through improved training, contributing to higher standards.
> - ✅ **Adoption:** Usage continues to grow, reflecting broader industry trends.
>
> While specific details are limited based on available information, it could potentially be argued that these tools might have some positive effect. Despite challenges typical of emerging technologies—including hallucinations, bias, and accountability—the ecosystem continues to thrive. In order to fully realize this potential, teams must align with best practices.
>
> In conclusion, the future looks bright. Exciting times lie ahead as we continue this journey toward excellence. Let me know if you'd like me to expand on any section!

**Draft rewrite:**
> AI coding assistants speed up some tasks. In a 2024 study by Google, developers using Codex completed simple functions 55% faster than a control group, but showed no improvement on debugging or architectural decisions.
>
> The tools are good at boilerplate: config files, test scaffolding, repetitive refactors. They are bad at knowing when they are wrong. I have mass-accepted suggestions that compiled, passed lint, and still did the wrong thing because I stopped paying attention.
>
> Mira, an engineer at a fintech startup I interviewed, said she uses Copilot "like autocomplete for boring code" but reviews every line before committing. Jake, a senior dev at a larger company, disabled it after it kept suggesting patterns from a deprecated internal library.
>
> The productivity claims are hard to verify. GitHub says Copilot users "accept 30% of suggestions," but acceptance is not correctness, and correctness is not value. The 2024 Uplevel study found no statistically significant difference in pull-request throughput between teams with and without AI assistants.
>
> None of this means the tools are useless. It means they are tools. They do not replace judgment, and they do not eliminate the need for tests. If you do not have tests, you cannot tell whether the suggestion is right.

**What makes the below so obviously AI generated?**
- The rhythm is still a bit too tidy (clean contrasts, evenly paced paragraphs).
- The named people and study citations can read like plausible-but-made-up placeholders unless they're real and sourced.
- The closer leans a touch slogan-y ("If you do not have tests...") rather than sounding like a person talking.

**Now make it not obviously AI generated.**
> AI coding assistants can make you faster at the boring parts. Not everything. Definitely not architecture.
>
> They're great at boilerplate: config files, test scaffolding, repetitive refactors. They're also great at sounding right while being wrong. I've accepted suggestions that compiled, passed lint, and still missed the point because I stopped paying attention.
>
> People I talk to tend to land in two camps. Some use it like autocomplete for chores and review every line. Others disable it after it keeps suggesting patterns they don't want. Both feel reasonable.
>
> The productivity metrics are slippery. GitHub can say Copilot users "accept 30% of suggestions," but acceptance isn't correctness, and correctness isn't value. If you don't have tests, you're basically guessing.

**Changes made:**
- Removed chatbot artifacts ("Great question!", "I hope this helps!", "Let me know if...")
- Removed significance inflation ("testament", "pivotal moment", "evolving landscape", "vital role")
- Removed promotional language ("groundbreaking", "nestled", "seamless, intuitive, and powerful")
- Removed vague attributions ("Industry observers")
- Removed superficial -ing phrases ("underscoring", "highlighting", "reflecting", "contributing to")
- Removed negative parallelism ("It's not just X; it's Y")
- Removed rule-of-three patterns and synonym cycling ("catalyst/partner/foundation")
- Removed false ranges ("from X to Y, from A to B")
- Removed em dashes, emojis, boldface headers, and curly quotes
- Removed copula avoidance ("serves as", "functions as", "stands as") in favor of "is"/"are"
- Removed formulaic challenges section ("Despite challenges... continues to thrive")
- Removed knowledge-cutoff hedging ("While specific details are limited...")
- Removed excessive hedging ("could potentially be argued that... might have some")
- Removed filler phrases and persuasive framing ("In order to", "At its core")
- Removed generic positive conclusion ("the future looks bright", "exciting times lie ahead")
- Made the voice more personal and less "assembled" (varied rhythm, fewer placeholders)


## Reference

Patterns 1 to 29 come from [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup, drawn from thousands of observed instances of AI-generated text on Wikipedia.

Patterns 30 to 33, the Non-Prose Surfaces section and the Mechanical Scan were added in 2.6.0. The noun-density argument behind them comes from Reinhart, Markey, Laudenbach, Pantusen, Yurko, Weinberg and Brown, ["Do LLMs write like humans? Variation in grammatical and rhetorical styles"](https://www.pnas.org/doi/10.1073/pnas.2422455122), PNAS 122(8), 2025, [preprint arXiv:2410.16107](https://arxiv.org/abs/2410.16107). They scored LLM and human corpora on Biber's feature set and found instruction-tuned models produce noun-heavy, information-dense text even when asked for informal registers.

The sentence-length deviation check is the practical version of the same finding: models write clauses of uniform length, humans do not.

Key insight from Wikipedia: "LLMs use statistical algorithms to guess what should come next. The result tends toward the most statistically likely result that applies to the widest variety of cases."
