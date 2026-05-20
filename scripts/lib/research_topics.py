"""ResearchTopicStore — flat-file research topic storage.

Reads/writes research-topics.yaml in the session directory.

Usage:
    store = ResearchTopicStore.create(planning_dir=Path("..."), project_slug="my-api-a3f9c1")
    store.create_topic("rt-01", "Authentication & Authorization", "security", "high", ["Q1", "Q2"])
    store.set_status("rt-01", "covered", findings_file="findings/rt-01-auth.md")
    missing = store.get_missing()
    pct = store.coverage_pct()
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TOPICS_FILENAME = "research-topics.yaml"


# ── Abstract interface ────────────────────────────────────────────────────────


class ResearchTopicStore(ABC):
    """Abstract interface for research topic storage."""

    @abstractmethod
    def create_topic(
        self,
        id: str,
        topic: str,
        category: str,
        priority: str,
        questions: list[str],
    ) -> None:
        """Record a new research topic."""

    @abstractmethod
    def set_status(
        self,
        id: str,
        status: str,
        findings_file: str | None = None,
    ) -> None:
        """Update a topic's status (pending → covered | skipped)."""

    @abstractmethod
    def get_missing(self) -> list[dict[str, Any]]:
        """Return topics that are still pending (not covered, not skipped)."""

    @abstractmethod
    def coverage_pct(self) -> float:
        """Return coverage percentage, excluding skipped topics from denominator."""

    @abstractmethod
    def get_all(self) -> list[dict[str, Any]]:
        """Return all topics with their current status."""

    def search_prior(self, query: str) -> list[dict[str, Any]]:  # noqa: ARG002
        """Search prior-project research for relevant topics.

        Returns []. Reserved for future cross-project backends.
        """
        return []

    @classmethod
    def create(
        cls,
        *,
        planning_dir: Path,
        project_slug: str,  # noqa: ARG003 — reserved for future cross-project backends
    ) -> "ResearchTopicStore":
        """Factory: return FlatFileBackend (only backend)."""
        return FlatFileBackend(planning_dir=planning_dir)


# ── FlatFileBackend ───────────────────────────────────────────────────────────


def _load_yaml_simple(path: Path) -> dict[str, Any]:
    """Load research-topics.yaml. Tries PyYAML, falls back to JSON."""
    content = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import]
        data = yaml.safe_load(content)
        return data if isinstance(data, dict) else {}
    except ImportError:
        pass
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def _dump_yaml_simple(data: dict[str, Any], path: Path) -> None:
    """Write dict as YAML. Uses PyYAML if available, falls back to JSON."""
    try:
        import yaml  # type: ignore[import]
        path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return
    except ImportError:
        pass
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@dataclass
class FlatFileBackend(ResearchTopicStore):
    """Stores research topics in research-topics.yaml inside the session directory."""

    planning_dir: Path

    @property
    def _topics_path(self) -> Path:
        return self.planning_dir / _TOPICS_FILENAME

    def _load(self) -> dict[str, Any]:
        if not self._topics_path.exists():
            return {"metadata": {}, "topics": []}
        return _load_yaml_simple(self._topics_path)

    def _save(self, data: dict[str, Any]) -> None:
        self.planning_dir.mkdir(parents=True, exist_ok=True)
        _dump_yaml_simple(data, self._topics_path)

    def create_topic(
        self,
        id: str,
        topic: str,
        category: str,
        priority: str,
        questions: list[str],
    ) -> None:
        data = self._load()
        topics: list[dict] = data.setdefault("topics", [])
        # Idempotent: skip if already exists
        if any(t.get("id") == id for t in topics):
            return
        topics.append({
            "id": id,
            "topic": topic,
            "category": category,
            "priority": priority,
            "questions": questions,
            "status": "pending",
            "findings_file": None,
        })
        meta = data.setdefault("metadata", {})
        meta["total"] = len(topics)
        meta["covered"] = sum(1 for t in topics if t.get("status") == "covered")
        self._save(data)

    def set_status(
        self,
        id: str,
        status: str,
        findings_file: str | None = None,
    ) -> None:
        data = self._load()
        for t in data.get("topics", []):
            if t.get("id") == id:
                t["status"] = status
                if findings_file is not None:
                    t["findings_file"] = findings_file
                break
        # Recompute metadata counts
        topics = data.get("topics", [])
        meta = data.setdefault("metadata", {})
        covered = [t for t in topics if t.get("status") == "covered"]
        skipped = [t for t in topics if t.get("status") == "skipped"]
        researchable = len(topics) - len(skipped)
        meta["covered"] = len(covered)
        meta["coverage_pct"] = round(len(covered) / researchable * 100, 1) if researchable > 0 else 100.0
        self._save(data)

    def get_missing(self) -> list[dict[str, Any]]:
        data = self._load()
        return [t for t in data.get("topics", []) if t.get("status") == "pending"]

    def coverage_pct(self) -> float:
        data = self._load()
        topics = data.get("topics", [])
        skipped = [t for t in topics if t.get("status") == "skipped"]
        covered = [t for t in topics if t.get("status") == "covered"]
        researchable = len(topics) - len(skipped)
        if researchable == 0:
            return 100.0
        return round(len(covered) / researchable * 100, 1)

    def get_all(self) -> list[dict[str, Any]]:
        return self._load().get("topics", [])
