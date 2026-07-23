"""Bootstrap step 2 — apply default excludes, produce the checklist.

Drops archived repos, forks, and repos with no push in 2+ years, then
rewrites ``bootstrap/select.md`` as an include/exclude checklist. Checkbox
state a human already set in select.md survives a re-run. The pilot set is
resolved (D1: RTest, homelab, FamilyWorkspace) — pass them via ``--check``
to pre-tick, e.g.::

    python3 bootstrap/filter_defaults.py --check RTest --check homelab \
        --check FamilyWorkspace

The pilot set of 3–5 is confirmed with the user before ingest (Task 3)
runs against it.

Contract: HANDOFF.md §5, Task 2.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.confidence import RepoFacts  # noqa: E402
from common.github_api import facts_from_dict  # noqa: E402

_CHECKED = re.compile(r"^- \[(?P<state>[ xX])\] `(?P<repo>[^`]+)`")


def load_cache(path: Path) -> list[RepoFacts]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [facts_from_dict(name, d) for name, d in data["repos"].items()]


def existing_checks(select_md: Path) -> dict[str, bool]:
    if not select_md.exists():
        return {}
    states: dict[str, bool] = {}
    for line in select_md.read_text(encoding="utf-8").splitlines():
        m = _CHECKED.match(line)
        if m:
            states[m.group("repo")] = m.group("state").lower() == "x"
    return states


def split_included(records: list[RepoFacts], today: dt.date, years_stale: int) -> tuple[list, list]:
    included, excluded = [], []
    cutoff_days = 365 * years_stale
    for r in records:
        reasons = []
        if r.archived:
            reasons.append("archived")
        if r.fork:
            reasons.append("fork")
        if r.pushed_at is None or (today - r.pushed_at).days > cutoff_days:
            reasons.append(f"no push in {years_stale}+ years")
        (excluded if reasons else included).append((r, reasons))
    key = lambda pair: (pair[0].pushed_at or dt.date.min)  # noqa: E731
    return (
        sorted(included, key=key, reverse=True),
        sorted(excluded, key=key, reverse=True),
    )


def render_checklist(included, excluded, checks: dict[str, bool], today: dt.date) -> str:
    lines = [
        "# Repo selection — bootstrap worksheet",
        "",
        f"Default excludes applied (Task 2) on {today.isoformat()}. Tick the repos to",
        "track, then run `bootstrap/ingest.py --from-select bootstrap/select.md`.",
        "Checkbox state here survives re-runs. **Pilot set (decision D1):**",
        "RTest, homelab, FamilyWorkspace — confirm before ingest runs (Task 2 gate).",
        "",
        "## Include in the portfolio?",
        "",
    ]
    for r, _ in included:
        mark = "x" if checks.get(r.repo, False) else " "
        desc = f" — {r.description}" if r.description else ""
        push = f" (last push {r.pushed_at.isoformat()})" if r.pushed_at else ""
        roadmap = "; ROADMAP.md" if r.roadmap_present else ""
        lines.append(f"- [{mark}] `{r.repo}`{desc}{push}{roadmap}")
    lines += ["", "## Excluded by default", ""]
    if not excluded:
        lines.append("_None._")
    for r, reasons in excluded:
        lines.append(f"- `{r.repo}` — {', '.join(reasons)}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bootstrap-filter", description=__doc__.splitlines()[0])
    here = Path(__file__).resolve().parent
    ap.add_argument("--cache", type=Path, default=here / "enumerated.json")
    ap.add_argument("--out", type=Path, default=here / "select.md")
    ap.add_argument("--years-stale", type=int, default=2)
    ap.add_argument("--check", action="append", default=[], metavar="NAME",
                    help="pre-tick a repo (short or full name; repeatable)")
    ap.add_argument("--today", help="override today's date YYYY-MM-DD (testing hook)")
    args = ap.parse_args(argv)

    if not args.cache.exists():
        print(f"error: cache not found: {args.cache} — run enumerate.py first (Task 1)",
              file=sys.stderr)
        return 1
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    records = load_cache(args.cache)
    checks = existing_checks(args.out)
    for name in args.check:
        for r in records:
            if r.repo == name or r.repo.split("/")[-1] == name:
                checks[r.repo] = True

    included, excluded = split_included(records, today, args.years_stale)
    args.out.write_text(render_checklist(included, excluded, checks, today), encoding="utf-8")
    ticked = sum(1 for r, _ in included if checks.get(r.repo))
    print(
        f"{len(included)} candidates ({ticked} ticked), {len(excluded)} excluded -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
