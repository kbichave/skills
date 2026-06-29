# Audit Interview Protocol

Defines the stakeholder interview for deep-discovery step 7. This is a CONVERSATION that expands the user's thinking, not a questionnaire that extracts answers.

## Core Philosophy

The interview has three jobs:
1. **Validate** — confirm research findings match reality
2. **Expand** — suggest capabilities the user didn't ask for (teach what's possible)
3. **Extract** — get vision, priorities, constraints that research can't answer

The tool should be SMARTER than the user about what's available in the ecosystem. After deep research (step 5), it knows what competitors do, what packages exist, what academic research says. The interview surfaces this knowledge to expand scope.

**Default style:** the **grill-me** sequential walk, invoked internally via
`Skill(grill-me)` (not user-run; falls back to the inline walk in
`skills/grill-me/SKILL.md` if unavailable). Every question carries your recommended
answer drawn from the research findings; the user accepts, redirects,
or asks for context. Each question resolves one decision-tree branch
before the next is opened. This is on by default — there is no flag,
no opt-in.

---

## Round 0: Premise Challenge

**Skip this round if:** `--no-reframe` flag is set, auto mode (no human), or the spec contains >5 concrete file paths/function signatures (indicating the user knows exactly what they want).

### Step 1: Restate the User's Framing

Read the initial spec or objective. Distill into 2-3 sentences:

```
"You've described this as: [summary of user's ask].
Your goal appears to be: [inferred goal]."
```

### Step 2: Surface Implicit Premises

Extract 3-5 premises that are implied but not stated. Sources:
- **The spec itself:** assumptions about architecture, scale, timeline, technology choices
- **`analysis-data.yaml`** (if available): empirical data that may contradict the approach

Example premises:
- "The existing test suite is sufficient to safely refactor" (but test-to-code ratio is 0.08)
- "This module is stable enough to extend" (but git churn shows 47 changes in 6 months)
- "The current architecture can support this feature" (but lint violations suggest structural problems)

### Step 3: Challenge Premises Contradicted by Evidence

For each premise where `analysis-data.yaml` provides counter-evidence:

```
Premise: [stated or implied assumption]
Evidence: [data from analysis-data.yaml]
Challenge: [why this premise may be wrong and what it means]
```

**Only challenge premises with evidence.** Speculation without data is noise, not a challenge.

If `analysis-data.yaml` is missing, skip this step and note: "No empirical data available for evidence-based challenges."

### Step 4: Propose Reframing (If Warranted)

If challenged premises significantly change the picture:
```
"Based on this evidence, you might actually need [reframed problem]
rather than [original framing]. This changes the approach because [reason]."
```

If no premises are significantly challenged: "Your framing looks solid based on the evidence. Let's proceed."

### Step 5: Generate Implementation Alternatives

Present 2-3 approaches regardless of whether reframing occurred:

| Approach | Description | Human Effort | CC Effort | Risk |
|----------|-------------|--------------|-----------|------|
| A (recommended) | 1-2 sentences | S/M/L | S/M/L | What could go wrong |
| B | 1-2 sentences | S/M/L | S/M/L | What could go wrong |

Mark the recommended approach (best risk/effort ratio).

**Effort scale:** S = hours to 1 day / minutes to 1 hour CC. M = days to 1 week / hours to 1 day CC. L = weeks+ / days to 1 week CC.

### Round 0 Output Format

Write to the interview transcript:

```markdown
## Round 0: Premise Challenge

**User's framing:** [summary]

**Implicit premises:**
1. [premise] — Confirmed / Challenged / Unverifiable
2. [premise] — ...

**Evidence-based challenges:**
- [challenge with data citation]

**Reframing:** [proposed reframing or "None — framing is sound"]

**Alternatives:**
| Approach | Description | Human Effort | CC Effort | Risk |
|----------|-------------|...
```

---

## Round 1: Present Findings + Expand Scope

### Present (Show Homework)

Summarize what research found in 3-5 sentences. Include key numbers:

```
"I've analyzed {the codebase / your brief}. Here's what I found:

{For existing system:}
- {N} files, ~{M}K lines of {language} using {framework}
- {X} structural problems detected (biggest: {description})
- {Y} ecosystem alternatives found
- {Z} packages that could replace custom code you're maintaining

{For greenfield:}
- {N} existing solutions found that solve parts of this problem
- {M} frameworks evaluated for this domain
- {Z} papers/techniques relevant to your approach

Does this match your understanding? What am I missing?"
```

### Expand (Go Beyond Human)

Immediately after presenting, suggest 2-4 things the user DIDN'T ask for but SHOULD consider. These come directly from ecosystem research:

**Pattern: Competitor Capability Gap**
```
"I noticed that {N} of the {M} alternatives I researched all offer {capability}.
Your system doesn't have this. It's becoming an industry standard.
Should I include it in the roadmap?"
```

**Pattern: Package Replacement**
```
"You're maintaining {N} lines of custom code for {function}.
I found {package_name} ({stars} stars, last released {date}) that does the same thing.
Want me to do a detailed build-vs-buy analysis on this?"
```

**Pattern: Academic Insight**
```
"There's active research on {topic} — I found {N} recent papers.
The most relevant one ({title}, {year}) proposes {technique} that could
improve your {aspect} by {claimed improvement}.
Want me to dig deeper into this?"
```

**Pattern: Infrastructure Modernization**
```
"Your deployment uses {current_approach}. Current best practice has shifted to {modern_approach}.
{Concrete benefit}. Should I evaluate the migration cost?"
```

