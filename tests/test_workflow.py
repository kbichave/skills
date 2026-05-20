"""Tests for scripts/lib/workflow.py — Workflow Issue Factory."""

from __future__ import annotations

import pytest
from pathlib import Path

from lib.deepstate import DeepStateTracker
from lib.workflow import (
    create_plan_workflow,
    create_discovery_workflow,
    create_section_issues,
    create_autonomous_workflow,
    _toposort,
    _has_discovery_artifacts,
    _REFERENCE_FILES,
    _AUDIT_REFERENCE_FILES,
    _CONTEXT_TASK_IDS,
)
from lib.tasks import (
    TASK_IDS,
    TASK_DEFINITIONS,
    TASK_DEPENDENCIES,
    AUDIT_TASK_IDS,
    AUDIT_TASK_DEFINITIONS,
    AUDIT_TASK_DEPENDENCIES,
)


@pytest.fixture
def tracker(tmp_path):
    """Fresh DeepStateTracker backed by tmp_path."""
    return DeepStateTracker(state_dir=tmp_path / ".deepstate")


@pytest.fixture
def plan_context(tmp_path):
    """Standard context kwargs for create_plan_workflow."""
    return {
        "plugin_root": "/fake/plugin",
        "planning_dir": str(tmp_path / "planning"),
        "initial_file": str(tmp_path / "spec.md"),
        "review_mode": "external_llm",
    }


@pytest.fixture
def sections_dir(tmp_path):
    """Create a sections/index.md with depends_on syntax."""
    planning = tmp_path / "planning"
    sections = planning / "sections"
    sections.mkdir(parents=True)
    index = sections / "index.md"
    index.write_text(
        "<!-- SECTION_MANIFEST\n"
        "section-01-alpha\n"
        "section-02-beta depends_on:section-01-alpha\n"
        "section-03-gamma depends_on:section-01-alpha,section-02-beta\n"
        "END_MANIFEST -->\n\n"
        "```PROJECT_CONFIG\n"
        "runtime: python-uv\n"
        "test_command: uv run pytest\n"
        "```\n"
    )
    return planning


# ── create_plan_workflow ────────────────────────────────────────────


