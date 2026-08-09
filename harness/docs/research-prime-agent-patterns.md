# Research — PrimeIntellect prime-agent: patterns worth stealing for the harness

**Date:** 2026-08-09 · **Status:** research only — nothing adopted; decision tracked as plan D13 (finding F22 in `../../docs/implementation-plan.md`)
**Source:** https://github.com/PrimeIntellect-ai/prime-agent (MIT, ~9.2k stars at time of reading). README plus source reads of `packages/coding-agent/src/core/` (`refinement/refinement.ts`, file inventory of `autonomous.ts`, `goals.ts`, `agent-messages.ts`, `cron-jobs.ts`, `session-lease.ts`).

## TL;DR

Prime Agent is an autonomous coding/research agent runtime (TypeScript + persistent IPython kernel) built around long-lived daemon sessions, heartbeats, agent-to-agent messaging, and — its most original piece — a **"continual harness"**: durable per-agent supplemental state (prompts, memories, skills, subagent specs) that the agent refines through *small, evidence-backed, snapshot-reversible* updates, never touching the immutable base prompt. **Do not adopt the runtime** — it executes model-generated Python with the user's permissions and its own docs say it is not a security sandbox, which is disqualifying under the Tier-0 trust design, and aiteam's orchestrator choice (Paperclip + Claude Code) is already made. **Do steal the governance patterns**: (1) the refinement discipline is a ready-made answer to F18's gate 6 (the memory-poisoning guard) and should become acceptance criteria for whatever wins the H-Task 9 memory bake-off; (2) its natural aiteam implementation — git-versioned per-role refinement files — gives the "Paperclip-native" bake-off candidate a concrete, zero-new-dependency shape; (3) "budget exhaustion ≠ success" plus explicit quality gates is a one-paragraph convention worth adopting for the pilot roles. The rest of the feature set (daemon continuity, heartbeat re-entry, a2a messaging) independently converges on the F21-L3 persistent-session design — validating evidence, no new action.

## What prime-agent is

- An open-source agent with a **persistent IPython control environment**: file ops, shell, and tool use happen as executed code; `rlm(...)` spawns real child agents programmatically ("Recursive Language Model" — context as variables, subagents as function calls).
- **Daemon-backed continuity**: sessions persist when terminals disconnect (`prime-agent attach`, `--resume`); `prime-agent agents` lists running/idle/saved sessions; `/heartbeat` and `prime-agent schedule` give periodic re-entry (`cron-jobs.ts`, `session-lease.ts`).
- **Direct agent-to-agent messaging**: running agents and retained subagents discover each other and exchange messages without user mediation (`agent-messages.ts`).
- **`/autonomous` mode**: turn/token/time budgets with user-defined quality gates; a passed gate certifies only what that gate verifies, and **reaching a budget limit explicitly does not imply task success**.
- **`/goal`**: an objective that stays active across turns until completed, paused, or cleared.
- **Security posture (their own words):** executes model-generated Python and project commands with your user permissions; worker/kernel processes are *not* a security sandbox.

## The continual harness — mechanics (from `refinement/refinement.ts`)

