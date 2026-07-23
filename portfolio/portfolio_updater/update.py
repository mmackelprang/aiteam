"""portfolio-updater — the ONLY way agents modify a project note.

    update(project, stage?: enum, changelog_note?: str <=140 chars)

- `stage` must be one of: research | design | development | testing |
  deployment | support. No free text.
- `changelog_note`, if given, is APPENDED to the `changelog` array with a
  timestamp — it never rewrites anything.
- `summary` and `status` (and every other judgment field) are not accepted
  as inputs and are never touched — they stay human-only, edited directly
  in Obsidian.

Working subagents (research/design/dev/test/deploy/support) call this at
end of session instead of editing notes. Free-form note edits by agents are
a hard-rule violation (CLAUDE.md #1 and #7).

Contract: HANDOFF.md §5, Task 7; proposal §5.1.
"""

if __name__ == "__main__":
    raise SystemExit("Not implemented yet — scaffold stub. See portfolio/HANDOFF.md §5, Task 7.")
