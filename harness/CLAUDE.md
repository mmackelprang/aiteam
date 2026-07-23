# CLAUDE.md — Agentic Team Harness

Project-level memory. Loaded automatically at the start of every Claude Code session in this repo. Keep this to durable facts and hard rules — implementation detail and task sequencing live in `HANDOFF-agentic-harness.md` and `docs/proposal.md`.

## What this repo is

Tooling for a per-project AI team (research/design/dev/test/deploy/support) running under Paperclip, reporting up into a companion portfolio-tracking system (`../portfolio/` in this repo — originally designed as a separate repo). Full design rationale: `docs/proposal.md`. Full task sequencing: `HANDOFF-agentic-harness.md`.

## Hard rules — do not violate these without explicit user sign-off

1. **`raise_for_review.py` is the only path that creates a review item.** No agent, script, or session should write directly to a Paperclip issue for review purposes outside this tool. If a task seems to need an agent to "flag something for review," the answer is: call this tool.
2. **Trust tiers are Board-granted only.** Every new project/agent starts at Tier 0 (no `dangerouslySkipPermissions`, all actions gated, everything routed to review). Raising a tier is a manual, versioned edit the user makes — never something this codebase does automatically, and never something a session should do "to unblock" a stuck agent.
3. **Cost and team-status data are consumed by the portfolio repo, not written by this one.** This repo builds read-interfaces (cost summaries, agent/company status). The actual write into that repo's Obsidian `computed:` block happens in *its* sync job, per that repo's own single-writer rule. Do not build a write path into the portfolio vault from this repo.
4. **One notification schema (`review_item`), rendered per channel.** Never hand-build a Slack-specific or Google-Chat-specific payload outside `notify.py` — add a renderer for a new channel, don't fork the shape.
5. **Google Chat ships one-way (webhook) first.** Do not build the full two-way Chat app (Google Cloud project, interaction endpoint) unless the user explicitly asks for that phase.
6. **Cost data is tagged by project id, agent-role, and task id from the first event onward** — even though today's only consumer is a simple rollup. This is what avoids re-instrumenting if cost tracking graduates to a dedicated tool later.
7. **The default team template lives in this repo** (`templates/default-team.json`), not only inside Paperclip's own database — changes to the default org chart should be diffable, reviewable git commits.

## Schema quick reference

```yaml
review_item.priority:        critical | high | medium | low
review_item.status:          pending | answered | expired
review_item.sla:             critical=4h, high=1d, medium=3d, low=1w
trust_tier.tier:              0 (default) | 1 | 2
```

Full schemas (review item, notification routing, trust tier, team template): `HANDOFF-agentic-harness.md` §2.

## Conventions

- `raise_for_review.py`, `notify.py`, cost/team-status read-interfaces each live in their own module under `tools/` — one concern per file, matching the narrow-write-surface philosophy throughout this whole system (portfolio and harness both).
- Secrets (`ANTHROPIC_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `GOOGLE_CHAT_WEBHOOK_URL`) come from a gitignored secrets file — never hardcoded, never committed.
- Per-project config (`notification_routing/`, `trust_tiers/`) is one file per project — don't collapse into a single global config; that's what makes per-team routing (some teams Slack, some Google Chat, some both) and per-project tier history tractable.

## Current phase

Phase 0 (pilot, one project). See `HANDOFF-agentic-harness.md` §6 for the task list, §7 for what's explicitly out of scope, §8 for acceptance criteria before proposing rollout beyond the pilot.
