# Research — Claude Code cross-session messaging: fit for the agentic team harness

**Date:** 2026-08-08 · **Status:** research only — nothing adopted; decision tracked as plan D12 (finding F21 in `../../docs/implementation-plan.md`)
**Primary source:** https://code.claude.com/docs/en/cross-session-messaging.md (read 2026-08-08); agent-teams / headless / settings docs via the same site. Version facts current as of Claude Code v2.1.224 (Aug 2026).

## TL;DR

Claude Code sessions can now discover and message each other (`ListAgents` / `SendMessage`) — GA since v2.1.224, on by default on macOS/Linux. Same-machine messaging is full bidirectional over per-session Unix sockets restricted to the OS user; the appserver, where all six roles of a harness team will run as one user, is exactly the sweet spot. **Yes, this is useful for aiteam** — three leverage points, in ascending ambition: (L1) wake the raising agent the moment its review item is answered, instead of at its next heartbeat; (L2) push handoffs between roles (engineer → QA) instead of polling; (L3) a persistent-session team where messages, not heartbeat restarts, drive turns — a direct attack on the §8/F13 re-context overhead and therefore a fourth candidate in the H-Task 9 bake-off. Phase 0 changes only minimally: pin the CLI version, and make the Tier-0 messaging posture *explicit* (recommended: deny + refuse until D12 says otherwise). The separate **agent teams** feature is experimental and duplicates Paperclip's coordination role — watch-list, not adopt.

## The capability, confirmed from the official docs

- **Tools:** `ListAgents` discovers reachable sessions (subagents, other local sessions, remote/cloud sessions via Remote Control); `SendMessage` delivers plain text by session name. Sessions are named via `--name` / `/rename` (else auto-named from cwd). GA in **v2.1.224+**, macOS + Linux, on by default; not available on Bedrock/Vertex/Foundry (irrelevant here — D5 is subscription auth).
- **Scope:** same machine = full bidirectional over a per-session Unix socket (never through Anthropic servers), restricted to the same OS user. Cross-machine and cloud sessions are **reply-only** (via Remote Control). **Containers partition messaging: sessions see each other only if they share a filesystem** — two sessions in one container work; container↔host does not.
- **Headless:** a long-running `claude -p` worker binds an inbox socket and can receive messages; `--bare` mode does not. A `-p` session can't show approval dialogs, so unattended delivery requires `crossSessionInbound: accept` in its `--settings`.
- **Delivery semantics:** idle session → message starts a new turn immediately; busy session → queued between tool calls; each message lands as Delivered / Held / Refused per the receiver's inbound controls. Caps: 50 queued, 100 held; identical repeats dropped; loops rate-limited. Same-machine messages are transient — **no delivery guarantee, nothing survives a restart**, dead-session behavior undocumented.
- **The inbox socket is a documented script seam:** the path appears in `/status` and is exported to hooks and Bash as `CLAUDE_CODE_MESSAGING_SOCKET`; the docs explicitly cover "when you want a script or hook to post into a session." A same-user external process posting to a session's socket goes through the same inbound controls as any peer message.
- **Built-in trust posture:** an inbound message is marked as coming from another session, not the user; it cannot approve permission prompts, cannot change config/CLAUDE.md, embedded commands arrive as inert text, and the receiver's own permission rules still apply. Delivered messages count toward usage like a typed prompt.
- **Controls:** `crossSessionInbound: accept | hold | refuse` (a `refuse` in *project* settings beats every other scope); permission deny rules on the bare names `SendMessage` / `ListAgents` remove sending and listing; `isolatePeerMachines: true` gates cross-machine sends even under `bypassPermissions`. Footgun: `DISABLE_TELEMETRY`, `DO_NOT_TRACK`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, or `DISABLE_GROWTHBOOK` can disable the feature entirely via feature-flag evaluation.
- **Adjacent features, for the record:** **agent teams** (lead spawns teammates, shared task list, structured protocol messages) is experimental, opt-in via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, one team per session, no session resumption of in-process teammates. **Channels** (external events pushed into a session) is a research preview. The **Agent SDK** exposes resume/fork but no API to inject a message into a running session — irrelevant for us since `claude_local` drives the CLI.

## Why the harness topology is the sweet spot

Stage 5 puts all six roles of the pilot team on the appserver as one OS user, driven by Paperclip's `claude_local` adapter. That is precisely the configuration where messaging is strongest: same machine, same user, full bidirectional, no Anthropic-server transit. Two topology constraints follow immediately:

1. **Agents must share a filesystem to message each other.** If Stage 5 containerizes agents individually, messaging dies at the container boundary. Run the roles directly on the host (or all in one container) if D12 enables any messaging use. The portfolio sync container is unaffected — it never messages anyone.
2. **The same-user boundary is also the trust boundary.** Any same-user process can post to any session's socket, and a second project's team on the same host shares that boundary. Acceptable for a single-operator homelab; worth revisiting (per-project OS users) before multi-team rollout.

## Leverage cases

### L1 — Review-answer wake (highest value per unit risk)

Today (F12), an agent raises a review item, the user answers in the Paperclip dashboard, and the agent finds out at its *next heartbeat*. With messaging: the SLA/escalation cron (H-Task 5) — which already polls Paperclip — detects the `pending → answered` transition and posts one line into the raising agent's live session via its inbox socket: *"Review item <id> answered: <answer summary>."* The idle session starts a turn immediately; the review loop's latency drops from heartbeat-interval to seconds. Needs: a session registry (which session-id/socket belongs to which role — the `claude_local` wrapper records it at spawn), `crossSessionInbound: accept` on agent sessions, and the message audit log below. The critical-item flow (4h SLA) benefits most.

