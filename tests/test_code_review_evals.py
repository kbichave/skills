"""Structural evals for the code-review panel (per "Don't Ship Skills Without Evals").

CI-safe: validates the eval case set and the panel's skill/agent structure
against the doc's rubric. No live model calls.
"""

from __future__ import annotations

import pathlib
import re

import pytest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENTS_DIR = PLUGIN_ROOT / "agents"
CASES_YAML = PLUGIN_ROOT / "tests" / "evals" / "code-review-cases.yaml"
SKILL_MD = PLUGIN_ROOT / "skills" / "code-review" / "SKILL.md"

# Panel members reviewed for structure (the code-review-specific agents).
PANEL_AGENTS = [
    "code-reviewer", "logic-reviewer", "architecture-reviewer", "ml-reviewer",
    "stats-reviewer", "mlops-reviewer", "data-eng-reviewer", "prompt-reviewer",
    "skill-reviewer", "claim-verifier", "review-verifier",
]

# Agents the SKILL.md routing table spawns as the panel (deep:<name>).
ROUTED_AGENTS = [
    "code-reviewer", "logic-reviewer", "architecture-reviewer", "ml-reviewer",
    "stats-reviewer", "mlops-reviewer", "data-eng-reviewer", "skill-reviewer",
    "prompt-reviewer",
]

NOOP_PATTERNS = re.compile(
    r"\b(be thorough|write clean|high.quality code|as appropriate\b.*handle|"
    r"make sure to handle errors appropriately)\b",
    re.IGNORECASE,
)


def _frontmatter(text: str) -> dict[str, str]:
    assert text.startswith("---"), "missing frontmatter"
    end = text.index("---", 3)
    fm: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


@pytest.fixture(scope="module")
def cases():
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(CASES_YAML.read_text())


# --- eval case set shape ---

class TestCaseSet:
    def test_yaml_loads_and_targets_code_review(self, cases):
        assert cases["skill"] == "code-review"
        assert isinstance(cases["cases"], list)

    def test_case_mix_golden_negative_edge(self, cases):
        ids = [c["id"] for c in cases["cases"]]
        golden = [i for i in ids if i.startswith("golden-")]
        neg = [i for i in ids if i.startswith("neg-")]
        edge = [i for i in ids if i.startswith("edge-")]
        assert len(golden) >= 5, "need >=5 golden happy-path cases"
        assert len(neg) >= 5, "need >=5 negative/near-miss cases"
        assert len(edge) >= 5, "need >=5 edge cases"

    def test_unique_ids_and_required_fields(self, cases):
        ids = [c["id"] for c in cases["cases"]]
        assert len(ids) == len(set(ids)), "duplicate case ids"
        for c in cases["cases"]:
            assert "prompt" in c and c["prompt"].strip()
            assert isinstance(c["should_trigger"], bool)

    def test_negative_cases_have_no_checks(self, cases):
        for c in cases["cases"]:
            if c["should_trigger"] is False:
                assert not c.get("checks"), f"{c['id']}: negative case should assert non-trigger only"

    def test_every_referenced_check_is_defined(self, cases):
        defined = set(cases["checks"].keys())
        for c in cases["cases"]:
            for check in c.get("checks", []):
                assert check in defined, f"{c['id']} references undefined check '{check}'"

    def test_ablation_block_present(self, cases):
        # Tip 8: retirement/ablation must be declared.
        assert "ablation" in cases and cases["ablation"].get("cadence")


# --- panel agent structure (the doc's rubric) ---

class TestAgentStructure:
    @pytest.mark.parametrize("name", PANEL_AGENTS)
    def test_agent_file_exists(self, name):
        assert (AGENTS_DIR / f"{name}.md").is_file()

    @pytest.mark.parametrize("name", PANEL_AGENTS)
    def test_frontmatter_and_name_matches_file(self, name):
        fm = _frontmatter((AGENTS_DIR / f"{name}.md").read_text())
        assert fm.get("name") == name
        assert fm.get("description", "").strip()
        assert fm.get("tools", "").strip()

    @pytest.mark.parametrize("name", PANEL_AGENTS)
    def test_agent_lean_under_500_lines(self, name):
        n = len((AGENTS_DIR / f"{name}.md").read_text().splitlines())
        assert n <= 500, f"{name}.md has {n} lines (doc bloat threshold)"

    @pytest.mark.parametrize("name", PANEL_AGENTS)
    def test_no_decorative_noops(self, name):
        text = (AGENTS_DIR / f"{name}.md").read_text()
        # Strip quoted and backtick spans: agents like skill-reviewer legitimately
        # quote fluff phrases ("be thorough") as examples of what to flag.
        scannable = re.sub(r'"[^"]*"|`[^`]*`', "", text)
        hit = NOOP_PATTERNS.search(scannable)
        assert hit is None, f"{name}.md contains a no-op: {hit.group(0)!r}"


# --- skill description + routing consistency ---

class TestSkillDescription:
    def test_description_has_negative_cases(self):
        fm = _frontmatter(SKILL_MD.read_text())
        desc = fm.get("description", "")
        assert "Do NOT" in desc or "do not use" in desc.lower(), \
            "SKILL.md description must exclude adjacent cases (anti-hijack)"

    def test_body_lean(self):
        n = len(SKILL_MD.read_text().splitlines())
        assert n <= 500, f"SKILL.md body is {n} lines"

    @pytest.mark.parametrize("name", ROUTED_AGENTS)
    def test_routing_table_lists_existing_agent(self, name):
        text = SKILL_MD.read_text()
        assert f"deep:{name}" in text, f"routing omits deep:{name}"
        assert (AGENTS_DIR / f"{name}.md").is_file()

    def test_step8_uses_marker_script_not_prose_math(self):
        text = SKILL_MD.read_text()
        assert "apply-review-markers.py" in text, "step 8 must delegate to the marker script"
