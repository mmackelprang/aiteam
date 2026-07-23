"""Nightly diff — surface repos not yet tracked in the vault.

Diff the GitHub account's repo list against the vault's project notes and
rewrite the "Unclaimed repos" queue on the dashboard note (only the content
between the `<!-- sync:unclaimed -->` markers — the rest of the dashboard
is human territory), so new work never sits silently outside the system.

Archived repos and forks are excluded by default, matching bootstrap's
default excludes; flags re-include them.

Contract: HANDOFF.md §5, Task 8; proposal §5.4.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import frontmatter as fmt  # noqa: E402
from common import vault as vaultlib  # noqa: E402
from common.confidence import RepoFacts  # noqa: E402
from common.github_api import SourceError, parse_source_arg  # noqa: E402


def tracked_repos(vault: Path) -> set[str]:
    tracked: set[str] = set()
    for path in vaultlib.iter_notes(vault):
        try:
            _, fm, _ = fmt.split_note(vaultlib.read_note(path))
            repo = fmt.parse(fm).get("repo")
        except fmt.FrontmatterError:
            continue
        if repo:
            tracked.add(str(repo))
    return tracked


def compute_unclaimed(records: list[RepoFacts], tracked: set[str], *,
                      include_archived: bool = False, include_forks: bool = False) -> list[RepoFacts]:
    out = []
    for r in records:
        if r.repo in tracked:
            continue
        if r.archived and not include_archived:
            continue
        if r.fork and not include_forks:
            continue
        out.append(r)
    out.sort(key=lambda r: (r.pushed_at or dt.date.min), reverse=True)
    return out


def render(unclaimed: list[RepoFacts]) -> str:
    if not unclaimed:
        return "_None — every repo is tracked._"
    lines = []
    for r in unclaimed:
        pushed = f" (last push {r.pushed_at.isoformat()})" if r.pushed_at else ""
        desc = f" — {r.description}" if r.description else ""
        lines.append(f"- `{r.repo}`{desc}{pushed}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="unclaimed-repos",
        description="Write the unclaimed-repos queue into the dashboard's marker block.",
    )
    ap.add_argument("--vault", required=True, type=Path)
    ap.add_argument("--source", default="github", help="github | fixture:PATH")
    ap.add_argument("--user", help="GitHub username to enumerate")
    ap.add_argument("--org", action="append", default=[], help="GitHub org (repeatable)")
    ap.add_argument("--dashboard", default="dashboard.md")
    ap.add_argument("--include-archived", action="store_true")
    ap.add_argument("--include-forks", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print the list, write nothing")
    args = ap.parse_args(argv)

    try:
        source = parse_source_arg(args.source, token=os.environ.get("GITHUB_TOKEN"))
        records = source.list_repos(user=args.user, orgs=tuple(args.org))
    except (ValueError, OSError, SourceError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    unclaimed = compute_unclaimed(
        records, tracked_repos(args.vault),
        include_archived=args.include_archived, include_forks=args.include_forks,
    )
    content = render(unclaimed)
    if args.dry_run:
        print(content)
        return 0

    dash = args.vault / args.dashboard
    if not dash.exists():
        print(f"error: dashboard note not found: {dash}", file=sys.stderr)
        return 1
    text = vaultlib.read_note(dash)
    try:
        new_text = vaultlib.replace_marker_block(text, "sync:unclaimed", content)
    except KeyError:
        print("error: dashboard has no <!-- sync:unclaimed --> markers", file=sys.stderr)
        return 1
    if new_text != text:
        vaultlib.write_note_atomic(dash, new_text)
    print(f"unclaimed repos: {len(unclaimed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
