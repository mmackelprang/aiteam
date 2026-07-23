# CLAUDE.md — aiteam (project & team management)

Repo-level memory, loaded for every session. Two companion systems live here, one self-contained subtree each — **read the subtree's own CLAUDE.md before touching it**:

- `portfolio/` — Project Portfolio System (Obsidian notes + dashboard over GitHub repos). Memory: `portfolio/CLAUDE.md`. Sequencing: `portfolio/HANDOFF.md`.
- `harness/` — Agentic Team Harness (per-project AI teams under Paperclip). Memory: `harness/CLAUDE.md`. Sequencing: `harness/HANDOFF-agentic-harness.md`.

They were designed as two separate repos and must stay separable: no imports or code references across subtrees. The only sanctioned coupling is the read-interface boundary below.

## The one cross-system rule

**The portfolio sync job is the single writer into the Obsidian vault's `computed:` fields; the harness only exposes read-interfaces.** Cost rollups and team status reach the vault by `portfolio/sync/sync_computed_fields.py` consuming `harness/tools/cost_summary.py` / `team_status.py` (and the Paperclip API) — never by the harness writing into the vault. (Portfolio hard rules #1–2; harness hard rule #3.)

## Repo-wide conventions

- Secrets live in each subtree's gitignored `.env` (`.env.example` documents the names). Never hardcoded, never committed.
- Python 3.10+, one concern per module — matching the narrow-write-surface philosophy of both systems.
- Judgment fields in vault notes (`status`, `priority`, `target_quarter`, `summary`) are human-only. Everywhere, always, no exceptions.

## Status (2026-07-23)

- Task 0 (scaffold) complete for both systems. Every `.py` file is a stub with its contract in the docstring — implementation follows each handoff's task order.
- `harness/docs/proposal.md` is a placeholder — the full agentic-team-framework proposal wasn't in the uploaded package; add it when available.
- `docs/implementation-plan.md` is the working plan: host topology (dev computer / NAS / appserver), review findings F1–F14, staged sequencing for both systems, open decisions D1–D8. Read it before starting any stage; keep its stage checklist current as work lands.
- Next: portfolio Phase 0 Task 1 — per the plan's Stage 1, it must run on the dev machine (this cloud session's GitHub scope is aiteam-only, finding F5). The portfolio pilot comes before the harness install — the harness reports into it.
- Stop-and-confirm gates with the user: portfolio Tasks 4 and 8 (`portfolio/HANDOFF.md` §5); harness pilot-project choice (`harness/HANDOFF-agentic-harness.md` §9); decisions D1–D8 in the plan.
- Google Chat is a first-class channel: per-agent named webhooks first (one-way), two-way Chat app only as an explicit Phase 2 — plan finding F14. Hard rules #4/#5 in `harness/CLAUDE.md` still apply.
