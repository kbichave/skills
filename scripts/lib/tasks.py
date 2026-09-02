"""Task definitions and generation for deep-plan workflow.

Replaces the legacy TodoWrite system with Claude Code Tasks (v2.1.16+).
Provides native dependency tracking, persistence, and subagent visibility.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskDefinition:
    """Definition of a workflow task."""

    subject: str
    description: str
    active_form: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        return {
            "subject": self.subject,
            "description": self.description,
            "activeForm": self.active_form,
        }


# Maximum concurrent subagents supported by Claude Code
BATCH_SIZE = 7

# Task IDs mapped to workflow step numbers
# Steps 0-4 are setup (not tracked as tasks)
# Steps 6-22 are the main workflow
TASK_IDS: dict[int, str] = {
    6: "research-decision",
    7: "execute-research",
    8: "detailed-interview",
    9: "save-interview",
    10: "write-spec",
    11: "generate-plan",
    12: "context-check-pre-review",
    13: "external-review",
    14: "integrate-feedback",
    15: "user-review",
    16: "apply-tdd",
    17: "context-check-pre-split",
    18: "create-section-index",
    19: "generate-section-tasks",
    20: "write-sections",
    21: "final-verification",
    22: "output-summary",
}

# Reverse mapping for lookup
TASK_ID_TO_STEP: dict[str, int] = {v: k for k, v in TASK_IDS.items()}

# Step names for display
STEP_NAMES: dict[int, str] = {
    0: "Context check",
    1: "Print intro and validate environment",
    2: "Handle environment errors",
    3: "Validate spec file input",
    4: "Setup planning session",
    6: "Research decision",
    7: "Execute research",
    8: "Detailed interview",
    9: "Save interview transcript",
    10: "Write initial spec",
    11: "Generate implementation plan",
    12: "Context check (pre-review)",
    13: "External LLM review",
    14: "Integrate external feedback",
    15: "User review of integrated plan",
    16: "Apply TDD approach",
    17: "Context check (pre-split)",
    18: "Create section index",
    19: "Generate section tasks",
    20: "Write section files",
    21: "Final status and cleanup",
    22: "Output summary",
}

# Explicit dependency graph (replaces step ordering)
# Each task lists the task IDs it is blocked by
TASK_DEPENDENCIES: dict[str, list[str]] = {
    # Context items - each blocked by final step, stays visible throughout workflow
    # Values are stored in subject field for visibility after compaction
    "context-plugin-root": ["output-summary"],
    "context-planning-dir": ["output-summary"],
    "context-initial-file": ["output-summary"],
    "context-review-mode": ["output-summary"],
    # Main workflow
    "research-decision": [],  # Can start immediately
    "execute-research": ["research-decision"],
    "detailed-interview": ["execute-research"],  # Depends on research (even if skipped)
    "save-interview": ["detailed-interview"],
    "write-spec": ["save-interview"],
    "generate-plan": ["write-spec"],
    "context-check-pre-review": ["generate-plan"],
    "external-review": ["context-check-pre-review"],
    "integrate-feedback": ["external-review"],
    "user-review": ["integrate-feedback"],
    "apply-tdd": ["user-review"],
    "context-check-pre-split": ["apply-tdd"],
    "create-section-index": ["context-check-pre-split"],
    "generate-section-tasks": ["create-section-index"],
    "write-sections": ["generate-section-tasks"],
    "final-verification": ["write-sections"],
    "output-summary": ["final-verification"],
}

# Task definitions with subject, description, and activeForm
# Note: Context tasks are NOT in this dict - they're generated dynamically
# with values in the subject field by create_context_tasks()
TASK_DEFINITIONS: dict[str, TaskDefinition] = {
    "research-decision": TaskDefinition(
        subject="Research Decision",
        description="Read research-protocol.md and decide on research approach",
        active_form="Deciding on research approach",
    ),
    "execute-research": TaskDefinition(
        subject="Execute Research",
        description="Launch research subagents based on decisions from previous step",
        active_form="Executing research",
    ),
    "detailed-interview": TaskDefinition(
        subject="Detailed Interview",
        description="Read interview-protocol.md and conduct stakeholder interview",
        active_form="Conducting detailed interview",
    ),
    "save-interview": TaskDefinition(
        subject="Save Interview Transcript",
        description="Write Q&A to claude-interview.md",
        active_form="Saving interview transcript",
    ),
    "write-spec": TaskDefinition(
        subject="Write Initial Spec",
        description="Combine input, research, and interview into claude-spec.md",
        active_form="Writing initial spec",
    ),
    "generate-plan": TaskDefinition(
        subject="Generate Implementation Plan",
        description="Create detailed plan in claude-plan.md. Write for unfamiliar reader.",
        active_form="Generating implementation plan",
    ),
    "context-check-pre-review": TaskDefinition(
        subject="Context Check (Pre-Review)",
        description="Run check-context-decision.py before external review",
        active_form="Checking context (pre-review)",
    ),
    "external-review": TaskDefinition(
        subject="External LLM Review",
        description="Read external-review.md and run review based on review_mode",
        active_form="Running external LLM review",
    ),
    "integrate-feedback": TaskDefinition(
        subject="Integrate External Feedback",
        description="Apply substantive review feedback directly to claude-plan.md",
        active_form="Integrating external feedback",
    ),
    "user-review": TaskDefinition(
        subject="User Review of Integrated Plan",
        description="Wait for user to review and approve claude-plan.md",
        active_form="Waiting for user review",
    ),
    "apply-tdd": TaskDefinition(
        subject="Apply TDD Approach",
        description="Read tdd-approach.md and create claude-plan-tdd.md",
        active_form="Applying TDD approach",
    ),
    "context-check-pre-split": TaskDefinition(
        subject="Context Check (Pre-Split)",
        description="Run check-context-decision.py before section splitting",
        active_form="Checking context (pre-split)",
    ),
    "create-section-index": TaskDefinition(
        subject="Create Section Index",
        description="Read section-index.md and create sections/index.md with SECTION_MANIFEST",
        active_form="Creating section index",
    ),
    "generate-section-tasks": TaskDefinition(
        subject="Generate Section Tasks",
        description="Run generate-section-tasks.py to get batch task operations",
        active_form="Generating section tasks",
    ),
    "write-sections": TaskDefinition(
        subject="Write Section Files",
        description="Read section-splitting.md and execute batch loop with subagents",
        active_form="Writing section files",
    ),
    "final-verification": TaskDefinition(
        subject="Final Verification",
        description="Run check-sections.py to verify all sections complete",
        active_form="Running final verification",
    ),
    "output-summary": TaskDefinition(
        subject="Output Summary",
        description="Print generated files and next steps",
        active_form="Outputting summary",
    ),
}


# ============================================================================
# AUDIT WORKFLOW DEFINITIONS
# ============================================================================

# Task IDs for audit workflow steps
# Steps 1-3 are setup (not tracked as tasks)
# Steps 4-15 are the main audit workflow (4, 4.5, 5, 5.5 added for topic + coverage steps)
AUDIT_TASK_IDS: dict[int, str] = {
    4: "quick-scan",
    5: "empirical-data-collection",
    6: "topic-enumeration",
    7: "deep-research",
    8: "coverage-validation",
    9: "auto-gaps",
    10: "stakeholder-interview",
    11: "generate-audit-docs",
    12: "generate-build-vs-buy",
    13: "generate-phase-specs",
    14: "external-review",
    15: "user-review",
    16: "output-summary",
}

AUDIT_TASK_ID_TO_STEP: dict[str, int] = {v: k for k, v in AUDIT_TASK_IDS.items()}

AUDIT_STEP_NAMES: dict[int, str] = {
    0: "Context check",
    1: "Validate environment",
    2: "Detect audit mode",
    3: "Setup session",
    4: "Quick scan",
    5: "Empirical data collection (git/lint/coverage analysis)",
    6: "Topic enumeration (research coverage manifest)",
    7: "Deep research (topic-assigned parallel subagents)",
    8: "Coverage validation (gap agents for uncovered topics)",
    9: "Auto gap identification",
    10: "Stakeholder interview",
    11: "Generate audit documents",
    12: "Generate build-vs-buy analysis",
    13: "Generate phase specs",
    14: "External LLM review",
    15: "User review",
    16: "Output summary",
}

AUDIT_TASK_DEPENDENCIES: dict[str, list[str]] = {
    # Context items
    "context-plugin-root": ["output-summary"],
    "context-planning-dir": ["output-summary"],
    "context-initial-file": ["output-summary"],
    "context-review-mode": ["output-summary"],
    # Main audit workflow — topic enumeration is the coverage contract before research
    "quick-scan": [],
    "empirical-data-collection": ["quick-scan"],
    "topic-enumeration": ["empirical-data-collection"],
    "deep-research": ["topic-enumeration"],       # agents now assigned specific topics
    "coverage-validation": ["deep-research"],     # gap agents for uncovered topics
    "auto-gaps": ["coverage-validation"],
    "stakeholder-interview": ["auto-gaps"],       # interview AFTER research (research-first)
    "generate-audit-docs": ["stakeholder-interview"],
    "generate-build-vs-buy": ["generate-audit-docs"],  # needs audit docs for context
    "generate-phase-specs": ["generate-build-vs-buy"],  # needs build-vs-buy decisions
    "external-review": ["generate-phase-specs"],
    "user-review": ["external-review"],
    "output-summary": ["user-review"],
}

AUDIT_TASK_DEFINITIONS: dict[str, TaskDefinition] = {
    "quick-scan": TaskDefinition(
        subject="Quick Scan",
        description="Read audit-research-protocol.md. Launch 1 Explore agent for structural scan. Detect tech stack, domain, size. Write scan-summary.md.",
        active_form="Running quick codebase scan",
    ),
    "empirical-data-collection": TaskDefinition(
        subject="Empirical Data Collection",
        description="Read audit-data-collection.md. Read scan-summary.md for language detection. Run git analysis (file churn, contributors, commit frequency, test-to-code ratio). Execute language-specific tools conditionally. Write analysis-data.yaml.",
        active_form="Collecting empirical codebase data",
    ),
    "topic-enumeration": TaskDefinition(
        subject="Topic Enumeration",
        description="Read audit-topic-enumeration.md. Simulate 3 perspectives (security auditor, new engineer, PM). Generate research-topics.yaml with 12-20 topics, each with id/category/priority/questions.",
        active_form="Enumerating research topics",
    ),
    "deep-research": TaskDefinition(
        subject="Deep Research",
        description="Read audit-research-protocol.md and research-topics.yaml. Assign 2-3 topics per agent. Each agent writes findings/<topic-id>-<slug>.md answering its assigned questions.",
        active_form="Running topic-assigned parallel research",
    ),
    "coverage-validation": TaskDefinition(
        subject="Coverage Validation",
        description="Read audit-coverage-validation.md. Run validate-coverage.py. Spawn gap agents for uncovered topics. Loop until coverage ≥ 80% or no more topics can be covered.",
        active_form="Validating research coverage",
    ),
    "auto-gaps": TaskDefinition(
        subject="Auto Gap Identification",
        description="Read all findings/<topic-id>-*.md files. Write current-state/ and gaps/ files. Draft build-vs-buy list from coverage findings.",
        active_form="Identifying gaps from research",
    ),
    "stakeholder-interview": TaskDefinition(
        subject="Stakeholder Interview",
        description="Read audit-interview-protocol.md. Present coverage map (research-topics.yaml), expand scope, follow thread. Write interview.md.",
        active_form="Conducting stakeholder interview",
    ),
    "generate-audit-docs": TaskDefinition(
        subject="Generate Audit Documents",
        description="Read audit-doc-writing.md. Launch parallel audit-doc-writer subagents. Eval-on-write quality gate.",
        active_form="Generating audit documents",
    ),
    "generate-build-vs-buy": TaskDefinition(
        subject="Generate Build-vs-Buy Analysis",
        description="Read audit-build-vs-buy.md. Launch parallel subagents to evaluate pip/npm/SaaS for each capability.",
        active_form="Generating build-vs-buy analysis",
    ),
    "generate-phase-specs": TaskDefinition(
        subject="Generate Phase Specs",
        description="Read audit-phasing.md. Discover phases from gaps. Generate phasing-overview.md + per-phase specs.",
        active_form="Generating phase specifications",
    ),
    "external-review": TaskDefinition(
        subject="External LLM Review",
        description="Read external-review.md. Focus: missing gaps, wrong build-vs-buy, phasing errors.",
        active_form="Running external LLM review",
    ),
    "user-review": TaskDefinition(
        subject="User Review",
        description="Present audit directory to user for review and feedback.",
        active_form="Waiting for user review",
    ),
    "output-summary": TaskDefinition(
        subject="Output Summary",
        description="Generate README.md index. Print file listing and next steps.",
        active_form="Outputting summary",
    ),
}




# ============================================================================
# GOALLOOP WORKFLOW DEFINITIONS
# ============================================================================

# The control layer only. Each iteration's plan and implement work runs in its
# own nested session under `iterations/iNN/`, with its own tracker — so these
# steps are the scaffolding around the loop, not the SDLC steps themselves.
# `run-iterations` is one issue that stays open for the whole run.
GOALLOOP_TASK_IDS: dict[int, str] = {
    4: "capture-goal",
    5: "probe-target",
    6: "goal-questions",
    7: "initial-ledger",
    8: "run-iterations",
    9: "goal-verification",
    10: "output-summary",
}

GOALLOOP_TASK_ID_TO_STEP: dict[str, int] = {
    v: k for k, v in GOALLOOP_TASK_IDS.items()
}

GOALLOOP_STEP_NAMES: dict[int, str] = {
    0: "Context check",
    1: "Validate environment",
    2: "Resolve goal and target",
    3: "Setup session",
    4: "Capture goal and acceptance lines",
    5: "Probe the target",
    6: "Clarification round (information-gain gated)",
    7: "Decompose into the initial ledger",
    8: "Run iterations until the goal or a stop",
    9: "Goal verification (three-clause done test)",
    10: "Output summary",
}

GOALLOOP_TASK_DEPENDENCIES: dict[str, list[str]] = {
    # Context items
    "context-plugin-root": ["output-summary"],
    "context-planning-dir": ["output-summary"],
    "context-initial-file": ["output-summary"],
    "context-review-mode": ["output-summary"],
    # Control flow. Questions come before decomposition because the answers
    # decide how the goal splits; probing comes before both because the repo
    # settles most of what there is to ask about.
    "capture-goal": [],
    "probe-target": ["capture-goal"],
    "goal-questions": ["probe-target"],
    "initial-ledger": ["goal-questions"],
    "run-iterations": ["initial-ledger"],
    "goal-verification": ["run-iterations"],
    "output-summary": ["goal-verification"],
}

GOALLOOP_TASK_DEFINITIONS: dict[str, TaskDefinition] = {
    "capture-goal": TaskDefinition(
        subject="Capture Goal",
        description=(
            "Read goalloop-protocol.md §0-§1. If the invocation carried no "
            "goal or no acceptance line, elicit them per §0 — ask, do not "
            "invent, and do not refuse the invocation. Record the end state in "
            "the user's words, keep each acceptance line an observation "
            "someone could make rather than a feeling, and run `check-goal` "
            "before `init`."
        ),
        active_form="Capturing the goal",
    ),
    "probe-target": TaskDefinition(
        subject="Probe Target",
        description=(
            "Read goalloop-protocol.md §2. If the target has no discovery "
            "artifacts, run the audit workflow at --depth quick and use its "
            "findings. If this issue names an existing findings path, ingest "
            "that instead and do not re-audit. Either way, this step is what "
            "keeps the clarification round from asking about things the "
            "codebase already states."
        ),
        active_form="Probing the target",
    ),
    "goal-questions": TaskDefinition(
        subject="Clarification Round",
        description=(
            "Read question-selection.md. Enumerate the live hypotheses for how "
            "the goal could be met, score candidate questions with "
            "pick-questions.py at --budget 2, ask only what it returns, and "
            "record the residual uncertainty as a stated assumption."
        ),
        active_form="Running the clarification round",
    ),
    "initial-ledger": TaskDefinition(
        subject="Initial Ledger",
        description=(
            "Read goalloop-protocol.md §3. Decompose the goal into ordered, "
            "individually shippable increments, each with its own one-line "
            "acceptance test. Add them with `goalloop.py add`."
        ),
        active_form="Decomposing the goal into increments",
    ),
    "run-iterations": TaskDefinition(
        subject="Run Iterations",
        description=(
            "Read goalloop-protocol.md §4. Stays open for the whole run. Per "
            "iteration: begin, write the increment as an intent, plan it, "
            "implement it, record evidence, end, tick. Close this issue only "
            "when tick stops returning 3."
        ),
        active_form="Running iterations",
    ),
    "goal-verification": TaskDefinition(
        subject="Goal Verification",
        description=(
            "Read goalloop-protocol.md §5. Run `goalloop.py tick` one final "
            "time and report its verdict verbatim. Do not restate an unmet "
            "clause as met."
        ),
        active_form="Verifying the goal",
    ),
    "output-summary": TaskDefinition(
        subject="Output Summary",
        description=(
            "Write goal-summary.md from `goalloop.py handoff`. Append the "
            "needs-human queue from every iteration directory. A run that "
            "stops without saying what is left has not reported."
        ),
        active_form="Outputting summary",
    ),
}
