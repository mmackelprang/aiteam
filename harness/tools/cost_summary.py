"""cost-summary — READ-interface for per-project cost data.

Returns cost rollups (total MTD, by agent-role, by stage) for a project.
Cost events are tagged from the very first event with project id,
agent-role, and task id (OpenTelemetry GenAI semantic conventions as the
shape) — CLAUDE.md hard rule #6 — so graduating to a real chargeback tool
later needs no re-instrumenting.

HARD RULE (CLAUDE.md #3): this repo exposes read-interfaces only. The
write into the portfolio vault's `computed:` block (cost_by_stage,
cost_total_mtd) happens in ../../portfolio/sync/sync_computed_fields.py,
per that system's single-writer rule. Never build a vault write path here.

Contract: HANDOFF-agentic-harness.md §5 + §6, Task 6.
"""

if __name__ == "__main__":
    raise SystemExit("Not implemented yet — scaffold stub. See harness/HANDOFF-agentic-harness.md §6, Task 6.")
