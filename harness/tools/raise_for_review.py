"""raise-for-review — the ONLY path that creates a review item.

Wraps Paperclip's Issues API and enforces the review_item schema
(HANDOFF-agentic-harness.md §2.1):

    id, project, type (question | design-decision | roadmap-direction |
    doc-review), priority (critical | high | medium | low), summary (1-2
    sentences), reasoning, confidence_score (0.0-1.0), documents
    ([{label, url}]), status (pending | answered | expired),
    raised_at / sla_due_at / answered_at

SLA by priority: critical 4h, high 1d, medium 3d, low 1w. Past-due and
still pending -> escalation (re-notify + daily digest), never silent.

HARD RULE (CLAUDE.md #1): no agent, script, or session writes directly to a
Paperclip issue for review purposes outside this tool. If something needs
to be "flagged for review", the answer is: call this tool.

On create, hands the item to tools/notify.py for channel rendering.

Contract: HANDOFF-agentic-harness.md §6, Task 3.
"""

if __name__ == "__main__":
    raise SystemExit("Not implemented yet — scaffold stub. See harness/HANDOFF-agentic-harness.md §6, Task 3.")