### L2 — Role-to-role handoff push

Engineer finishes; QA currently discovers the handoff by polling Paperclip at its own heartbeat. With messaging, the finishing role sends "branch X ready for QA, task <id>" directly. **Discipline required:** Paperclip stays authoritative for *what the team works on and whether it may* (the F17 discipline, verbatim) — a message is a *latency optimization on coordination*, never an assignment. The receiving role still claims the task in Paperclip; a message that names no checked-out Paperclip task is a nudge, not work. One paragraph in the role CLAUDE.mds encodes this.

### L3 — Persistent sessions: message-driven turns instead of heartbeat restarts

The big prize. Proposal §8's open problem is heartbeat re-context overhead: every wake replays identity/role/context. A long-running named `-p` session per role keeps its context window alive; messages (from Paperclip's wrapper, the cron, or peer roles) drive turns; the heartbeat degrades to a low-frequency liveness fallback. This directly attacks the §8/F13 overhead — not by re-injecting context smarter (the F17/F18 candidates) but by not discarding it. It therefore belongs in the **H-Task 9 memory-layer bake-off as a fourth candidate**: Paperclip-native context packet vs Beads `bd prime` vs claude-mem injection vs persistent sessions + messaging. Honest caveats: an unbounded-lifetime session eventually compacts (its own quality cost, and compaction ≠ curated memory); reconciling "Paperclip thinks in heartbeats" with "the session runs continuously" is unverified until the Stage 5 Paperclip client work — if Paperclip's budget metering, audit, and pause semantics assume it owns every invocation, persistent sessions outside that loop are split-brain (same failure F17 warns about). Evaluate on F13 evidence, not enthusiasm.

### L4 — Manual-drive synergy (free)

`/list-agents` from a user-driven session on the appserver shows the whole live team, and the user can message any agent directly. The pause-first rule (hard constraint #3) is unchanged — messaging an agent is not pausing it — but visibility improves: `team_status.py` could later report which sessions hold live inbox sockets.

## Guardrails the design must keep

- **Authority:** messages never assign work or grant anything. Paperclip = what/whether; messages = coordination. (Docs already enforce the mechanical half: no permission approval, no config changes, commands inert.)
- **Audit:** inter-agent messages bypass Paperclip's ledger. Before any leverage case ships, log every inbound/outbound message (sender, receiver, text, timestamp) — the wrapper and/or hooks can do this cheaply (`CLAUDE_CODE_MESSAGING_SOCKET` is exported before `SessionStart`). Same principle as F18 gate 6: what an agent saw must be reconstructable.
- **Reliability:** no delivery guarantee, transient sockets, restart drops everything. **Heartbeats guarantee; messages accelerate.** Nothing may *depend* on a message arriving.
- **Cost (hard rule #6):** message-triggered turns count as usage inside the receiving session, so the wrapper's project/role/task tags still attribute them; tag message-triggered turns distinctly so F13 can compare heartbeat-driven vs message-driven overhead.
- **Determinism at Tier 0 (F10 logic):** an unconfigured posture means held messages and expiring dialogs in headless sessions — exactly the silent-stall failure D4 was designed out of. The posture must be explicit either way.

## Agent teams: watch, don't adopt

It overlaps Paperclip's job (lead coordination, shared task list, spawning) — adopting it creates two orchestrators for one team. It's experimental, one-team-per-session, and in-process teammates don't survive `/resume`. The composable primitive aiteam wants is plain cross-session messaging; agent teams goes on the watch-list with Beads/claude-mem, re-evaluated only if Paperclip itself disappoints as orchestrator.

## What would need to be done

**Phase 0, cheap, do regardless of D12 (they make current behavior explicit):**
1. Stage 5 CLI install: require/pin Claude Code ≥ v2.1.224 on the appserver; verify with `/list-agents`; ensure no `DISABLE_TELEMETRY`-family env vars in agent environments.
2. Add the messaging posture to every Tier-0 allowlist preset (`harness/config/allowlists/`): **deny `SendMessage` + `ListAgents`, `crossSessionInbound: refuse`** in each role's project settings — deterministic silence until D12 opens it up. (A checked-in project-settings `refuse` is the strongest scope per the docs.)
3. Record the topology constraint in the Stage 5 deploy design: agent sessions share host/container if messaging is ever wanted.

**If D12 enables L1/L2 (Stage 5–6 work):**
4. `claude_local` wrapper: name sessions `<role>--<project>`, record session-id + socket path in a small registry file; start agents with `crossSessionInbound: accept` (scoped via `--settings`, not user-global).
5. Message audit log (wrapper- or hook-level JSONL beside the cost log) — gate for any messaging at all.
6. Extend the H-Task 5 cron with the answered-item wake (L1); add the coordination-not-assignment paragraph to role CLAUDE.mds (L2).

**If F13 evidence triggers L3 (H-Task 9):**
7. Persistent-session pilot for *one* role (Project Lead — highest heartbeat frequency, biggest §8 win), only after the Stage 5 Paperclip reconciliation confirms budget/audit/pause semantics tolerate externally-driven turns. Compared head-to-head with the F17/F18 candidates in the one bake-off decision.

## Open questions for D12

- Enable L1 (review-answer wake) in the pilot from Stage 6, or hold everything until H-Task 9 evidence?
- Is the same-OS-user trust boundary acceptable for the single-team pilot (recommended: yes, revisit at multi-team rollout)?
- Should the F13 instrumentation distinguish message-triggered turns from day one (recommended: yes — one extra tag, enables the L3 comparison)?
