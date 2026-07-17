# Plan Writing Guidelines

## Output Compression

All intermediate artifacts use compressed prose. Token budget is the primary constraint.

**Rules (apply to claude-spec.md, claude-research.md, claude-plan.md):**
- Fragments OK. Drop section-intro sentences ("This section describes..." → just the content).
- Bullets > paragraphs for 3+ items.
- Tables > bullets for comparisons.
- Max 15 words per prose sentence.
- No hedging ("might", "could potentially", "worth noting", "it's important to").
- No filler transitions ("Additionally", "Furthermore", "In summary").

**Exception:** `claude-interview.md` keeps full Q&A fidelity — compress nothing.

### Structured Spec Format

`claude-spec.md` uses this header block instead of prose introduction:

```markdown
**Goal:** <one sentence, max 20 words>
**Scope in:** <bullet list>
**Scope out:** <bullet list>
**Constraints:** <bullet list>
**Key decisions:** <`Decision: Choice (alternative rejected, reason)`>
```

Then free-form sections for requirements and context. This saves ~40% vs prose intro.

---

## What is the Implementation Plan?

The implementation plan (`claude-plan.md`) is the central artifact of deep-plan. It's a self-contained prose document that describes **what** to build, **why**, and **how** - in enough detail that an engineer or LLM can implement it without guessing.

The plan is a **blueprint**, not a **building**. You describe the architecture; the implementer (human or `deep-implement`) writes the code. If it has code in it, it shouldn't amount to more than function stubs and docstrings.

---

## Required Inputs

Before writing the plan, these files will be in `{planning_dir}`:

| File | Contains | How to Use |
|------|----------|------------|
| `claude-spec.md` | Synthesized requirements from user input, research, and interview | Primary source - this defines WHAT we're building |
| `claude-research.md` | Codebase patterns, web research findings (if research was done) | Inform architecture decisions, follow existing conventions |
| `claude-interview.md` | Q&A transcript from stakeholder interview | Clarify ambiguities, understand priorities and constraints |

**Read all three files before writing.** The plan should synthesize these inputs, not ignore them.

---

## Writing for an Unfamiliar Reader

The plan must be **fully self-contained**. An engineer or LLM with NO prior context should understand:
- What we're building
- Why we're building it this way
- How to implement it
- Crucially, the reader is a software engineer; you do not need to show them code implementations

**Do NOT assume the reader has seen:**
- The original user request
- The interview conversation
- The research findings
- Any context from this session

**Do NOT write for yourself.** You already know everything - the plan is for someone who doesn't.

---

## The Code Budget

LLMs instinctively write code when they see a feature request. This produces 25k+ token "plans" that are actually implementations - wasting context and doing `deep-implement`'s job.

## Module Design Comes First

Adopted from the global `codebase-design` and `tdd` skills (Matt Pocock;
no longer vendored — see NOTICE). Before listing sections, sketch the
**deep modules** the implementation introduces:

* Each module has a *simple, stable* interface and a *substantial*
  implementation behind it.
* Validate the module list with the user before splitting into
  sections. Sections should be subordinate to modules — a section that
  produces an awkward module shape signals a planning miss.
* Avoid **shallow** modules: a public interface nearly as wide as its
  implementation is a smell. Fold or deepen.
* Avoid **hypothetical seams**: do not introduce an abstract base or
  Protocol with a single concrete implementation unless the second
  adapter is in scope for this plan.

The plan body should describe modules in terms of *external behavior*,
not file paths or code. File paths are appropriate inside individual
sections; in the plan body they rot quickly as the implementation
evolves.

## What Code IS Appropriate

- **Type definitions** (fields only, no methods)
- **Function signatures** with docstrings
- **API contracts** (endpoint paths, request/response shapes)
- **Directory structure** (tree format)
- **Configuration keys** (not full config files)

### GOOD Examples

```python
@dataclass
class CompanyData:
    name: str
    description: str | None
    industry: str | None
    employee_count: int | None
```

```python
def parse_company_page(html: str, url: str) -> CompanyData:
    """Extract company data from HTML using JSON-LD or HTML fallback.

    Returns CompanyData with populated fields, logs warning if <50% populated.
    """
```

```
src/
  scrapers/
    base.py          # Abstract scraper interface
    linkedin.py      # LinkedIn-specific implementation
    glassdoor.py     # Glassdoor-specific implementation
  parsers/
    json_ld.py       # JSON-LD extraction
    html.py          # HTML fallback parsing
```

---

## What Code is NOT Appropriate

- Full function/method bodies
- Complete test implementations
- Import statements
- Error handling code
- Validation logic
- Database queries
- API response handling

### BAD Examples

```python
# BAD - Full implementation
def parse_company_page(html: str, url: str) -> CompanyData:
    soup = BeautifulSoup(html, 'html.parser')
    json_ld = soup.find('script', type='application/ld+json')
    if json_ld:
        try:
            data = json.loads(json_ld.string)
            # ... 40 more lines
```

```python
# BAD - Full test
def test_json_ld_extraction():
    html = '<html><script type="application/ld+json">...</script></html>'
    result = parse_company_page(html, "https://example.com")
    assert result.name == "Acme Corp"
```

---

## Synthesizing Inputs

Your job is to transform the inputs into a coherent plan:

**From claude-spec.md:**
- Extract the core requirements
- Note any constraints or preferences
- Identify the key deliverables

**From claude-research.md:**
- Follow existing codebase patterns (if applicable)
- Apply best practices from web research
- Note any technical constraints discovered

**From claude-interview.md:**
- Incorporate clarifications about scope
- Respect stated priorities
- Address concerns that were raised

**Resolve conflicts:** If inputs disagree, use your judgment and document the decision.

---

## Anti-Goals

Every plan MUST include an **Anti-Goals** section (typically section 2, after Background). Anti-goals define what the implementation explicitly will NOT do. They prevent scope creep and give the implementer clear boundaries.

### Why Anti-Goals Matter

Without anti-goals, implementers (human or LLM) fill ambiguity with assumptions -- usually by building more than needed. Anti-goals transform implicit scope into explicit decisions.

### Format

The Anti-Goals section should be a bullet list. Each item starts with **"Do NOT"** followed by a clear boundary and a brief rationale:

```markdown
## Anti-Goals

- **Do NOT require external binaries** -- the plugin must work with only `uv`.
- **Do NOT replace markdown content files** -- findings.md, claude-plan.md stay as files.
- **Do NOT build a full issue tracker** -- this is a minimal dependency graph, not Jira.
```

### What Makes a Good Anti-Goal

- **Specific and testable**: "Do NOT require external binaries" is verifiable. "Keep it simple" is not.
- **Addresses a real temptation**: If nobody would think to do it, it doesn't need to be an anti-goal.
- **States the boundary AND the reason**: The reason prevents someone from re-litigating the decision later.

### What Does NOT Belong in Anti-Goals

- Features deferred to a future phase (those go in a "Deferred" or "Future Work" section)
- Obvious non-requirements ("Do NOT build a spaceship")
- Vague platitudes ("Do NOT over-engineer" -- too subjective to be actionable)

### Minimum Count

Every plan should have at least 3 anti-goals. If you cannot think of 3, you have not thought carefully enough about what the system should NOT do. Re-read the spec and interview for scope temptations.

