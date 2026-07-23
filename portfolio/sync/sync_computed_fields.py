"""Nightly sync — rebuild each note's `computed:` block. THE single writer.

For every project note with a `repo` set (drafts included — plan F8): fetch
repo facts from the configured source and rebuild the nested `computed:`
frontmatter key wholesale — last_commit, open_issues, latest_release,
language, archived_on_github, activity_state (active <60d / idle 60–180d /
stale >180d), summary_confidence, missing_signals, roadmap_last_updated,
last_synced.

HARD RULE (CLAUDE.md #2): parse → replace ONLY the `computed:` key →
serialize. Enforced three ways: (1) the write is a textual splice via
common.frontmatter, never a YAML round-trip (plan F6); (2) a
verify_untouched() guard aborts if any unowned key would change; (3) the
test suite asserts byte-identity of everything outside the computed span.

No-op guard (plan F7): a note is rewritten only when something *other than*
`last_synced` changed, so nightly runs don't bury real changes in vault-git
commit churn. The global "last sync ran" line lives on the dashboard note
between `<!-- sync:last-run -->` markers instead.

Run it against a throwaway note first (fixture source, --dry-run):

    python3 sync/sync_computed_fields.py --vault /path/to/vault \
        --source fixture:sync/fixture.example.json --dry-run

Phase 1+: Paperclip becomes a second source here (computed.cost_by_stage,
cost_total_mtd, team_status, open_reviews per D9) — this job stays the only
writer either way (../../harness/HANDOFF-agentic-harness.md §5).

Contract: HANDOFF.md §5, Task 6.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import frontmatter as fmt  # noqa: E402
from common import vault as vaultlib  # noqa: E402
from common.confidence import RepoFacts, activity_state, confidence, missing_signals  # noqa: E402
from common.github_api import SourceError, parse_source_arg  # noqa: E402

OWNED_KEYS = {"computed"}

COMPUTED_ORDER = [
    "last_commit", "open_issues", "latest_release", "language",
    "archived_on_github", "activity_state", "summary_confidence",
    "missing_signals", "roadmap_last_updated", "last_synced",
]
COMPUTED_COMMENTS = {
    "activity_state": "active (<60d) | idle (60-180d) | stale (>180d)",
    "summary_confidence": "high | medium | low",
}

_LAST_SYNCED_LINE = re.compile(r"^\s*last_synced\s*:.*\r?\n?$", re.MULTILINE)


def build_computed(facts: RepoFacts, today: dt.date, now: dt.datetime) -> dict:
    missing = missing_signals(facts, today)
    return {
        "last_commit": facts.last_commit,
        "open_issues": facts.open_issues,
        "latest_release": facts.latest_release,
        "language": facts.language,
        "archived_on_github": facts.archived,
        "activity_state": activity_state(facts.last_commit, today),
        "summary_confidence": confidence(missing),
        "missing_signals": missing,
        "roadmap_last_updated": facts.roadmap_last_updated,
        "last_synced": now,
    }


def sync_note_text(text: str, facts: RepoFacts, today: dt.date, now: dt.datetime) -> tuple[str, bool]:
    """Pure function: (note text, facts) -> (new text, changed?)."""
    head, fm, tail = fmt.split_note(text)
    nl = fmt.newline_of(fm or text)
    computed = build_computed(facts, today, now)
    new_block = fmt.emit_mapping_block(
        "computed", computed, comments=COMPUTED_COMMENTS, order=COMPUTED_ORDER, nl=nl
    )
    old_block = fmt.get_block(fm, "computed") or ""
    if _LAST_SYNCED_LINE.sub("", old_block) == _LAST_SYNCED_LINE.sub("", new_block):
        return text, False  # F7: only last_synced would change -> leave the note alone
    new_fm = fmt.replace_key_block(fm, "computed", new_block)
    fmt.verify_untouched(fm, new_fm, OWNED_KEYS)
    return fmt.join_note(head, new_fm, tail), True


@dataclass
class Report:
    checked: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_no_repo: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)

    def summary(self, now: dt.datetime) -> str:
        line = (
            f"Last sync: {now.replace(microsecond=0).isoformat(sep=' ')} — "
            f"{self.checked} checked, {self.updated} updated, "
            f"{self.unchanged} unchanged, {len(self.errors)} errors."
        )
        if self.errors:
            line += "\n" + "\n".join(f"- ⚠ {p}: {e}" for p, e in self.errors)
        return line


def run(vault: Path, source, *, only_project: str | None = None, dry_run: bool = False,
        dashboard_name: str = "dashboard.md", today: dt.date | None = None,
        now: dt.datetime | None = None, out=sys.stdout) -> Report:
    today = today or dt.date.today()
    now = now or dt.datetime.now()
    report = Report()

    for path in vaultlib.iter_notes(vault):
        text = vaultlib.read_note(path)
        try:
            _, fm, _ = fmt.split_note(text)
            parsed = fmt.parse(fm)
        except fmt.FrontmatterError:
            continue  # not a project note
        project = parsed.get("project")
        repo = parsed.get("repo")
        if only_project and project != only_project:
            continue
        if not project:
            continue
        if not repo:
            report.skipped_no_repo += 1  # roadmap ideas have no repo yet
            continue
        report.checked += 1
        try:
            facts = source.fetch(str(repo))
        except SourceError as exc:
            report.errors.append((project, str(exc)))
            continue
        try:
            new_text, changed = sync_note_text(text, facts, today, now)
        except fmt.FrontmatterError as exc:
            report.errors.append((project, f"refused: {exc}"))
            continue
        if not changed:
            report.unchanged += 1
            continue
        report.updated += 1
        if dry_run:
            out.writelines(
                difflib.unified_diff(
                    text.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=str(path),
                    tofile=f"{path} (dry-run)",
                )
            )
        else:
            vaultlib.write_note_atomic(path, new_text)

    if not dry_run and not only_project:
        dash = vault / dashboard_name
        if dash.exists():
            try:
                dash_text = vaultlib.read_note(dash)
                dash_new = vaultlib.replace_marker_block(
                    dash_text, "sync:last-run", report.summary(now)
                )
                if dash_new != dash_text:
                    vaultlib.write_note_atomic(dash, dash_new)
            except KeyError:
                pass  # dashboard has no markers yet — not an error
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="sync-computed-fields",
        description="Rebuild every note's computed: block (the vault's single automated writer).",
    )
    ap.add_argument("--vault", required=True, type=Path)
    ap.add_argument("--source", default="github", help="github | fixture:PATH")
    ap.add_argument("--note", metavar="PROJECT", help="sync a single project (throwaway testing)")
    ap.add_argument("--dashboard", default="dashboard.md", help="dashboard note name in the vault")
    ap.add_argument("--dry-run", action="store_true", help="print diffs, write nothing")
    ap.add_argument("--today", help="override today's date YYYY-MM-DD (testing hook)")
    args = ap.parse_args(argv)

    try:
        source = parse_source_arg(args.source, token=os.environ.get("GITHUB_TOKEN"))
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    today = dt.date.fromisoformat(args.today) if args.today else None

    report = run(
        args.vault, source, only_project=args.note, dry_run=args.dry_run,
        dashboard_name=args.dashboard, today=today,
    )
    print(
        f"checked={report.checked} updated={report.updated} "
        f"unchanged={report.unchanged} no-repo={report.skipped_no_repo} "
        f"errors={len(report.errors)}"
    )
    for project, err in report.errors:
        print(f"  ⚠ {project}: {err}", file=sys.stderr)
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
