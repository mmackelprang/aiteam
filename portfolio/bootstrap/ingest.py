"""Bootstrap step 3 — signal checks, confidence scoring, draft notes.

For each selected repo: fetch facts, run the §2 confidence-signal checks,
and render ``templates/project-note.md`` into a draft note with a
best-effort summary (the repo description) and an inferred stage.

Every draft is flagged ``_draft: true`` and its judgment fields are left
blank — the Task 4 human review pass sets status/priority/target_quarter
and removes the marker. Never auto-finalize them here (hard rules 1 & 5).

Overwrite policy: an existing **confirmed** note (no ``_draft``) is never
touched, with or without ``--force``. An existing draft is skipped unless
``--force``.

Contract: HANDOFF.md §5, Task 3.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import frontmatter as fmt  # noqa: E402
from common import vault as vaultlib  # noqa: E402
from common.confidence import RepoFacts, infer_stage  # noqa: E402
from common.github_api import SourceError, parse_source_arg  # noqa: E402
from sync.sync_computed_fields import build_computed  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "project-note.md"
_LEADING_COMMENT = re.compile(r"\A<!--.*?-->\s*\n", re.DOTALL)
_CHECKED = re.compile(r"^- \[[xX]\] `(?P<repo>[^`]+)`")


class IngestError(RuntimeError):
    pass


def parse_selected(select_md: Path) -> list[str]:
    repos = []
    for line in select_md.read_text(encoding="utf-8").splitlines():
        m = _CHECKED.match(line)
        if m:
            repos.append(m.group("repo"))
    return repos


def _iso_or_empty(v) -> str:
    return v.isoformat() if v else ""


def render_note(facts: RepoFacts, *, personal_owner: str | None, today: dt.date,
                now: dt.datetime, template_text: str | None = None) -> str:
    template = template_text if template_text is not None else TEMPLATE.read_text(encoding="utf-8")
    template = _LEADING_COMMENT.sub("", template)

    owner, short = facts.repo.split("/", 1)
    computed = build_computed(facts, today, now)
    summary = (facts.description or "").strip() or (
        "TODO: summarize this repo (no GitHub description) — written during the "
        "Task 4 review pass."
    )
    values = {
        "project": short,
        "source": "personal" if (personal_owner is None or owner == personal_owner) else "org",
        "repo": facts.repo,
        "visibility": facts.visibility,
        "draft_summary": summary,
        "roadmap_source": "repo" if facts.roadmap_present else "none",
        "roadmap_link": f"{facts.repo}/ROADMAP.md" if facts.roadmap_present else "",
        "roadmap_url": (
            f"https://github.com/{facts.repo}/blob/{facts.default_branch}/ROADMAP.md"
            if facts.roadmap_present else "—"
        ),
        "stage": infer_stage(facts, today),
        "last_commit": _iso_or_empty(computed["last_commit"]),
        "open_issues": str(computed["open_issues"]),
        "latest_release": computed["latest_release"] or "",
        "language": computed["language"] or "",
        "archived_on_github": "true" if computed["archived_on_github"] else "false",
        "activity_state": computed["activity_state"],
        "summary_confidence": computed["summary_confidence"],
        "missing_signals": "[" + ", ".join(fmt.emit_scalar(s) for s in computed["missing_signals"]) + "]",
        "roadmap_last_updated": _iso_or_empty(computed["roadmap_last_updated"]),
        "last_synced": fmt.emit_scalar(computed["last_synced"]),
    }
    out = template
    for key, val in values.items():
        out = out.replace("{{" + key + "}}", val)
    leftover = re.findall(r"\{\{(\w+)\}\}", out)
    if leftover:
        raise IngestError(f"template tokens not filled: {leftover}")
    out = re.sub(r"[ \t]+$", "", out, flags=re.MULTILINE)

    # The rendered draft must be a valid note the rest of the pipeline accepts:
    head, fm, tail = fmt.split_note(out)
    parsed = fmt.parse(fm)
    if parsed.get("_draft") is not True or parsed.get("project") != short:
        raise IngestError("rendered draft failed self-check (_draft/project)")
    return out


def ingest_one(facts: RepoFacts, dest_dir: Path, *, personal_owner: str | None,
               today: dt.date, now: dt.datetime, force: bool = False) -> tuple[Path, str]:
    """Returns (path, action) where action ∈ written | skipped-draft | refused-confirmed."""
    short = facts.repo.split("/", 1)[1]
    path = dest_dir / f"{short}.md"
    if path.exists():
        existing = fmt.parse(fmt.split_note(vaultlib.read_note(path))[1])
        if existing.get("_draft") is not True:
            return path, "refused-confirmed"  # human-reviewed note: bootstrap never touches it
        if not force:
            return path, "skipped-draft"
    text = render_note(facts, personal_owner=personal_owner, today=today, now=now)
    vaultlib.write_note_atomic(path, text)
    return path, "written"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bootstrap-ingest", description=__doc__.splitlines()[0])
    here = Path(__file__).resolve().parent
    ap.add_argument("--vault", type=Path, help="write drafts into this vault directory")
    ap.add_argument("--out-dir", type=Path, default=here / "out",
                    help="fallback output dir when --vault is not given")
    ap.add_argument("--source", default="github", help="github | fixture:PATH")
    ap.add_argument("--repos", nargs="*", default=[], metavar="OWNER/NAME")
    ap.add_argument("--from-select", type=Path, help="ingest the ticked repos in select.md")
    ap.add_argument("--personal-owner", help="owner name that counts as source: personal")
    ap.add_argument("--force", action="store_true", help="overwrite existing DRAFTS (never confirmed notes)")
    ap.add_argument("--today", help="override today's date YYYY-MM-DD (testing hook)")
    args = ap.parse_args(argv)

    repos = list(args.repos)
    if args.from_select:
        repos += [r for r in parse_selected(args.from_select) if r not in repos]
    if not repos:
        print("error: nothing to ingest (pass --repos or --from-select)", file=sys.stderr)
        return 2

    dest = args.vault or args.out_dir
    dest.mkdir(parents=True, exist_ok=True)
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    now = dt.datetime.now()
    try:
        source = parse_source_arg(args.source, token=os.environ.get("GITHUB_TOKEN"))
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    failures = 0
    for repo in repos:
        try:
            facts = source.fetch(repo)
            path, action = ingest_one(
                facts, dest, personal_owner=args.personal_owner,
                today=today, now=now, force=args.force,
            )
        except (SourceError, IngestError, fmt.FrontmatterError) as exc:
            print(f"  ⚠ {repo}: {exc}", file=sys.stderr)
            failures += 1
            continue
        marker = {"written": "drafted", "skipped-draft": "skipped (draft exists; use --force)",
                  "refused-confirmed": "REFUSED (confirmed note — bootstrap never overwrites)"}[action]
        print(f"  {repo} -> {path.name}: {marker}")
    print(
        f"done: {len(repos) - failures}/{len(repos)} processed into {dest} — drafts await "
        "the Task 4 human review pass (sorted low-confidence first)."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