class TestCreatePlanWorkflow:
    def test_creates_17_step_issues(self, tracker, plan_context):
        create_plan_workflow(tracker, **plan_context)
        issues = tracker.list_issues()
        assert len(issues) == 17

    def test_epic_title_contains_spec_name(self, tracker, plan_context):
        title = create_plan_workflow(tracker, **plan_context)
        assert title == "deep-plan: spec"

    def test_stores_context_in_epic(self, tracker, plan_context):
        create_plan_workflow(tracker, **plan_context)
        state = tracker._load()
        ctx = state["epic"]["context"]
        assert ctx["plugin_root"] == plan_context["plugin_root"]
        assert ctx["planning_dir"] == plan_context["planning_dir"]
        assert ctx["initial_file"] == plan_context["initial_file"]
        assert ctx["review_mode"] == plan_context["review_mode"]

    def test_dependency_edges_match_task_dependencies(self, tracker, plan_context):
        create_plan_workflow(tracker, **plan_context)
        for task_id in TASK_IDS.values():
            issue = tracker.show(task_id)
            expected_deps = [
                d for d in TASK_DEPENDENCIES.get(task_id, [])
                if d not in _CONTEXT_TASK_IDS
            ]
            assert issue["depends_on"] == expected_deps, (
                f"{task_id}: expected deps {expected_deps}, got {issue['depends_on']}"
            )

    def test_execute_research_depends_on_research_decision(self, tracker, plan_context):
        create_plan_workflow(tracker, **plan_context)
        issue = tracker.show("execute-research")
        assert "research-decision" in issue["depends_on"]

    def test_descriptions_include_reference_pointer(self, tracker, plan_context):
        create_plan_workflow(tracker, **plan_context)
        for task_id, ref_file in _REFERENCE_FILES.items():
            issue = tracker.show(task_id)
            assert f"**Reference:**" in issue["description"]
            assert ref_file in issue["description"]

    def test_descriptions_include_acceptance_criteria(self, tracker, plan_context):
        create_plan_workflow(tracker, **plan_context)
        issue = tracker.show("research-decision")
        assert "**Acceptance Criteria:**" in issue["description"]

    def test_descriptions_include_resume_here(self, tracker, plan_context):
        create_plan_workflow(tracker, **plan_context)
        issue = tracker.show("research-decision")
        assert "**Resume Here:**" in issue["description"]

    def test_no_context_tasks_created(self, tracker, plan_context):
        create_plan_workflow(tracker, **plan_context)
        for ctx_id in _CONTEXT_TASK_IDS:
            with pytest.raises(KeyError):
                tracker.show(ctx_id)

    def test_all_issues_are_open(self, tracker, plan_context):
        create_plan_workflow(tracker, **plan_context)
        for issue in tracker.list_issues():
            assert issue["status"] == "open"

    # ── discovery_findings param ───────────────────────────────────

    def test_no_discovery_uses_standard_interview(self, tracker, plan_context):
        """Without discovery_findings, interview uses interview-protocol.md."""
        create_plan_workflow(tracker, **plan_context)
        issue = tracker.show("detailed-interview")
        assert "interview-protocol.md" in issue["description"]
        assert "discovery-bridge.md" not in issue["description"]

    def test_with_discovery_artifacts_uses_bridge(self, tracker, plan_context, tmp_path):
        """When discovery artifacts exist, interview step uses bridge passthrough."""
        discovery_dir = tmp_path / "discovery"
        discovery_dir.mkdir()
        (discovery_dir / "interview.md").write_text("Q: foo\nA: bar")
        (discovery_dir / "findings").mkdir()
        (discovery_dir / "findings" / "topic-01-auth.md").write_text("finding")

        create_plan_workflow(tracker, **plan_context, discovery_findings=str(discovery_dir))
        issue = tracker.show("detailed-interview")
        assert "discovery-bridge.md" in issue["description"]
        assert "interview-protocol.md" not in issue["description"]
        assert "Do NOT conduct a new interview" in issue["description"]

    def test_with_discovery_artifacts_save_interview_uses_passthrough(self, tracker, plan_context, tmp_path):
        """When discovery artifacts exist, save-interview step uses passthrough description."""
        discovery_dir = tmp_path / "discovery"
        discovery_dir.mkdir()
        (discovery_dir / "interview.md").write_text("Q: foo\nA: bar")
        (discovery_dir / "findings").mkdir()

        create_plan_workflow(tracker, **plan_context, discovery_findings=str(discovery_dir))
        issue = tracker.show("save-interview")
        assert "Derived from discovery interview" in issue["description"]

    def test_discovery_findings_path_missing_interview_falls_back(self, tracker, plan_context, tmp_path):
        """Missing interview.md → _has_discovery_artifacts returns False → standard interview."""
        discovery_dir = tmp_path / "discovery"
        discovery_dir.mkdir()
        # Only findings/ present, no interview.md
        (discovery_dir / "findings").mkdir()

        create_plan_workflow(tracker, **plan_context, discovery_findings=str(discovery_dir))
        issue = tracker.show("detailed-interview")
        assert "interview-protocol.md" in issue["description"]

    def test_discovery_findings_none_falls_back(self, tracker, plan_context):
        """None discovery_findings → standard interview."""
        create_plan_workflow(tracker, **plan_context, discovery_findings=None)
        issue = tracker.show("detailed-interview")
        assert "interview-protocol.md" in issue["description"]


# ── _has_discovery_artifacts ────────────────────────────────────────


