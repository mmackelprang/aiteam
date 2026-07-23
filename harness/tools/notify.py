"""notify — render the one review_item schema per channel, then send.

Renders a review_item (§2.1) into Slack Block Kit and/or Google Chat
Cards v2 and sends via the channels configured in
config/notification_routing/<project>.yaml (§2.2 shape).

HARD RULES (CLAUDE.md #4, #5):
- One schema, rendered per channel. Never hand-build a channel-specific
  payload outside this module — add a renderer here, don't fork the shape.
- Google Chat is one-way webhook only in Phase 0/1. No Google Cloud
  project, no interaction endpoint, unless the user explicitly asks.

Every rendering must include a clickable link for each entry in
`documents`, plus the primary "open in Paperclip" link (which is also the
answer path while notifications are one-way).

Secrets (SLACK_BOT_TOKEN, webhook URLs) come from the gitignored .env /
secret store — committed routing configs reference env vars, never embed
URLs (webhook URLs carry key+token query params).

Contract: HANDOFF-agentic-harness.md §6, Task 4 (Task 5 adds SLA
escalation + the daily digest on top).
"""

if __name__ == "__main__":
    raise SystemExit("Not implemented yet — scaffold stub. See harness/HANDOFF-agentic-harness.md §6, Task 4.")
