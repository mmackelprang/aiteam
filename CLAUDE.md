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

- Task 0 (scaffold) complete for both systems, and the off-site build pass (2026-07-23) implemented the environment-independent core with 78 passing tests (`python3 -m pytest portfolio/tests harness/tests`): portfolio `common/` splice engine + updater + sync + bootstrap; harness review schema + raise-for-review + notify renderers + cost log/rollup + Tier-0 allowlist presets. Remaining stubs/unverified seams are flagged ⚠ in their docstrings: `harness/tools/team_status.py`, the Paperclip HTTP client (reconcile Stage 5), the live GitHub client (verify Stage 3), and real Slack/Chat sends (Stage 6).
- Both proposals are in place (`portfolio/docs/proposal.md`, `harness/docs/proposal.md` — the latter added 2026-07-23). Harness proposal §7's "append review queue to the note" is overridden by hard rule #3 — see plan F16/D9.
- `docs/implementation-plan.md` is the working plan: host topology (dev computer / NAS / appserver), review findings F1–F17 (F17 = Beads watch-list, adopt only on pilot evidence + sign-off), staged sequencing for both systems, decisions D1–D9 (all resolved 2026-07-23 — see plan §5). Read it before starting any stage; keep its stage checklist current as work lands.
- Host ground truth: `mmackelprang/homelab` (plan §1.0). Appserver = the `/srv/aiteam` stack (data on `/data/aiteam/`, deploys via an `appserver-aiteam` GHA runner, Paperclip `:3100` never published through Caddy); NAS = TrueNAS `datapool` (vault + `vault.git`, reached over `ssh nas`); tailnet `taila02f52.ts.net`. New services must be registered back into homelab's docs (service doc, DASHBOARDS, Homepage, SECRETS pointers).
- Root-level `bin/` is sanctioned glue: wrappers may invoke each subtree's CLI as subprocesses (never import across subtrees). First instance: `bin/new-project` (plan F15) — adding a project/PM must stay configuration, not development.
- Next: portfolio Phase 0 Task 1 — per the plan's Stage 1, it must run on the dev machine (this cloud session's GitHub scope is aiteam-only, finding F5). The portfolio pilot comes before the harness install — the harness reports into it.
- Stop-and-confirm gates with the user: portfolio Tasks 4 and 8 (`portfolio/HANDOFF.md` §5). Decisions D1–D9 are resolved (plan §5): pilot repos RTest / homelab / FamilyWorkspace; harness pilot FamilyWorkspace; git-as-transport; Tier-0 allowlists; subscription-auth first; `computed.open_reviews` via sync (D9).
- Google Chat is a first-class channel: per-agent named webhooks first (one-way), two-way Chat app only as an explicit Phase 2 — plan finding F14. Hard rules #4/#5 in `harness/CLAUDE.md` still apply.
