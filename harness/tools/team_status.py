"""team-status — READ-interface for agent/company status, plus the pause.

Queries the Paperclip API for a project's team state (per-agent state,
paused/running, open review items) in a small, stable shape the portfolio
sync job can consume as `computed.team_status`.

Also home of the one-command pause (handoff §1, constraint 3): before
driving a project manually, pause that project's Paperclip agents first —
a single action, and the pause must be visible wherever the portfolio
sync job next reads it.

HARD RULE (CLAUDE.md #3): read-interface only — the vault write happens in
../../portfolio/sync/sync_computed_fields.py.

Contract: HANDOFF-agentic-harness.md §5 + §6, Task 7.
"""

if __name__ == "__main__":
    raise SystemExit("Not implemented yet — scaffold stub. See harness/HANDOFF-agentic-harness.md §6, Task 7.")
