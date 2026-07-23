"""Bootstrap step 3 — signal checks, confidence scoring, draft notes.

For each selected repo: run the confidence-signal checks from HANDOFF.md §2
(README present/fresh, CONTRIBUTING.md, ARCHITECTURE.md, commits in last 90
days, tests directory, CI config, releases/tags), compute
`summary_confidence` (0–1 missing → high, 2–3 → medium, 4+ → low) and
`missing_signals`, and draft a project note from
`templates/project-note.md` with a best-effort `summary` paragraph and an
inferred `stage`.

Every draft is flagged `_draft: true` — judgment fields (`status`,
`priority`, `target_quarter`) stay unset until the human review pass
(Task 4) confirms the note and removes the marker. Never auto-finalize
them here (CLAUDE.md hard rules 1 and 5).

Contract: HANDOFF.md §5, Task 3.
"""

if __name__ == "__main__":
    raise SystemExit("Not implemented yet — scaffold stub. See portfolio/HANDOFF.md §5, Task 3.")
