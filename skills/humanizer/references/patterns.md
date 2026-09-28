# Humanizer Pattern Catalog

The catalog of AI-writing tells, numbered 1-37 and grouped by category. Each entry lists words or phrases to watch, the underlying problem, and a before/after example. Nine patterns carry an "In marketing copy" note that relaxes the rule for persuasive content (see Content Types in `SKILL.md`). `§N` references elsewhere in the skill point here.

The "After" examples never add facts the "Before" lacked. Where a real rewrite would want a date, a source or a name, it comes from the source text or the user, not from you.

## Rewrite moves that recur

- **Point the sentence at the reader.** "You do not get to pick the format" becomes "you have no control over the input format".
- **Swap vague stand-ins for the concrete thing the source already has.** "Most of these" becomes "400 different file structures" when the 400 is in the text.
- **Name the consequence.** A hook that stops at "that is not a coincidence" gets the stake spelled out.
- **Soften absolutes the author can't defend.** "Every vendor primer" becomes "most vendors".

## CONTENT PATTERNS

### 1. Undue Emphasis on Significance, Legacy, and Broader Trends

**Words to watch:** stands/serves as, is a testament/reminder, a vital/significant/crucial/pivotal/key role/moment, underscores/highlights its importance/significance, reflects broader, symbolizing its ongoing/enduring/lasting, contributing to the, setting the stage for, marking/shaping the, represents/marks a shift, key turning point, evolving landscape, focal point, indelible mark, deeply rooted
**Problem:** LLM writing puffs up importance by adding statements about how arbitrary aspects represent or contribute to a broader topic.
**Before:**
> The launch of our analytics dashboard in 2021 marked a pivotal moment in the evolution of how modern teams work with data, reflecting a broader industry shift toward democratizing insights and empowering decision-makers at every level.
**After:**
> We launched the analytics dashboard in 2021.

**In marketing copy:** don't delete the significance, make it concrete and tie it to the reader's problem. "marks a pivotal moment for growing teams" → "means your team stops re-keying the same data into three tools."

### 2. Undue Emphasis on Notability and Media Coverage

**Words to watch:** independent coverage, local/regional/national media outlets, written by a leading expert, active social media presence, featured in, as seen in, trusted by industry leaders
**Problem:** LLMs hit readers over the head with claims of notability, often listing outlets or logos without context.
**Before:**
> Our platform has been featured in TechCrunch, Forbes, Wired, and dozens of leading industry publications, and we maintain an active presence across every major social platform.
**After:**
> TechCrunch and Forbes have both covered the platform.