class TestHasDiscoveryArtifacts:
    def test_returns_false_for_none(self):
        assert _has_discovery_artifacts(None) is False

    def test_returns_false_for_nonexistent_path(self, tmp_path):
        assert _has_discovery_artifacts(str(tmp_path / "nonexistent")) is False

    def test_returns_false_missing_interview(self, tmp_path):
        (tmp_path / "findings").mkdir()
        assert _has_discovery_artifacts(str(tmp_path)) is False

    def test_returns_false_missing_findings_dir(self, tmp_path):
        (tmp_path / "interview.md").write_text("Q: foo")
        assert _has_discovery_artifacts(str(tmp_path)) is False

    def test_returns_true_with_both(self, tmp_path):
        (tmp_path / "interview.md").write_text("Q: foo")
        (tmp_path / "findings").mkdir()
        assert _has_discovery_artifacts(str(tmp_path)) is True


# ── create_discovery_workflow ───────────────────────────────────────


class TestCreateDiscoveryWorkflow:
    def test_creates_13_step_issues(self, tracker, plan_context):
        # 11 original steps + empirical-data-collection + coverage-validation = 13
        create_discovery_workflow(tracker, **plan_context)
        issues = tracker.list_issues()
        assert len(issues) == 13

    def test_epic_title_contains_spec_name(self, tracker, plan_context):
        title = create_discovery_workflow(tracker, **plan_context)
        assert title == "deep-discovery: spec"

    def test_dependency_chain_matches_audit_dependencies(self, tracker, plan_context):
        create_discovery_workflow(tracker, **plan_context)
        for task_id in AUDIT_TASK_IDS.values():
            issue = tracker.show(task_id)
            expected_deps = [
                d for d in AUDIT_TASK_DEPENDENCIES.get(task_id, [])
                if d not in _CONTEXT_TASK_IDS
            ]
            assert issue["depends_on"] == expected_deps

    def test_deep_research_depends_on_topic_enumeration(self, tracker, plan_context):
        # deep-research now depends on topic-enumeration, not directly on quick-scan
        create_discovery_workflow(tracker, **plan_context)
        issue = tracker.show("deep-research")
        assert "topic-enumeration" in issue["depends_on"]

    def test_topic_enumeration_depends_on_empirical_data(self, tracker, plan_context):
        create_discovery_workflow(tracker, **plan_context)
        issue = tracker.show("topic-enumeration")
        assert "empirical-data-collection" in issue["depends_on"]

    def test_empirical_data_depends_on_quick_scan(self, tracker, plan_context):
        create_discovery_workflow(tracker, **plan_context)
        issue = tracker.show("empirical-data-collection")
        assert "quick-scan" in issue["depends_on"]

    def test_coverage_validation_depends_on_deep_research(self, tracker, plan_context):
        create_discovery_workflow(tracker, **plan_context)
        issue = tracker.show("coverage-validation")
        assert "deep-research" in issue["depends_on"]

    def test_auto_gaps_depends_on_coverage_validation(self, tracker, plan_context):
        create_discovery_workflow(tracker, **plan_context)
        issue = tracker.show("auto-gaps")
        assert "coverage-validation" in issue["depends_on"]

    def test_descriptions_include_audit_reference_files(self, tracker, plan_context):
        create_discovery_workflow(tracker, **plan_context)
        for task_id, ref_file in _AUDIT_REFERENCE_FILES.items():
            issue = tracker.show(task_id)
            assert ref_file in issue["description"]


