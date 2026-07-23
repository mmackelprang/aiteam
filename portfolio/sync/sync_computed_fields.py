"""Nightly sync — rebuild each note's `computed:` block. THE single writer.

For every project note with a `repo` set: hit the GitHub API and rebuild the
nested `computed:` frontmatter key wholesale — last_commit, open_issues,
latest_release, language, archived_on_github, activity_state (active <60d /
idle 60–180d / stale >180d, derived from last_commit), summary_confidence,
missing_signals, roadmap_last_updated, last_synced.

HARD RULE (CLAUDE.md #2): parse → replace ONLY the `computed:` key →
serialize. `status`, `summary`, `priority`, `depends_on`, `changelog`, and
every other key pass through untouched. Test against a throwaway note and
prove a hand-edited `status` survives a run before pointing this at real
notes.

Phase 1+: extend with Paperclip as a second data source
(computed.cost_by_stage, computed.cost_total_mtd, computed.team_status) via
the harness read-interfaces — see ../harness/HANDOFF-agentic-harness.md §5.
This job stays the only writer either way.

Contract: HANDOFF.md §5, Task 6.
"""

if __name__ == "__main__":
    raise SystemExit("Not implemented yet — scaffold stub. See portfolio/HANDOFF.md §5, Task 6.")
