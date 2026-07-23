# Agentic Team Framework / Harness — Proposal

A companion system to the [Project Portfolio System](../../portfolio/docs/proposal.md): a per-project team of AI agents with a defined hierarchy, execution model, cost tracking, and human-review workflow, reporting up into the portfolio dashboard already spec'd. This doc captures the decisions made through discussion and research; it's a proposal to react to, not a locked design.

---

## 1. Framework choice: Paperclip

Adopting [Paperclip](https://github.com/paperclipai/paperclip) (open source, MIT, Node.js server + React dashboard) as the org-chart/budget/approval/audit runtime, wrapping Claude Code sessions as the actual "employees." Rationale, in brief: it's explicitly not an agent-building framework — it takes agents you already have and gives them org charts, budgets, governance, approvals, and a durable audit trail, which matches this system's needs far more directly than building the same primitives on top of raw Claude Code subagents, or adopting a heavier code-first framework (LangGraph, CrewAI) that would require building the coordination layer from scratch.

Known caveats carried forward from the initial evaluation (see prior discussion): ~6 months old, single pseudonymous lead author, file-based memory noted as a scaling limitation, and an openly-acknowledged security gap in its third-party skills ecosystem. None of these are disqualifying, but they're why several decisions below default to conservative/pilot-first rather than full rollout.

---

## 2. Org chart and execution pattern

**Default team template**, instantiated per project, covering the ~90% case:

```
Board (you)
 └── Project Lead agent          — decomposes the project goal, delegates, aggregates status
      ├── Research agent
      ├── Design agent
      ├── Engineer agent(s)       — cwd = project's repo/worktree
      ├── QA agent                — same cwd
      ├── Release/Deploy agent    — same cwd, CI/CD-facing
      └── Support agent           — low-frequency, mostly event-triggered
```

- **Tunable at creation and over time.** The template covers the default case; individual projects can drop/add roles (e.g., no Design agent for a backend-only service, a second Engineer for a larger repo) by editing the instantiated config. Paperclip already revisions agent configs and supports rollback, so tuning a role later is a normal versioned edit, not a special case.
- **The canonical template lives in this repo too**, not only inside Paperclip's own database — exported alongside the rest of the portfolio-system schema, under git, so a change to "what the default team looks like" is a diffable, reviewable change, and upgrading existing projects to a newer default is a deliberate action rather than silent drift.
- **Execution pattern: always-on, heartbeat-driven** (Paperclip's native model) rather than a strict sequential pipeline. Heartbeat cadence is tuned per role, not uniform — the Project Lead checks in often and on-demand (assignments, mentions); Support is almost entirely event-triggered rather than polling on a schedule. This matters for cost as much as responsiveness.

---

## 3. Dashboard visibility: who's actively working where

**Problem:** Paperclip's atomic task-checkout and execution locks prevent two Paperclip-driven agents from colliding with each other, but Paperclip has no visibility into a manual Claude Code session driven outside it — that collision risk is real and not automatically solved just by adopting this system.

**Design:**
- Extend the portfolio project note's `computed:` block (see portfolio proposal §3) with a `team_status` field: `idle | automated-active | manual-active`, sourced from Paperclip's own agent/company status via the existing sync job.
- Going hands-on manually becomes one explicit action — pause that project's Paperclip agents before driving manually — rather than a purely mental discipline. That single action both prevents the actual collision and keeps `team_status` accurate, satisfying the "make this visible on the dashboard" requirement directly.

---

## 4. The review queue (the highest-priority piece of this system)

This is treated as the make-or-break value of the whole harness, per discussion — designed accordingly.

### 4.1 Structure

Reuses Paperclip's native Issues (labels, priority, comments) rather than inventing a parallel system, extended with the fields production HITL systems converge on:

```yaml
review_item:
  id: <Paperclip issue id>
  project: acme-billing-service
  type: question | design-decision | roadmap-direction | doc-review
  priority: critical | high | medium | low
  summary: "agent-authored, 1-2 sentences"
  reasoning: "why the agent is asking, what it already tried"
  confidence_score: 0.0-1.0
  documents: [{ label, url }, ...]     # zero or more, always clickable
  status: pending | answered | expired
  raised_at / sla_due_at / answered_at
```

Raised through a single narrow **`raise-for-review`** tool (same discipline as the portfolio system's `portfolio-updater`) — no agent free-writes into this structure; it only ever gets created through this one call.

### 4.2 Notification — the actual fix for "I miss pending items"

The root problem isn't that a queue doesn't exist — it's that nothing pulls you back to it. Fix is multi-channel push, not a dashboard to remember to check:

- **Slack and Google Chat, both supported**, routed per-team (some teams live in Slack, some in Google Chat, some in both) via a per-project config set at team-creation time (§2's tuning step).
- **One internal alert shape, rendered per channel** — same pattern as Paperclip's own adapters:
  - Slack (Block Kit): priority/project header, summary, each document as a clickable link, primary "Open in Paperclip" link.
  - Google Chat (Cards v2, incoming webhook): header card, summary section, a button per document link, plus the primary link.
- **Known asymmetry, addressed explicitly rather than papered over:** Slack supports two-way reply capture now (a thread reply is written back as a Paperclip comment, which can wake the blocked agent immediately via @-mention). Google Chat's simple incoming webhook is **one-way only** — real two-way reply capture requires a full Chat app (Google Cloud project, an endpoint receiving interaction events), a meaningfully bigger lift. **Plan: ship the Google Chat webhook first** (satisfies alerting + clickable documents immediately), treat the full two-way Chat app as a fast-follow once the alerting itself is proven. In the interim, a Google Chat-only team replies directly on the Paperclip issue via the alert's primary link.
- **Staleness is a first-class state, not silence.** Priority-based SLAs (critical: 4h, high: 1 day, medium: 3 days, low: 1 week); unanswered items past their SLA auto-escalate (re-notify, bump into the daily digest) rather than aging quietly.
- **A daily digest as the guaranteed catch-all**, independent of per-item pushes — every open review item across all projects, sorted by priority and age. Natural fit for the existing `morning` skill rather than a new mechanism.

### 4.3 Guardrail against the opposite failure mode

Routing everything to review risks the well-documented flip side — reviewers rubber-stamping once volume is high and accuracy looks good ("automation complacency"). The `confidence_score` field exists so, once a pattern is trusted, low-stakes/high-confidence items can graduate to auto-proceed. **Start conservative — everything routes to review — and loosen only with evidence**, never by default.

---

## 5. Cost tracking: by step and by project

Two tiers, staged rather than both built at once:

- **Now — a rollup script**, matching the portfolio system's existing sync-job pattern: reads Paperclip's native per-agent/per-run cost events via its API, groups by project (company) + agent-role + task, writes the summary into the project note's `computed:` block (`computed.cost_by_stage`, `computed.cost_total_mtd`). This is genuinely integration work, not a build.
- **Later, if this becomes a real service offering with client-facing accounting** — Langfuse (MIT, self-hostable) is the standout option: per-trace cost with tags, versioned pricing tables, rollups — the "accounting-grade chargeback" bar. (Helicone was considered and set aside — acquired by Mintlify in March 2026 and now maintenance-mode only; not a good new-adoption target.)
- **Tag cost data using OpenTelemetry GenAI semantic conventions from day one**, regardless of which tier is active — the common substrate nearly every cost tool eventually reads, and the difference between swapping tools later versus re-instrumenting everything later.

---

## 6. Trust and autonomy tiers

Secure-by-default, with explicit, auditable dials to loosen over time — never silent creep:

- **Tier 0 (default, every new project/agent):** no `dangerouslySkipPermissions`; every write/push/deploy action gated; conservative heartbeat intervals; everything routes through the review queue.
- **Tier 1:** low-risk actions (running tests, reading files, commenting) auto-approved; anything touching prod config, deploys, or spend above a threshold still gated.
- **Tier 2:** skip-permissions allowed for a specific agent/role, granted explicitly by the Board (you) after a track record (e.g., N successful runs, zero rollbacks) — never granted by the system itself.

Stored and versioned the same way Paperclip already revisions agent configs, so raising *or lowering* trust is an explicit, rollback-able action — same principle applied everywhere else in this design (many narrow writers, nothing silently expanding its own scope).

---

## 7. Reporting integration with the portfolio system: hybrid

Confirmed approach from discussion:
- **Cost and status summaries flow passively** via the existing sync job into the project note's `computed:` block, alongside the GitHub-derived fields — Paperclip becomes just one more data source for a mechanism that already exists, not a new write-path.
- **The review queue is pushed actively**, via a dedicated tool (`raise-for-review`, §4.1) that only ever appends to a capped review-queue list on the note — never touching `summary`, `status`, or anything else. Highest-value, most time-sensitive content gets surfaced where you already look, without widening who can write to the vault.

---

## 8. Open item: heartbeat re-context overhead (not yet resolved by design — needs measurement)

Live, acknowledged gap in Paperclip itself: there's an open upstream feature request for importance-scored, top-N memory injection (rather than full-context replay) between heartbeats, and a third-party plugin already fills this today via selective injection at run-start. Paperclip's own "context packet" is somewhat curated already (memory state + open tasks + recent inputs, not full conversation history), but identity/role/company-context still resends every heartbeat regardless of whether anything changed.

**Plan: measure before designing a fix.** During the pilot, instrument actual reinjection token overhead per role — likely low for infrequent roles (Support), possibly meaningful for frequent ones (Project Lead checking in hourly). If it's meaningful, the fix is the same principle applied throughout this design: inject only what's relevant and changed, not everything — not a new caching mechanism invented from scratch.

---

## 9. Adversarial findings carried into this design (recap, with resolutions)

| # | Finding | Resolution |
|---|---|---|
| 1 | Always-on heartbeats can collide with manual Claude Code sessions in the same repo | Explicit pause-before-manual-work action, surfaced as `team_status` on the dashboard (§3) |
| 2 | 20 projects × ~6 agents ≈ 120 configs to tune/monitor | Canonical template + per-project tuning at creation and over time, versioned in-repo (§2) |
| 3 | Review queue was resting on unenforced convention | Dedicated `raise-for-review` tool, structured schema, multi-channel push, SLA-based escalation (§4) |
| 4 | "Cost by step" is a real gap, not a native Paperclip feature | Staged: custom rollup now, Langfuse-class tool later if needed for client accounting (§5) |
| 5 | Security posture (skip-permissions, skills marketplace gaps) needs a conscious dial | Three-tier trust model, Board-granted only, versioned/rollback-able (§6) |
| 6 | Heartbeat wake/reorient overhead could compound across ~120 agents | Measure in pilot before designing a fix; reuse the selective-injection pattern already proven elsewhere if needed (§8) |

---

## 10. Suggested pilot scope

Consistent with the portfolio system's own Phase 0: **one project, not all 20.** Tier 0 trust by default, hybrid reporting integration, both notification channels wired (even if only one team needs each, to prove the pattern), and instrumentation in place to actually measure §8 rather than guess. Expand to the remaining projects only after the pilot validates the operational load assumptions in finding #2.

---

## 11. Dependent components — full list

Everything this design relies on, split into what's already required by the portfolio system (shared infrastructure, not new work) versus what this harness specifically adds, plus what's optional/deferred.

### 11.1 Already required by the portfolio system (no new work, listed for completeness)

| Component | Role here | Reference |
|---|---|---|
| Git / GitHub + a Personal Access Token | Source of truth for project repos | Portfolio proposal §2 / HANDOFF §4.3 |
| GitHub MCP connector | Repo enumeration, metadata | HANDOFF §4.3 |
| Node.js (v18+), Python (3.10+), `uv`/`uvx` | Runtime for scripts and MCP servers | HANDOFF §4.2 |
| Docker (or equivalent) on the appserver | Container runtime for scheduled jobs | HANDOFF §4.5 |
| cron / systemd timer | Scheduling for the sync job | HANDOFF §4.5 |
| NAS (vault storage) + appserver (containers, CI/CD) | Underlying infra | HANDOFF §4.5 |

Note: Obsidian itself (and its plugins — Bases, Dataview, Obsidian Git, Local REST API, `mcp-obsidian`) is a portfolio-system dependency, **not** a direct dependency of this harness under the hybrid integration model (§7) — Paperclip agents never talk to Obsidian directly; only the existing sync job does, extended to pull from one more source.

### 11.2 New for this harness

| Component | Type | Where it runs | Notes / prerequisites |
|---|---|---|---|
| **Paperclip** (server + dashboard) | Required | Appserver (self-hosted) | Node.js server, React UI, embedded PostgreSQL created automatically on first run. MIT licensed. |
| **Claude Code CLI** | Required | Wherever each agent's `claude_local` adapter executes (dev machine and/or appserver) | Needs its own reachable install per execution host; already in use elsewhere in this system, but Paperclip's adapter invokes it directly, so it must be installed/authenticated on any host running an agent |
| **Anthropic API key or Claude subscription auth**, per agent | Required | Wherever Claude Code CLI runs | Cost driver — budget limits (§6) apply per key/agent |
| **`raise-for-review` tool** (custom) | Required, to be built | Wherever Paperclip agent skills execute | Thin wrapper around Paperclip's Issues API — no external dependency beyond Paperclip's own REST API |
| **Cost rollup script** (custom) | Required, to be built | Appserver, same cron/systemd pattern as the existing sync job | Reads Paperclip's cost-events API; no new infra, reuses existing scheduling |
| **Slack app/bot credentials** (bot token, signing secret) | Required (Slack teams) | Wherever the notification sender runs | Beyond the Slack MCP connector already in use for chat — sending alerts and capturing thread replies needs bot-level Slack app permissions (`chat:write`, Events API subscription for reply capture) |
| **Google Chat incoming webhook** (per space) | Required (Google Chat teams, Phase 1) | Wherever the notification sender runs | One webhook URL per Chat space; one-way only (§4.2) |
| **Google Cloud project + Chat API + Chat app** | Deferred (Phase 2) | Appserver (needs a reachable endpoint for interaction events) | Only needed when/if two-way Google Chat reply capture is built; meaningfully more setup than the Phase 1 webhook |

### 11.3 Optional / deferred

| Component | Status | Notes |
|---|---|---|
| `@paperclipai/mcp-server` | Optional | Exposes Paperclip's REST API as MCP tools — lets you manage Paperclip (create issues, approve actions) conversationally from Claude Desktop/Code instead of only the web dashboard. Not required for the design as spec'd. |
| **Langfuse** (self-hosted) | Deferred | Only if cost tracking needs to graduate to client-facing, accounting-grade chargeback (§5). Has its own hosting footprint (self-hosted, MIT) separate from Paperclip's. |
| **OpenTelemetry GenAI semantic conventions** | Convention, not infra | Not a component to install — a tagging standard to follow now (§5) so a later move to Langfuse or any other cost tool doesn't require re-instrumenting |

### 11.4 Credentials/secrets checklist (new, beyond the portfolio system's existing `.env`)

```
ANTHROPIC_API_KEY (or per-agent equivalent)
SLACK_BOT_TOKEN
SLACK_SIGNING_SECRET
GOOGLE_CHAT_WEBHOOK_URL (per space)
# Phase 2 only:
GOOGLE_CLOUD_SERVICE_ACCOUNT_CREDENTIALS
```

None of these should be committed — same convention as the portfolio system's `.env` handling (HANDOFF §4.6).