class TestPlanExpressPath:
    def test_express_prd_precloses_research_and_interview(self, tracker, plan_context):
        create_plan_workflow(
            tracker, **plan_context, express_source="/path/to/prd.md", express_kind="prd"
        )
        for skipped in ("research-decision", "execute-research", "detailed-interview", "save-interview"):
            issue = tracker.show(skipped)
            assert issue["status"] == "closed"
            assert "Express path" in (issue.get("closed_reason") or "")
            assert "prd" in (issue.get("closed_reason") or "")

    def test_express_adr_uses_adr_label(self, tracker, plan_context):
        create_plan_workflow(
            tracker, **plan_context, express_source="/path/to/adrs", express_kind="adr"
        )
        issue = tracker.show("research-decision")
        assert "adr" in (issue.get("closed_reason") or "")

    def test_express_keeps_plan_steps_open(self, tracker, plan_context):
        create_plan_workflow(
            tracker, **plan_context, express_source="/path/to/prd.md", express_kind="prd"
        )
        for task_id in ("write-spec", "generate-plan", "external-review", "user-review"):
            assert tracker.show(task_id)["status"] == "open"

    def test_express_write_spec_description_references_source(self, tracker, plan_context):
        create_plan_workflow(
            tracker, **plan_context, express_source="/x/prd.md", express_kind="prd"
        )
        desc = tracker.show("write-spec")["description"]
        assert "/x/prd.md" in desc
        assert "Express path" in desc

    def test_no_express_keeps_research_open(self, tracker, plan_context):
        create_plan_workflow(tracker, **plan_context)
        for task_id in ("research-decision", "execute-research"):
            assert tracker.show(task_id)["status"] == "open"

    def test_express_invalid_kind_raises(self, tracker, plan_context):
        with pytest.raises(ValueError, match="express_kind"):
            create_plan_workflow(
                tracker, **plan_context, express_source="/x", express_kind="rfc"
            )


class TestDiscoveryDepth:
    def test_standard_depth_keeps_all_open(self, tracker, plan_context):
        create_discovery_workflow(tracker, **plan_context, depth="standard")
        # All non-context audit tasks should be open
        for task_id in AUDIT_TASK_IDS.values():
            assert tracker.show(task_id)["status"] == "open"

    def test_quick_depth_preclose_excluded_steps(self, tracker, plan_context):
        create_discovery_workflow(tracker, **plan_context, depth="quick")
        skipped = {
            "deep-research",
            "coverage-validation",
            "auto-gaps",
            "generate-build-vs-buy",
            "external-review",
        }
        for task_id in skipped:
            issue = tracker.show(task_id)
            assert issue["status"] == "closed"
            assert "depth=quick" in (issue.get("closed_reason") or "")

    def test_quick_depth_keeps_load_bearing_steps_open(self, tracker, plan_context):
        create_discovery_workflow(tracker, **plan_context, depth="quick")
        # Topic enumeration (load-bearing) and interview must remain open
        for task_id in ("quick-scan", "topic-enumeration", "stakeholder-interview",
                        "generate-audit-docs", "generate-phase-specs"):
            assert tracker.show(task_id)["status"] == "open"

    def test_deep_depth_adds_cross_verify_note(self, tracker, plan_context):
        create_discovery_workflow(tracker, **plan_context, depth="deep")
        for task_id in ("deep-research", "coverage-validation"):
            assert "cross-verify" in tracker.show(task_id)["description"].lower()

    def test_standard_depth_no_cross_verify_note(self, tracker, plan_context):
        create_discovery_workflow(tracker, **plan_context, depth="standard")
        for task_id in ("deep-research", "coverage-validation"):
            assert "cross-verify" not in tracker.show(task_id)["description"].lower()

    def test_unknown_depth_raises(self, tracker, plan_context):
        with pytest.raises(ValueError, match="Unknown depth"):
            create_discovery_workflow(tracker, **plan_context, depth="ultra")

    def test_depth_stored_in_context(self, tracker, plan_context):
        create_discovery_workflow(tracker, **plan_context, depth="quick")
        state = tracker._load()
        assert state["epic"]["context"]["depth"] == "quick"


# ── create_section_issues ───────────────────────────────────────────


