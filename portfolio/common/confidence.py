"""Confidence signals, scoring, and activity state (HANDOFF.md §2).

The signal table is fixed by the handoff; scoring is 0–1 missing → high,
2–3 → medium, 4+ → low. `activity_state` derives from last_commit with the
60/180-day thresholds. Both are recomputed wholesale on every sync run.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

# (flag name on RepoFacts, message recorded when the signal is missing)
SIGNAL_TABLE: list[tuple[str, str]] = [
    ("readme_present", "no README"),
    ("readme_fresh", "README appears stale"),
    ("contributing_present", "no CONTRIBUTING.md"),
    ("architecture_present", "no ARCHITECTURE.md"),
    ("recent_commits", "no recent commit activity"),
    ("tests_dir", "no tests directory detected"),
    ("ci_config", "no CI config detected"),
    ("releases_present", "no releases tagged"),
]

STAGES = ["research", "design", "development", "testing", "deployment", "support"]


@dataclass
class RepoFacts:
    """Everything the sync/ingest pipeline needs to know about one repo.

    Produced by a data source (GitHub API or a fixture file) — consumers
    never talk to the network themselves, which is what keeps the whole
    pipeline testable off-site.
    """

    repo: str
    default_branch: str = "main"
    description: str = ""
    language: str | None = None
    visibility: str = "private"
    archived: bool = False
    fork: bool = False
    last_commit: dt.date | None = None
    open_issues: int = 0
    latest_release: str | None = None
    readme_present: bool = False
    readme_last_commit: dt.date | None = None
    contributing_present: bool = False
    architecture_present: bool = False
    tests_dir: bool = False
    ci_config: bool = False
    releases_present: bool = False
    roadmap_present: bool = False
    roadmap_last_updated: dt.date | None = None
    extra: dict = field(default_factory=dict)

    # Derived, injectable-today variants -------------------------------------
    def recent_commits(self, today: dt.date) -> bool:
        return self.last_commit is not None and (today - self.last_commit).days <= 90

    def readme_fresh(self) -> bool:
        """Approximation of "README updated within ~1 commit-era of latest
        code" (HANDOFF §2): fresh iff its last commit is within 180 days of
        the repo's last commit. Documented approximation — revisit with D8."""
        if not self.readme_present:
            return False
        if self.readme_last_commit is None or self.last_commit is None:
            return True  # can't tell -> don't double-penalise beyond "present"
        return (self.last_commit - self.readme_last_commit).days <= 180


def missing_signals(facts: RepoFacts, today: dt.date) -> list[str]:
    flags = {
        "readme_present": facts.readme_present,
        "readme_fresh": facts.readme_fresh() if facts.readme_present else True,
        # ^ "stale README" only applies when a README exists; absence is
        #   already recorded by readme_present.
        "contributing_present": facts.contributing_present,
        "architecture_present": facts.architecture_present,
        "recent_commits": facts.recent_commits(today),
        "tests_dir": facts.tests_dir,
        "ci_config": facts.ci_config,
        "releases_present": facts.releases_present,
    }
    return [msg for key, msg in SIGNAL_TABLE if not flags[key]]


def confidence(missing: list[str]) -> str:
    n = len(missing)
    if n <= 1:
        return "high"
    if n <= 3:
        return "medium"
    return "low"


def activity_state(last_commit: dt.date | None, today: dt.date) -> str:
    """active (<60d) | idle (60–180d) | stale (>180d or unknown)."""
    if last_commit is None:
        return "stale"
    days = (today - last_commit).days
    if days < 60:
        return "active"
    if days <= 180:
        return "idle"
    return "stale"


def infer_stage(facts: RepoFacts, today: dt.date) -> str:
    """Best-effort stage guess for a bootstrap draft (human-reviewed later)."""
    if facts.recent_commits(today):
        return "development"
    if facts.releases_present:
        return "support"
    return "research"
