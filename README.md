# aiteam — project & team management

The starting repo for two companion systems that together manage a portfolio of ~20 projects and the per-project AI teams that work on them:

| Subtree | System | What it does |
|---|---|---|
| [`portfolio/`](portfolio/HANDOFF.md) | **Project Portfolio System** | A thin tracking layer above existing GitHub repos: one Obsidian note per project, a portfolio dashboard, a repeatable bootstrap flow, and one narrow structured write-path for agents. GitHub stays the source of truth for all project detail. |
| [`harness/`](harness/HANDOFF-agentic-harness.md) | **Agentic Team Harness** | Per-project AI teams (research / design / dev / test / deploy / support) running under [Paperclip](https://github.com/paperclipai/paperclip) with Claude Code sessions as the workers — review queue, notifications, trust tiers, cost tracking. |

The two systems were designed as **two separate repos**. They start life here as one repo with one fully self-contained subtree each, so splitting them out later stays trivial. Nothing in either subtree reaches into the other except the documented read-interface boundary below.

## How the two systems connect

Harness agents report **cost** and **team status** up into the portfolio's Obsidian vault — but the actual write happens in the **portfolio's** sync job (`portfolio/sync/sync_computed_fields.py`), extended to treat Paperclip as a second data source alongside GitHub. The harness only ever builds **read-interfaces** (`harness/tools/cost_summary.py`, `harness/tools/team_status.py`). See `harness/HANDOFF-agentic-harness.md` §5 for the exact boundary.

## Where things stand

- ✅ **Task 0 (scaffold) done for both systems** — structure, docs, templates, stub modules, and project memory (`CLAUDE.md`) are in place. All `.py` files are stubs carrying their contract in the docstring; implementation follows each handoff's task order.
- 📋 **[`docs/implementation-plan.md`](docs/implementation-plan.md)** — the working plan: component placement across dev computer / NAS / appserver, review findings F1–F14 (including the Google Chat per-agent identity design), the staged plan for both systems, and the open decision list D1–D8.
- ⚠️ **Missing:** `harness/docs/proposal.md` — the full `agentic-team-framework-proposal.md` was not part of the uploaded package. A placeholder marks the spot; drop the real proposal in when available.
- ⏭️ **Next:** the plan's Stage 0 checklist (remote-doable prep + decisions), then Stage 1 at the dev computer — portfolio Phase 0, Task 1 onward. Portfolio pilot comes **first**; the harness's cost/status reporting has nothing to write into otherwise.

## Getting started (new Claude Code session)

- Portfolio work: *"Read portfolio/HANDOFF.md and start on Phase 0, Task 1."*
- Harness work (after the portfolio pilot exists): *"Read harness/HANDOFF-agentic-harness.md and start on Phase 0, Task 1."*

Tooling install checklists (Obsidian + plugins, MCP connectors, Paperclip, Slack / Google Chat) live in each handoff's §4. Secrets go in each subtree's gitignored `.env` — see the `.env.example` files; never commit them.
