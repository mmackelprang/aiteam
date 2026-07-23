"""Bootstrap step 1 — enumerate repos.

Pull the repo list for the account(s): name, description, visibility,
language, last push date, archived flag, fork flag, and whether ROADMAP.md
exists. Two outputs:

- ``bootstrap/enumerated.json`` — machine cache, deliberately in the same
  ``{"repos": {...}}`` shape FixtureSource reads, so later steps (filter,
  ingest, unclaimed) can run offline from it.
- ``bootstrap/select.md`` — the raw, human-readable list (no filtering yet;
  that's filter_defaults.py, which rewrites select.md as a checklist).

Runs on the dev machine where the PAT can see the whole account (plan F5) —
this cloud session can't. ``--source fixture:PATH`` exists for tests.

Contract: HANDOFF.md §5, Task 1.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.confidence import RepoFacts  # noqa: E402
from common.github_api import SourceError, facts_to_dict, parse_source_arg  # noqa: E402


def render_raw_list(records: list[RepoFacts], generated: dt.datetime) -> str:
    lines = [
        "# Repo selection — bootstrap worksheet",
        "",
        f"Raw enumeration (Task 1), generated {generated.replace(microsecond=0).isoformat(sep=' ')}.",
        "Next: run `bootstrap/filter_defaults.py` to apply the default excludes and",
        "turn this into an include/exclude checklist (Task 2).",
        "",
        "| Repo | Description | Lang | Last push | Flags | ROADMAP.md |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(records, key=lambda x: (x.pushed_at or dt.date.min), reverse=True):
        flags = ", ".join(
            f for f, on in (("archived", r.archived), ("fork", r.fork)) if on
        ) or "—"
        lines.append(
            f"| `{r.repo}` | {r.description or '—'} | {r.language or '—'} | "
            f"{r.pushed_at.isoformat() if r.pushed_at else '—'} | {flags} | "
            f"{'yes' if r.roadmap_present else 'no'} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bootstrap-enumerate", description=__doc__.splitlines()[0])
    ap.add_argument("--user", help="GitHub username (personal repos)")
    ap.add_argument("--org", action="append", default=[], help="GitHub org (repeatable)")
    ap.add_argument("--source", default="github", help="github | fixture:PATH")
    here = Path(__file__).resolve().parent
    ap.add_argument("--out", type=Path, default=here / "select.md")
    ap.add_argument("--cache", type=Path, default=here / "enumerated.json")
    ap.add_argument("--no-check-roadmap", action="store_true",
                    help="skip the per-repo ROADMAP.md existence check (1 API call/repo)")
    args = ap.parse_args(argv)

    try:
        source = parse_source_arg(args.source, token=os.environ.get("GITHUB_TOKEN"))
        records = source.list_repos(
            user=args.user, orgs=tuple(args.org), check_roadmap=not args.no_check_roadmap
        )
    except (ValueError, OSError, SourceError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not records:
        print("error: enumeration returned no repos (check --user/--org and token scope)",
              file=sys.stderr)
        return 1

    now = dt.datetime.now()
    cache = {
        "generated": now.replace(microsecond=0).isoformat(sep=" "),
        "repos": {r.repo: facts_to_dict(r) for r in records},
    }
    args.cache.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")
    args.out.write_text(render_raw_list(records, now), encoding="utf-8")
    print(f"{len(records)} repos -> {args.out} (cache: {args.cache})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