class TestCreateSectionIssues:
    def test_creates_one_issue_per_section_plus_two(self, tracker, sections_dir):
        """3 sections + final-verification + output-summary = 5 issues."""
        tracker.init("test", {"planning_dir": str(sections_dir)})
        # Pre-create the generate-section-tasks step so deps can reference it
        tracker.create("generate-section-tasks", "Generate Section Tasks")
        mapping = create_section_issues(
            tracker, planning_dir=str(sections_dir), plugin_root="/fake"
        )
        # 3 sections + generate-section-tasks (pre-existing) + final-verification + output-summary
        issues = tracker.list_issues()
        assert len(issues) == 6

    def test_returns_section_mapping(self, tracker, sections_dir):
        tracker.init("test", {"planning_dir": str(sections_dir)})
        tracker.create("generate-section-tasks", "Generate Section Tasks")
        mapping = create_section_issues(
            tracker, planning_dir=str(sections_dir), plugin_root="/fake"
        )
        assert "section-01-alpha" in mapping
        assert "section-02-beta" in mapping
        assert "section-03-gamma" in mapping

    def test_dependency_edges_from_depends_on(self, tracker, sections_dir):
        tracker.init("test", {"planning_dir": str(sections_dir)})
        tracker.create("generate-section-tasks", "Generate Section Tasks")
        create_section_issues(
            tracker, planning_dir=str(sections_dir), plugin_root="/fake"
        )
        beta = tracker.show("section-02-beta")
        assert "section-01-alpha" in beta["depends_on"]

    def test_section_without_explicit_deps_depends_on_generate_step(self, tracker, sections_dir):
        tracker.init("test", {"planning_dir": str(sections_dir)})
        tracker.create("generate-section-tasks", "Generate Section Tasks")
        create_section_issues(
            tracker, planning_dir=str(sections_dir), plugin_root="/fake"
        )
        alpha = tracker.show("section-01-alpha")
        assert "generate-section-tasks" in alpha["depends_on"]

    def test_final_verification_blocked_by_all_sections(self, tracker, sections_dir):
        tracker.init("test", {"planning_dir": str(sections_dir)})
        tracker.create("generate-section-tasks", "Generate Section Tasks")
        mapping = create_section_issues(
            tracker, planning_dir=str(sections_dir), plugin_root="/fake"
        )
        fv = tracker.show("final-verification")
        for section_name in mapping:
            assert section_name in fv["depends_on"]

    def test_output_summary_blocked_by_final_verification(self, tracker, sections_dir):
        tracker.init("test", {"planning_dir": str(sections_dir)})
        tracker.create("generate-section-tasks", "Generate Section Tasks")
        create_section_issues(
            tracker, planning_dir=str(sections_dir), plugin_root="/fake"
        )
        os = tracker.show("output-summary")
        assert "final-verification" in os["depends_on"]

    def test_resume_skips_existing_issues(self, tracker, sections_dir):
        """If an issue already exists, create_section_issues skips it."""
        tracker.init("test", {"planning_dir": str(sections_dir)})
        tracker.create("generate-section-tasks", "Generate Section Tasks")
        # First call creates all
        create_section_issues(
            tracker, planning_dir=str(sections_dir), plugin_root="/fake"
        )
        # Close one section
        tracker.close("section-01-alpha", "done")
        # Second call should not re-create it
        mapping = create_section_issues(
            tracker, planning_dir=str(sections_dir), plugin_root="/fake"
        )
        alpha = tracker.show("section-01-alpha")
        assert alpha["status"] == "closed"

    def test_missing_index_raises_file_not_found(self, tracker, tmp_path):
        tracker.init("test", {"planning_dir": str(tmp_path / "nonexistent")})
        with pytest.raises(FileNotFoundError):
            create_section_issues(
                tracker, planning_dir=str(tmp_path / "nonexistent"), plugin_root="/fake"
            )

    def test_gamma_depends_on_both_alpha_and_beta(self, tracker, sections_dir):
        tracker.init("test", {"planning_dir": str(sections_dir)})
        tracker.create("generate-section-tasks", "Generate Section Tasks")
        create_section_issues(
            tracker, planning_dir=str(sections_dir), plugin_root="/fake"
        )
        gamma = tracker.show("section-03-gamma")
        assert "section-01-alpha" in gamma["depends_on"]
        assert "section-02-beta" in gamma["depends_on"]