- **State:** a versioned JSON `HarnessState` with four entry kinds — `prompt` (supplemental behavioral notes), `memory` (durable facts/decisions/preferences), `skill` (Python callables with explicit import/argument contracts), `subagent` (delegation templates). Each entry carries id, title, content, scope (local/global), version, timestamps. The **base system prompt is immutable** — refinement can never edit it.
- **Flow:** *plan* (LLM sees a truncated harness overview, recent refinement history, and recent conversation; returns a JSON proposal with `summary`, `rationale`, `expectedOutcome`, `edits`) → *validate* (action whitelist, required fields, immutability rules) → *apply* (conflict detection against a pre-planning baseline snapshot; per-edit before/after tracking; version increments; history append with evidence).
- **Guards:** an **auto-refine review gate** — a separate small LLM call whose job is to *reject one-off noise* before it becomes durable state; scope isolation (local refinement can't mutate global entries); per-proposal edit-scope enforcement; token caps.
- **Rollback:** every applied proposal is invertible (`rollbackProposal` reverses the edit list — deletes become creates, updates restore original content) and the new refinement links to its target via `rollbackOf`.
- **Persistence:** session-local state under the session artifact dir; global state under the agent dir with a `refinements.jsonl` append-only history; atomic tmp-file renames.

## What aiteam should steal

### S1 — The refinement discipline as acceptance criteria for the H-Task 9 memory winner

F18 gate 6 demands a poisoning guard before any unattended memory injection: "a wrong conclusion becomes durable team state re-injected forever" without retraction/expiry and per-session injection logging. Prime-agent's refinement loop is precisely that guard, worked out in shipping code: **small evidence-backed diffs (never wholesale rewrites) · a second-model review gate that rejects one-off noise · versioned append-only history · first-class rollback · immutable base prompt · local/global scope isolation.** Whichever candidate wins the H-Task 9 bake-off (Paperclip context packet, Beads `bd prime`, claude-mem, or F21-L3 persistent sessions), require these properties of it. This turns F18's abstract gate into a concrete checklist and applies equally to all candidates.

### S2 — Git-versioned per-role refinement files: the concrete shape of the "Paperclip-native" candidate

Prime-agent implements snapshots/rollback/history by hand (JSON versions + JSONL log + atomic renames). aiteam already has an infrastructure that provides all three for free and matches the repo's philosophy (hard rule #7: the org chart lives in git so changes are diffable): **git**. Sketch: each role gets a `memory.md` (or `harness-state.yaml`) in its worktree config area, distinct from the human-authored role CLAUDE.md (which stays immutable agent territory, mirroring prime-agent's immutable base prompt); at session end (or on `/refine`-equivalent prompting) the agent proposes a small diff; the diff is a git commit — history is the log, `git revert` is the rollback, and the review gate can be as simple as the Project Lead role (or the human, at Tier 0) approving the commit. This gives the bake-off's "Paperclip-native context packet" candidate a concrete, zero-new-dependency implementation, and it's the only candidate whose audit story (F18 gate 6's "reconstruct what an agent saw") is just `git log`. Not a new bake-off entrant — a sharpening of an existing one.

### S3 — "Budget exhaustion ≠ success" + explicit quality gates (adopt as convention)

Two sentences from prime-agent's autonomous mode worth encoding in the pilot role conventions: a passed gate certifies only what that gate verifies, and hitting a turn/token/time budget never counts as completing the task. aiteam mapping: an agent that exhausts its Paperclip budget or heartbeat allotment mid-assignment **raises a review item** (`raise_for_review`, type `question`, stating what's done/undone) rather than marking work complete — and per-assignment "done" should name a machine-checkable gate (tests green, build passes) where one exists. One paragraph in the role CLAUDE.mds at Stage 5; no code.

### S4 — Convergent validation of F21-L3 (no new action)

Prime-agent's core bet — persistent daemon sessions + heartbeat re-entry + direct a2a messaging + durable goals — is independently the same shape as F21's L3 persistent-session model under Claude Code. Two runtimes converging on it is evidence the shape is right; it changes nothing about the gate (Stage 5 Paperclip reconciliation + F13 data first).

## What not to take

- **The runtime itself.** Unsandboxed model-generated Python with user permissions is disqualifying at Tier 0, and adopting a second agent runtime beside Paperclip + Claude Code recreates the two-orchestrators problem (same reasoning that put agent teams on the watch-list in F21).
- **RLM / context-as-variables.** Inseparable from their IPython kernel architecture; nothing to transplant into a Claude Code harness.
- **Agent-authored skills** (`skill` entries + skill creator): interesting long-term, but a Tier-0 agent authoring its own callable tools is a trust-surface expansion in the wrong direction for the pilot. Revisit only post-pilot, and only through the S1 discipline (evidence, review gate, rollback).

## What would need to be done

1. **Now (doc-only):** fold S1's checklist into the H-Task 9 decision criteria; note S2 as the concrete shape of the Paperclip-native candidate. (This document + plan F22 do that; D13 confirms.)
2. **Stage 5:** add the S3 paragraph (budget-exhaustion → review item; named quality gates) to the pilot role CLAUDE.mds alongside the F4 stage-setter convention.
3. **H-Task 9:** evaluate candidates against the S1 criteria; if the Paperclip-native option wins, implement it as S2's git-versioned per-role files (worktree config area, immutable role CLAUDE.md untouched, lead/human-gated commits).

## Open questions for D13

- Adopt S1 (refinement-discipline criteria) as binding on the H-Task 9 decision, or advisory? (Recommended: binding — it is F18 gate 6 made concrete.)
- Adopt S3's convention at Stage 5? (Recommended: yes — one paragraph, no code, closes a real "declared success on an exhausted budget" failure mode.)
- Any interest in agent-authored skills post-pilot, or strike it from the watch-list entirely?
