"""portfolio-updater — the ONLY way agents modify a project note.

    update.py --vault PATH --project NAME [--stage STAGE]
              [--changelog-note "TEXT"] [--dry-run]

- `stage` must be one of: research | design | development | testing |
  deployment | support. No free text.
- `changelog_note` (≤140 chars) is APPENDED to the `changelog` array with
  today's date — it never rewrites existing entries.
- `summary`, `status`, and every other judgment field are not accepted as
  inputs and are never touched: edits are byte-preserving splices via
  common.frontmatter (plan F6), and a post-edit `verify_untouched()` guard
  aborts the write if anything outside `stage`/`changelog` would change.
- Draft notes (`_draft: true`) are refused — they belong to the bootstrap/
  review flow until a human removes the marker (hard rule #5).

Working subagents (research/design/dev/test/deploy/support) call this at
end of session instead of editing notes. Free-form note edits by agents are
a hard-rule violation (CLAUDE.md #1 and #7). Stage transitions are made by
the Project Lead role or a human (plan F4); changelog appends are open to
any role.

Contract: HANDOFF.md §5, Task 7; proposal §5.1.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import frontmatter as fmt  # noqa: E402
from common import vault as vaultlib  # noqa: E402
from common.confidence import STAGES  # noqa: E402

OWNED_KEYS = {"stage", "changelog"}
MAX_NOTE_LEN = 140


class UpdateError(ValueError):
    pass


def _changelog_entry(note: str, today: dt.date, nl: str) -> str:
    escaped = json.dumps(note, ensure_ascii=False)
    return f"  - {{ date: {today.isoformat()}, note: {escaped} }}{nl}"


def apply_update(
    text: str,
    *,
    stage: str | None = None,
    changelog_note: str | None = None,
    today: dt.date | None = None,
) -> str:
    """Pure function: note text in, updated note text out (validates first)."""
    if stage is None and changelog_note is None:
        raise UpdateError("nothing to do: pass stage and/or changelog_note")
    if stage is not None and stage not in STAGES:
        raise UpdateError(f"invalid stage {stage!r}; must be one of: {', '.join(STAGES)}")
    if changelog_note is not None:
        changelog_note = changelog_note.strip()
        if not changelog_note:
            raise UpdateError("changelog note is empty")
        if len(changelog_note) > MAX_NOTE_LEN:
            raise UpdateError(
                f"changelog note is {len(changelog_note)} chars; cap is {MAX_NOTE_LEN} (D8)"
            )
    today = today or dt.date.today()

    head, fm, tail = fmt.split_note(text)
    parsed = fmt.parse(fm)
    if parsed.get("_draft") is True:
        raise UpdateError(
            "note is a draft (_draft: true) — drafts are owned by the bootstrap/"
            "review flow; remove the marker in the human review pass first"
        )
    nl = fmt.newline_of(fm or text)
    new_fm = fm

    if stage is not None:
        if fmt.key_span(new_fm, "stage") is None:
            raise UpdateError("note has no top-level `stage:` line (schema drift — fix the note first)")
        new_fm = fmt.set_scalar(new_fm, "stage", stage)

    if changelog_note is not None:
        entry = _changelog_entry(changelog_note, today, nl)
        span = fmt.key_span(new_fm, "changelog")
        if span is None:
            block = f"changelog:{nl}{entry}"
            new_fm = fmt.insert_block_after(new_fm, "stage", block)
        else:
            existing = fmt.get_block(new_fm, "changelog") or ""
            first_line = existing.splitlines()[0]
            value_part = first_line.split(":", 1)[1].split("#", 1)[0].strip()
            if value_part == "[]" or value_part == "":
                if value_part == "[]":
                    # flow-empty -> block list with the new entry
                    block = f"changelog:{nl}{entry}"
                else:
                    block = existing + entry
                new_fm = fmt.replace_key_block(new_fm, "changelog", block)
            elif value_part.startswith("["):
                # Flow-style non-empty list: convert to block style (changelog
                # is agent-owned territory, so re-emitting it is allowed).
                items = fmt.parse(existing).get("changelog") or []
                lines = [f"changelog:{nl}"]
                for item in items:
                    if isinstance(item, dict):
                        inner = ", ".join(
                            f"{k}: {fmt.emit_scalar(v)}" for k, v in item.items()
                        )
                        lines.append(f"  - {{ {inner} }}{nl}")
                    else:
                        lines.append(f"  - {fmt.emit_scalar(item)}{nl}")
                lines.append(entry)
                new_fm = fmt.replace_key_block(new_fm, "changelog", "".join(lines))
            else:
                # block list already: append after its last line
                block = existing + entry
                new_fm = fmt.replace_key_block(new_fm, "changelog", block)

    fmt.verify_untouched(fm, new_fm, OWNED_KEYS)
    return fmt.join_note(head, new_fm, tail)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="portfolio-updater",
        description="Narrow agent write-path: enum stage + capped changelog append.",
    )
    ap.add_argument("--vault", required=True, type=Path, help="vault directory")
    ap.add_argument("--project", required=True, help="project name (frontmatter `project:`)")
    ap.add_argument("--stage", choices=STAGES, help="set the stage (Project Lead / human only — plan F4)")
    ap.add_argument("--changelog-note", metavar="TEXT", help=f"append a ≤{MAX_NOTE_LEN}-char changelog entry")
    ap.add_argument("--dry-run", action="store_true", help="print the diff, write nothing")
    args = ap.parse_args(argv)

    try:
        path = vaultlib.find_note_by_project(args.vault, args.project)
        if path is None:
            known = ", ".join(sorted(vaultlib.list_projects(args.vault))) or "(none)"
            raise UpdateError(f"no note with project: {args.project!r}. Known projects: {known}")
        before = vaultlib.read_note(path)
        after = apply_update(before, stage=args.stage, changelog_note=args.changelog_note)
    except (UpdateError, fmt.FrontmatterError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if before == after:
        print(f"{path}: no change")
        return 0
    if args.dry_run:
        sys.stdout.writelines(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=str(path),
                tofile=f"{path} (dry-run)",
            )
        )
        return 0
    vaultlib.write_note_atomic(path, after)
    did = []
    if args.stage:
        did.append(f"stage -> {args.stage}")
    if args.changelog_note:
        did.append("changelog +1")
    print(f"{path}: {', '.join(did)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