# ── create_autonomous_workflow ──────────────────────────────────────


class TestToposort:
    def test_linear_chain(self):
        deps = {"P00": [], "P01": ["P00"], "P02": ["P01"]}
        assert _toposort(deps) == ["P00", "P01", "P02"]

    def test_forward_reference(self):
        """P01 depends on P08 — lower number depends on higher."""
        deps = {"P00": [], "P01": ["P08"], "P08": ["P00"]}
        result = _toposort(deps)
        assert result.index("P00") < result.index("P08")
        assert result.index("P08") < result.index("P01")

    def test_diamond(self):
        deps = {"P00": [], "P01": ["P00"], "P02": ["P00"], "P03": ["P01", "P02"]}
        result = _toposort(deps)
        assert result.index("P00") < result.index("P01")
        assert result.index("P00") < result.index("P02")
        assert result.index("P01") < result.index("P03")
        assert result.index("P02") < result.index("P03")

    def test_deterministic_order_for_independent_phases(self):
        deps = {"P03": [], "P01": [], "P02": []}
        assert _toposort(deps) == ["P01", "P02", "P03"]

    def test_cycle_raises(self):
        deps = {"P00": ["P01"], "P01": ["P00"]}
        with pytest.raises(ValueError, match="Cycle"):
            _toposort(deps)


class TestCreateAutonomousWorkflow:
    def test_requires_valid_phases_dir(self, tracker):
        """parse_phasing_overview raises FileNotFoundError for missing dir."""
        with pytest.raises(FileNotFoundError):
            create_autonomous_workflow(
                tracker,
                phases_dir="/nonexistent",
                plugin_root="/fake",
                discovery_findings="/fake",
            )

    def test_forward_dependency_succeeds(self, tmp_path):
        """Forward-dependency support: P01 may depend on P08."""
        tracker = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        phases_dir = tmp_path / "phases"
        phases_dir.mkdir()
        (phases_dir / "phasing-overview.md").write_text(
            "## Dependency Graph\n\n"
            "P00 ──→ P08 ──→ P01\n"
        )
        create_autonomous_workflow(
            tracker,
            phases_dir=str(phases_dir),
            plugin_root="/fake",
            discovery_findings="/fake",
        )
        p01 = tracker.show("phase-P01")
        assert "phase-P08" in p01["depends_on"]

    def test_autonomous_first_phase_uses_bridge_when_discovery_exists(self, tmp_path):
        """auto first phase uses bridge passthrough when discovery artifacts present."""
        tracker = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        phases_dir = tmp_path / "phases"
        phases_dir.mkdir()
        (phases_dir / "phasing-overview.md").write_text(
            "## Dependency Graph\n\nP01\n"
        )
        discovery_dir = tmp_path
        (discovery_dir / "interview.md").write_text("Q: foo\nA: bar")
        (discovery_dir / "findings").mkdir()

        create_autonomous_workflow(
            tracker,
            phases_dir=str(phases_dir),
            plugin_root="/fake",
            discovery_findings=str(discovery_dir),
        )
        issue = tracker.show("P01-detailed-interview")
        assert "discovery-bridge.md" in issue["description"]
        assert "SELF-INTERVIEW" not in issue["description"]

    def test_autonomous_first_phase_self_interviews_without_discovery(self, tmp_path):
        """auto first phase uses self-interview when no discovery artifacts."""
        tracker = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        phases_dir = tmp_path / "phases"
        phases_dir.mkdir()
        (phases_dir / "phasing-overview.md").write_text(
            "## Dependency Graph\n\nP01\n"
        )
        # No discovery artifacts

        create_autonomous_workflow(
            tracker,
            phases_dir=str(phases_dir),
            plugin_root="/fake",
            discovery_findings=str(tmp_path),
        )
        issue = tracker.show("P01-detailed-interview")
        assert "SELF-INTERVIEW" in issue["description"]
