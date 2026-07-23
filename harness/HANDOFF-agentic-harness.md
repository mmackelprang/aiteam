# Handoff: Agentic Team Harness — Kickoff Brief for Claude Code

> **Repo note (2026-07-23):** this system lives in the `harness/` subtree of the `aiteam` repo, alongside its companion system in `../portfolio/`. Both systems were originally designed as two separate repos; they share this one starting repo, one self-contained subtree each, so a later split stays trivial. All paths in this doc are relative to `harness/`, and the project-memory file `CLAUDE-agentic-harness.md` is checked in here as `CLAUDE.md`.

**How to use this doc:** paste/drop this file into a new, blank repo (separate from the portfolio-tracking repo) and open Claude Code in that directory. Self-contained — no other context from prior conversations assumed. Start with: *"Read HANDOFF-agentic-harness.md and start on Phase 0, Task 1."*

**Companion system:** this harness reports up into the [Project Portfolio System](../portfolio/HANDOFF.md) — a separate subtree (originally a separate repo). Two of this harness's outputs (cost rollup, team-status) are written **by the portfolio repo's existing sync job, not by this repo** — see §5's cross-repo note before building those two pieces.

---

## 0. What this is

A per-project team of AI agents — research, design, dev, test, deploy, support — running under [Paperclip](https://github.com/paperclipai/paperclip) (self-hosted org-chart/budget/approval/audit runtime), with Claude Code sessions as the actual workers. Full design rationale and the adversarial-review process behind every decision below: `docs/proposal.md` (copy the full proposal into this repo — see Task 0).

---

## 1. Non-negotiable design constraints

1. **Reviews are raised only through the `raise-for-review` tool.** No agent free-writes into Paperclip Issues for review purposes — this tool is the single write path, matching the schema in §2.
2. **Trust/autonomy is Board-granted only, never self-escalated.** Every new project/agent starts at Tier 0 (no `dangerouslySkipPermissions`, everything gated, everything routes to review). Raising to Tier 1/2 is an explicit, versioned action taken by the user — never something an agent or script does on its own.
3. **Team-status visibility requires an explicit pause action.** Before driving a project manually, pause that project's Paperclip agents first. This is a habit/workflow rule as much as a technical one — build the pause into a one-command action, don't rely on remembering.
4. **Cost data is tagged from day one** using project id, agent-role, and task id (OpenTelemetry GenAI semantic conventions as the shape) — even though the only consumer today is a simple rollup script. This is what avoids re-instrumenting later if cost tracking graduates to a real chargeback tool (e.g., Langfuse).
5. **Notification alerts share one internal schema, rendered per channel** (§2's `review_item` shape) — never hand-craft a Slack-specific or Google-Chat-specific payload from scratch; add a renderer, not a new shape.
6. **Google Chat ships as a one-way webhook first.** Do not build the full two-way Chat app (Google Cloud project, interaction-event endpoint) in Phase 0 — see §7's explicitly-out-of-scope list.

---

## 2. Schema — full spec

### 2.1 Review item (the review-queue's core object)

```yaml
review_item:
  id: <Paperclip issue id>
  project: acme-billing-service
  type: question | design-decision | roadmap-direction | doc-review
  priority: critical | high | medium | low
  summary: "agent-authored, 1-2 sentences"
  reasoning: "why the agent is asking, what it already tried"
  confidence_score: 0.0-1.0
  documents: [{ label, url }, ...]     # zero or more, always rendered as clickable links
  status: pending | answered | expired
  raised_at / sla_due_at / answered_at
```

SLA thresholds by priority: critical 4h, high 1 day, medium 3 days, low 1 week. Past due and still `pending` → auto-escalate (re-notify, surface in the daily digest) rather than sitting silently.

### 2.2 Notification routing (per project)

```yaml
notification_routing:
  project: acme-billing-service
  channels: [slack, google_chat]    # one or both
  slack:
    target: "#acme-billing-reviews"  # channel or user DM
  google_chat:
    webhook_url: "https://chat.googleapis.com/v1/spaces/.../messages?key=...&token=..."
```

### 2.3 Trust tier (per agent or per project-role)

```yaml
trust_tier:
  project: acme-billing-service
  agent_role: engineer
  tier: 0            # 0 | 1 | 2
  granted_by: you
  granted_at: 2026-07-23
  history: [...]      # prior tier changes, for rollback/audit
```

### 2.4 Default team template (Paperclip company template, exported)

Six roles — Project Lead, Research, Design, Engineer(s), QA, Release/Deploy, Support — each a Paperclip agent with a `claude_local` adapter. Store the exported template as `templates/default-team.json` in this repo (not only inside Paperclip's own DB), so changes to the default org chart are diffable and reviewable. Per-role heartbeat interval and budget are part of this template; tune per project at instantiation.

---

## 3. Repo structure to scaffold

```
/ (this repo)
├── HANDOFF-agentic-harness.md  (this file)
├── docs/
│   └── proposal.md              (paste the full agentic-team-framework-proposal.md here)
├── templates/
│   └── default-team.json        # exported Paperclip company template, the six-role org chart
├── tools/
│   ├── raise_for_review.py      # the ONLY path that creates a review_item (§2.1)
│   └── notify.py                # renders review_item -> Slack Block Kit / Google Chat Cards v2, sends
├── config/
│   ├── notification_routing/    # one file per project, §2.2 shape
│   └── trust_tiers/             # one file per project+role, §2.3 shape
└── CLAUDE-agentic-harness.md    # project memory for future Claude Code sessions on this repo
```

---

## 4. Installation — tooling checklist

### 4.1 Paperclip

1. Install on the appserver (self-hosted): `npx paperclipai onboard` is the documented fast path as of this writing — confirm against current docs, since this is a fast-moving ~6-month-old project and install flow may have changed. Alternative: clone `github.com/paperclipai/paperclip`, `pnpm install`, `pnpm dev` for a from-source setup.
2. On first run it creates its own embedded PostgreSQL — no separate DB setup needed for a single-instance deployment.
3. Confirm the dashboard is reachable (default `http://localhost:3100` or your appserver's mapped port).

### 4.2 Claude Code CLI on every execution host

Each Paperclip agent's `claude_local` adapter invokes the Claude Code CLI directly — install and authenticate it on every host that will run an agent (dev machine and/or appserver, depending on where you place the pilot project's agents).

### 4.3 Per-agent Anthropic auth

Each agent adapter config needs its own `ANTHROPIC_API_KEY` (or subscription auth), referenced via Paperclip's secret syntax (`${secrets.anthropic_key}`) rather than hardcoded in adapter config — never commit these.

### 4.4 Slack app (beyond the Slack MCP connector already in use for chat)

1. Create a Slack app at https://api.slack.com/apps, install it to your workspace.
2. Bot token scopes needed: `chat:write` (send alerts), `channels:read`/`im:write` (resolve targets).
3. If building thread-reply capture (two-way), enable the Events API and set a Request URL pointing at an endpoint this repo exposes.
4. Store `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` in your secrets file.

### 4.5 Google Chat webhook (Phase 1, one-way)

1. In the target Google Chat space: Space menu → Apps & integrations → Webhooks → create.
2. Copy the generated webhook URL into that project's `notification_routing` config (§2.2).
3. No Google Cloud project needed for this simple path — that's only required for the Phase 2 two-way Chat app (§7).

### 4.6 Secrets checklist

```
ANTHROPIC_API_KEY
SLACK_BOT_TOKEN
SLACK_SIGNING_SECRET
GOOGLE_CHAT_WEBHOOK_URL   # per space, stored per-project in config/notification_routing/
```

---

## 5. Cross-repo touchpoint — read this before Task 6/7

**Cost rollup and `team_status` are consumed by the portfolio repo, but *written* by that repo's existing sync job — not by this repo.** The portfolio system's hard rule (its own CLAUDE.md §1) is that only its `sync/sync_computed_fields.py` touches the `computed:` frontmatter key. Rather than duplicating that write logic here:

- **This repo's job:** expose the data — a small, stable read interface (e.g., a `tools/cost_summary.py` and a Paperclip API query for agent/company status) that the portfolio repo's sync job can call or query.
- **The portfolio repo's job:** extend `sync_computed_fields.py` to add Paperclip as a second data source, alongside GitHub, writing `computed.cost_by_stage`, `computed.cost_total_mtd`, and `computed.team_status` the same way it already writes GitHub-derived fields.

If you're working in this repo alone, build the read-side (§2.1's data, cost totals by role) and stop there — the write into Obsidian is explicitly out of scope for this repo.

---

## 6. Phase 0 task list (pilot — one project)

**Task 0 — Scaffold.** Create the structure in §3. Copy the full proposal into `docs/proposal.md`. Write `CLAUDE-agentic-harness.md` (provided alongside this file) with the hard rules from §1.

**Task 1 — Install Paperclip**, confirm dashboard reachable (§4.1).

**Task 2 — Instantiate the pilot project's team** from `templates/default-team.json`: six agents, `claude_local` adapters, `cwd` pointing at the pilot repo's worktree for the code-touching roles, budgets set (`budgetMonthlyCents` — never leave unset), heartbeat intervals tuned per role (Project Lead frequent/on-demand, Support mostly event-triggered).

**Task 3 — Build `raise_for_review.py`.** Wraps Paperclip's Issues API, enforces the §2.1 schema, is the only path that creates a review item. No agent should have another way to raise one.

**Task 4 — Build `notify.py`.** Renders a `review_item` into Slack Block Kit and Google Chat Cards v2, sends via the configured channels in `config/notification_routing/<project>.yaml`. Both renderers must always include clickable links for every entry in `documents`, plus the primary "open in Paperclip" link.

**Task 5 — SLA escalation + daily digest.** A scheduled check (same cron/systemd pattern as elsewhere) flags `pending` items past their SLA, re-notifies, and separately produces one daily digest of every open item across tracked projects — a natural extension of the existing `morning` skill rather than a new mechanism.

**Task 6 — Cost summary read-interface.** Per §5 — build the read side only; confirm with the user before touching the portfolio repo's sync job.

**Task 7 — Team-status read-interface.** Same caveat as Task 6.

**Task 8 — Trust tiers.** Confirm every pilot agent starts at Tier 0 (§2.3): no skip-permissions, budgets set, approval gates on. Do not implement any auto-escalation path — tier changes are a manual, versioned edit the user makes directly.

**Task 9 — End-to-end pilot validation.** Confirm: an agent can raise a review item that produces a correctly-rendered Slack and/or Google Chat alert with working document links; an unanswered item escalates past its SLA; the cost summary read-interface returns sane per-role numbers; pausing the pilot project's agents is a one-step action.

---

## 7. Explicitly out of scope for Phase 0

Do not build these unless the user asks for them in a given session:

- The full two-way Google Chat app (Google Cloud project, interaction-event endpoint) — Phase 1 ships the one-way webhook only.
- Langfuse or any accounting-grade cost tool — only the simple rollup, per the proposal's staged approach.
- `@paperclipai/mcp-server` — optional convenience, not required for the design as spec'd.
- Any auto-escalation of trust tiers — tier changes are always a manual action.
- Rolling the team template out beyond the single pilot project.

---

## 8. Acceptance criteria for Phase 0

- The pilot project's six-agent team is running under Paperclip, budgets and heartbeat intervals set per role.
- A real (not simulated) review item raised by an agent produces a correctly rendered alert on every channel configured for that project, with working links to every attached document.
- An intentionally-unanswered low-priority item correctly escalates once its SLA passes.
- The cost summary read-interface returns a real per-role breakdown for the pilot project.
- Pausing the pilot project's agents is a single action, and that pause is visible wherever the portfolio repo's sync job next reads it.
- No agent in the pilot has `dangerouslySkipPermissions` enabled.

---

## 9. Open questions to raise with the user during this build

- Which project is the actual pilot?
- Slack app permissions — request `Events API` scope now (for future two-way) or defer until needed?
- Instrumentation approach for measuring heartbeat re-context overhead (proposal §8) — simplest is probably logging token counts per heartbeat by role for the pilot's duration before drawing conclusions.