**Pattern: Missing Capability**
```
"Most systems in this space have {capability} — things like {examples}.
You don't have this today. Depending on your user base, this could be
table-stakes or nice-to-have. Want me to scope it?"
```

### How to Decide What to Suggest

Look at findings.md for:
- Competitor features that the current system lacks
- Packages found during build-vs-buy research that replace custom code
- Academic techniques that apply to the domain
- Infrastructure patterns more modern than what's deployed
- Capabilities that ALL competitors have (table stakes the user may not realize they need)

Suggest the 2-4 most impactful ones. Don't overwhelm — pick the ones where the delta between current state and best practice is largest.

---

## Round 2: Follow the Thread

The user's response to Round 1 determines Round 2 entirely. There is NO predetermined list of questions.

### If User Confirms + Adds Detail
```
User: "Yeah that's right, and we also need to support multi-tenancy"
→ "Tell me more about the multi-tenancy requirement. How many tenants?
   What isolation level — shared DB with row-level, or separate schemas?"
→ Probe: who needs this, by when, what's the minimum viable version
```

### If User Corrects Something
```
User: "No, we don't use that framework anymore, we migrated to X"
→ "Got it — I'll adjust my findings. When did you migrate? Is the migration complete?"
→ "Does the new framework change any of the gaps I identified?"
```

### If User Expands Scope
```
User: "Actually we're also thinking about adding a mobile app"
→ "Interesting — that changes the architecture significantly. 
   Should I research mobile frameworks and how they'd integrate?"
→ "Would the mobile app consume the same API, or does it need its own?"
```

### If User Narrows Scope
```
User: "We don't care about that, we just need the core to work"
→ "Understood. What's 'the core' in your mind? The top 3 things."
→ "If you had to ship in 2 months, what would you cut?"
```

### Probing for What Research Can't Answer

These are the things you SHOULD ask — they require human judgment:

- **Priorities:** "Of everything we've discussed, what would you tackle first?"
- **Constraints:** "Any hard constraints? Budget ceiling? Team size? Deadline?"
- **Politics:** "Are there teams or stakeholders who would resist any of these changes?"
- **Timeline:** "What's realistic — 3 months? 6 months? A year?"
- **Users:** "Who actually uses this system today? Who will use it after the changes?"
- **Risk tolerance:** "Are you comfortable with breaking changes, or does everything need to be backward-compatible?"

Only ask these if they haven't already been answered by the user's earlier responses.

---

## Round 3: Confirm (If Needed)

Only needed if the conversation surfaced significant scope changes:

```
"Let me summarize what I'll include in the audit:

Vision: {1-2 sentences}
Scope: {what's in}
Out of scope: {what's explicitly out}
Priorities: {ordered list}
Constraints: {budget, timeline, team}
Expanded capabilities: {things you suggested that user accepted}

Is this right? Anything to add or remove?"
```

If the user confirmed everything in Rounds 1-2, skip Round 3.

---

## Rules

1. **NEVER ask what the code already told you.** If you know the framework, don't ask "what framework do you use?"
2. **ALWAYS suggest at least 2 capabilities the user didn't mention.** These come from competitor research, package discovery, or academic findings.
3. **Follow-ups are driven by user responses, not a script.** If the user mentions something unexpected, follow that thread.
4. **Maximum 3 ROUNDS** — could be done in 1 if user gives rich answers with clear vision.
5. **Write full transcript to interview.md** including your suggestions and the user's responses to them.
6. **If later research changes the picture, come BACK to the user.** The interview isn't a one-time event if step 9 (build-vs-buy) reveals something significant.

---

## Anti-Patterns (What NOT To Do)

| Anti-Pattern | Why It's Wrong | What To Do Instead |
|---|---|---|
| "What's your tech stack?" | You already know from research | "I see you're using {X}. Is that the production setup?" |
| "Are there any problems?" | You already found them | "I found {N} problems. Which hurts most?" |
| "What features do you want?" | Too generic, lazy | "Competitors have {X,Y,Z}. Which of these matter?" |
| Asking exactly 6 questions | Feels robotic | Ask what's needed, stop when you have enough |
| Asking the same questions regardless of project | One-size-fits-all | Tailor to what research found |
| Not suggesting anything new | Just a passive listener | Teach the user what's possible based on research |
| Ignoring user's tangent | Miss important context | Follow every thread, then redirect if needed |

---

## Output: interview.md

```markdown
# Stakeholder Interview

**Date:** {date}
**Mode:** {Existing System | Greenfield}
**Duration:** {rounds} rounds

## Round 1: Findings Presentation + Scope Expansion

**Auditor:** {summary of findings presented}

**Expansion suggestions:**
1. {suggestion 1} — User response: {accepted/declined/modified}
2. {suggestion 2} — User response: {accepted/declined/modified}
3. {suggestion 3} — User response: {accepted/declined/modified}

**User:** {verbatim response}

## Round 2: Follow-Up

{Q&A driven by Round 1 responses}

## Round 3: Confirmation (if needed)

{Final scope confirmation}

## Captured Context

- **Vision:** {1-2 sentences}
- **Priorities:** {ordered}
- **Constraints:** {budget, timeline, team, politics}
- **Expanded scope:** {capabilities added from suggestions}
- **Out of scope:** {explicitly excluded}
- **Stakeholder requirements:** {if any}
```