(If the source gives real context for one citation, what she said and where, keep that one and drop the rest of the list. Don't invent the context to make the trimmed version sound better.)

**In marketing copy:** real, specific social proof (named customers, real logos, a genuine "used by" list, a sourced number) is a conversion asset, keep it. Cut or make specific only the *vague* version ("trusted by industry leaders," "thousands of happy customers" with no figure). Never invent a customer, logo, or count.

### 3. Superficial Analyses with -ing Endings

**Words to watch:** highlighting/underscoring/emphasizing..., ensuring..., reflecting/symbolizing..., contributing to..., cultivating/fostering..., encompassing..., showcasing...
**Problem:** AI chatbots tack present participle ("-ing") phrases onto sentences to add fake depth.
**Before:**
> Our onboarding flow guides new users through each step, ensuring a smooth experience, fostering long-term engagement, and reflecting our deep commitment to customer success.
**After:**
> Our onboarding flow walks new users through each step of setup.

### 4. Promotional and Advertisement-like Language

**Words to watch:** boasts a, vibrant, rich (figurative), profound, enhancing its, showcasing, exemplifies, commitment to, natural beauty, nestled, in the heart of, groundbreaking (figurative), renowned, breathtaking, must-visit, stunning
**Problem:** LLMs have serious problems keeping a neutral tone, especially for "cultural heritage" topics.
**Before:**
> Nestled at the intersection of design and performance, Acme stands as a vibrant, all-in-one project management platform with a rich feature set and a breathtaking, best-in-class user experience.
**After:**
> Acme is a project management platform.

**In marketing copy:** don't strip the sell, earn it. Replace generic superlatives with concrete, benefit-driven specifics instead of deleting them. "boasts a powerful dashboard" → "shows every campaign on one screen," not → "has a dashboard." Keep the persuasion; cut the empty adjectives ("stunning," "seamless," "cutting-edge") that any product could claim.

### 5. Vague Attributions and Weasel Words

**Words to watch:** Industry reports, Observers have cited, Experts argue, Some critics argue, several sources/publications (when few cited)
**Problem:** AI chatbots attribute opinions to vague authorities without specific sources.
**Before:**
> Experts agree that AI is reshaping customer support, and observers have noted that teams adopting these tools see dramatic gains in customer satisfaction.
**After:**
> AI is changing how customer support teams work.

(If a real source exists, name it. Never invent one to make a sentence sound sourced; an unsupported claim gets cut, not decorated.)

### 6. Outline-like "Challenges and Future Prospects" Sections

**Words to watch:** Despite its... faces several challenges..., Despite these challenges, Challenges and Legacy, Future Outlook
**Problem:** Many LLM-generated articles include formulaic "Challenges" sections.
**Before:**
> Despite its rapid growth, the company faces several challenges common to scaling startups, from hiring to infrastructure costs. Despite these challenges, with its strong culture and clear vision, it remains well-positioned to keep thriving for years to come.
**After:**
> As it grew, the company hit hiring and infrastructure-cost problems.

(The specifics you'd want here, like when hiring got hard or what the costs were, come from sources or the user, not from the rewrite.)

## LANGUAGE AND GRAMMAR PATTERNS

### 7. Overused "AI Vocabulary" Words

**High-frequency AI words:** Actually, additionally, align with, crucial, delve, emphasizing, enduring, enhance, fostering, garner, highlight (verb), interplay, intricate/intricacies, key (adjective), landscape (abstract noun), pivotal, showcase, tapestry (abstract noun), testament, underscore (verb), valuable, vibrant
**Problem:** These words appear far more frequently in post-2023 text. They often co-occur.
**Before:**
> Additionally, our platform leverages a robust, intricate architecture that showcases an enduring commitment to performance. This vibrant ecosystem underscores the pivotal role automation plays in the modern landscape.
**After:**
> Our platform is built for performance and relies on automation.

### 8. Avoidance of "is"/"are" (Copula Avoidance)

**Words to watch:** serves as/stands as/marks/represents [a], boasts/features/offers [a]
**Problem:** LLMs substitute elaborate constructions for simple copulas.
**Before:**
> Our reporting suite serves as the central hub for your metrics. It boasts real-time dashboards and features integrations with over 50 tools.
**After:**
> Our reporting suite is the central hub for your metrics. It has real-time dashboards and integrates with over 50 tools.

Related: this pattern replaces "is" with something fancier. For dropping the verb altogether, see §30.

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

The three-part version is the loudest, but the habit is matched clause shape at any length. See §31 for the two-part case, which slips past most readers and most detectors.

**In marketing copy:** intentional parallel benefits and triads ("faster, simpler, cheaper") are a legitimate device. Flag only *forced* or *uniform* threes, where everything is packaged in threes regardless of the real count.

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

### 14. Em Dashes (and En Dashes): Cut Them

**Rule:** The final rewrite contains no em dashes (—) or en dashes (–). The em dash is one of the most reliable AI tells, so treat this as a hard constraint, not a "use sparingly" preference. Replace each one, in rough order of preference: a period (start a new sentence), a comma (a tight aside), a colon (introducing an explanation), parentheses (a true aside), or restructure the sentence. Also catch spaced em dashes (` — `) and double hyphens (` -- `) used the same way.
**Before:**
> The term is primarily promoted by Dutch institutions—not by the people themselves. You don't say "Netherlands, Europe" as an address—yet this mislabeling continues—even in official documents.
**After:**
> The term is primarily promoted by Dutch institutions, not by the people themselves. You don't say "Netherlands, Europe" as an address, yet this mislabeling continues in official documents.
**Before:**
> The new policy — announced without warning — affects thousands of workers. The changes -- long overdue according to critics -- will take effect immediately.
**After:**
> The new policy, announced without warning, affects thousands of workers. The changes, long overdue according to critics, will take effect immediately.

Before returning the final rewrite, scan it for `—` and `–`. Any hit means the draft isn't done. One exception: a user-provided writing sample that uses em dashes overrides this rule (see `references/voice.md`); match the sample's frequency instead of banning them.

### 15. Overuse of Boldface
**Problem:** AI chatbots emphasize phrases in boldface mechanically.
**Before:**
> It blends **OKRs (Objectives and Key Results)**, **KPIs (Key Performance Indicators)**, and visual strategy tools such as the **Business Model Canvas (BMC)** and **Balanced Scorecard (BSC)**.
**After:**
> It blends OKRs, KPIs, and visual strategy tools like the Business Model Canvas and Balanced Scorecard.

**In marketing copy:** bolding a few key phrases for skimmers is expected and useful. The tell is *mechanical* bolding (every list item, the same word in every paragraph), not any bold at all. Keep purposeful emphasis; remove the reflexive kind.

### 16. Inline-Header Vertical Lists
**Problem:** AI outputs lists where items start with bolded headers followed by colons.
**Before:**
> - **User Experience:** The user experience has been significantly improved with a new interface.
> - **Performance:** Performance has been enhanced through optimized algorithms.
> - **Security:** Security has been strengthened with end-to-end encryption.
**After:**
> The update improves the interface, speeds up load times through optimized algorithms, and adds end-to-end encryption.

**In marketing copy:** genuine benefit or feature bullets with short lead-in labels are a normal, scannable landing-page format. Convert only the *padded* pseudo-lists that restate the label in the sentence after it; keep real bullets that each carry new information.

### 17. Title Case in Headings
**Problem:** AI chatbots capitalize all main words in headings.
**Before:**
> ## Strategic Negotiations And Global Partnerships
**After:**
> ## Strategic negotiations and global partnerships

**In marketing copy:** many brand style guides mandate title case for headings (AP style is common in marketing). Defer to the brand's style guide; flag title case as a tell only when no style guide specifies heading case.

### 18. Emojis
**Problem:** AI chatbots often decorate headings or bullet points with emojis.
**Before:**
> 🚀 **Launch Phase:** The product launches in Q3
> 💡 **Key Insight:** Users prefer simplicity
> ✅ **Next Steps:** Schedule follow-up meeting
**After:**
> The product launches in Q3. User research showed a preference for simplicity. Next step: schedule a follow-up meeting.

**In marketing copy:** some brand voices use emojis on purpose (B2C, social-forward). Defer to the brand voice; flag only decorative, mechanical use, like an emoji bolted onto every heading or bullet.

### 19. Curly Quotation Marks
**Problem:** ChatGPT uses curly quotes (“...”) instead of straight quotes ("...").
**Before:**
> He said “the project is on track” but others disagreed.
**After:**
> He said "the project is on track" but others disagreed.

## COMMUNICATION PATTERNS

### 20. Collaborative Communication Artifacts

**Words to watch:** I hope this helps, Of course!, Certainly!, You're absolutely right!, Would you like..., Want me to...?, Want me to give examples?, Should I continue?, let me know, here is a...
**Problem:** Text meant as chatbot correspondence gets pasted as content.
**Before:**
> Here is an overview of the French Revolution. I hope this helps! Let me know if you'd like me to expand on any section.
**After:**
> The French Revolution began in 1789 when financial crisis and food shortages led to widespread unrest.

### 21. Knowledge-Cutoff Disclaimers and Speculative Gap-Filling

**Words to watch:** as of [date], Up to my last training update, While specific details are limited/scarce..., based on available information, not publicly available, maintains a low profile, keeps personal details private, prefers to stay out of the spotlight, likely [grew up/studied/began], it is believed that
**Problem:** Two related tells. (a) Older models leave hard knowledge-cutoff disclaimers in the text. (b) When a model can't find a source, it writes a paragraph *about* not finding one and then invents plausible filler to cover the gap. For a private person the guess almost always lands on the same stock phrases ("maintains a low profile," "keeps personal details private"), none of it sourced. Say what isn't known, or cut the sentence; don't dress a guess up as fact.
**Before (cutoff disclaimer):**
> While specific details about the company's founding are not extensively documented in readily available sources, it appears to have been established sometime in the 1990s.
**After:**
> The company's founding date is not documented in the available sources. (Or cut the sentence. State a date only if a source provides one.)
**Before (speculative gap-fill):**
> Information about her early life is not publicly available, suggesting she maintains a low profile and keeps personal details private. She likely grew up in a middle-class household, which shaped her later interest in education reform.
**After:**
> Her early life is not documented in the available sources. (Or omit the section.)

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
> (Cut the paragraph. End on the last concrete fact instead of a send-off. If the source states real plans, use those.)

**In marketing copy:** don't just cut the ending, a marketing piece needs a close. Replace the vague send-off ("exciting times ahead," "the future looks bright") with a specific, concrete call to action. The ending should ask for one clear next step, not trail off on a fact or a slogan.

### 26. Hyphenated Word Pair Overuse

**Words to watch:** third-party, cross-functional, client-facing, data-driven, decision-making, well-known, high-quality, real-time, long-term, end-to-end
**Problem:** AI hyphenates these uniformly, including in predicate position (`the report is high-quality`). Humans hyphenate inconsistently, typically only when the compound is attributive (`a high-quality report`) and often dropping the hyphen otherwise (`the report is high quality`). Keep attributive-position hyphens; drop them when the compound follows the noun.
**Before:**
> The cross-functional team delivered a high-quality, data-driven report. The team is cross-functional, the report is high-quality, and the methodology is data-driven.
**After:**
> The cross-functional team delivered a high-quality, data-driven report. The team is cross functional, the report is high quality, and the methodology is data driven.

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

## NOMINAL STYLE PATTERNS

These four come from the noun-density finding in `SKILL.md` (Why the tells cluster), and they survive most cleanups because none of them use a flagged word. The sentences are plain. The shape is the problem.

### 30. Verbless Nominal Decks and Tag Lines

**Signs to watch:** A sentence with no finite verb, usually a noun phrase plus a trailing modifier. Common under headings, in card headers, in chart labels, and as the summary line under a title.

**Problem:** Dropping the copula is a headline convention, and it is fine in a headline. LLMs carry it into body text, captions and bullet lines until every line reads like a brochure. Grammatically this is a nominal sentence with zero copula. It sounds authoritative because nothing is asserted, so nothing can be checked.

Compare with §8. There the verb is replaced with something ornate. Here it is deleted.

**Before:**
> One roadmap covering merchandise and tobacco, on one calendar and one gate ladder.

**After:**
> Merchandise and tobacco are planned together, on the same calendar and the same gate ladder.

**Before:**
> A governed brand asset, versioned and testable.

**After:**
> We version the brand mapping and test it, and one team owns it.

**When to leave it alone:** genuine headlines, deck standfirsts, chart labels and table cells, where a finite verb would be padding. See Non-Prose Surfaces in `references/surfaces-and-scan.md`. Even there, do not let every label take the same shape.

### 31. Balanced Doublets and Numeral Anaphora

**Signs to watch:** Two clauses of matching length and shape joined by "and", often with a word repeated at the front of each: "one calendar and one gate ladder", "no model and no platform", "what we claim and what we can prove".

**Problem:** §10 catches the three-part version. The two-part version does the same thing and reads as elegant rather than mechanical, so it survives editing. The giveaway is that the repetition is carrying the argument. If the point is that there is only one of something, an LLM will repeat "one" instead of saying why one matters.

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

This differs from §15 (boldface overuse), which is about emphasis inside sentences, and §16 (inline-header lists), which is about list items. This is about paragraph openers in running prose.

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

## RHETORICAL PATTERNS

### 34. Diff-Anchored Writing
**Problem:** Documentation or comments written as if narrating a change rather than describing the thing as it is. Unless the document is inherently version-scoped (changelogs, release notes, migration guides), it should read coherently without knowing what changed in the last commit.
**Before:**
> This function was added to replace the previous approach of iterating through all items, which caused O(n²) performance.
**After:**
> This function uses a hash map for O(1) lookups, avoiding the O(n²) cost of naive iteration.

### 35. Manufactured Punchlines and Staccato Drama
**Problem:** LLMs often make every sentence land like a quotable closer, then stack short declarative fragments to manufacture drama. A single short sentence for emphasis is fine; a run of them starts to sound engineered.
**Before:**
> Then AlphaEvolve arrived. It had no preference for symmetry. No aesthetic prior. No nostalgia for human taste. The old rules were gone.
**After:**
> AlphaEvolve changed the search because it did not favor symmetry or human-looking designs. That made some of the older assumptions less useful.

### 36. Aphorism Formulas

**Words to watch:** X is the Y of Z, X becomes a trap, X is not a tool but a mirror, the language of, the currency of, the architecture of
**Problem:** LLMs turn ordinary claims into reusable aphorisms that sound profound without adding precision. Replace the formula with the concrete claim it is gesturing at.
**Before:**
> Symmetry is the language of trust. Efficiency becomes a trap when teams forget the human layer.
**After:**
> Symmetric layouts often feel more predictable to users. Teams can over-optimize workflows and miss how people actually use them.

### 37. Conversational Rhetorical Openers

**Phrases to watch:** Honestly?, Look, Here's the thing, The thing is, Let's be honest, Real talk, when used as standalone hooks or fake-candid pauses before an ordinary point.
**Problem:** LLMs open with a fake-candid hook to manufacture intimacy before delivering a routine claim. The tell is the theatrical pause-and-reveal: a one-word question or aside, then the "real" answer. A person being honest usually just says the thing.
**Before:**
> Is it worth the price? Honestly? It depends on how often you'll use it.
**After:**
> Whether it's worth the price depends on how often you'll use it.
