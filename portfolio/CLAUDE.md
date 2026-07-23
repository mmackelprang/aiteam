# CLAUDE.md — Project Portfolio System

Project-level memory for the `portfolio/` subtree, loaded automatically when working here. Keep this to durable facts and hard rules — task sequencing lives in `HANDOFF.md`, design rationale in `docs/proposal.md`.

## What this is

A thin tracking/documentation layer above ~20 existing GitHub repos. One lightweight Obsidian note per project (status, priority, target quarter, links out), a Bases dashboard rolling them up, a repeatable bootstrap flow, and one narrow write-path for agents. GitHub stays the source of truth for all project detail — READMEs, ADRs, ROADMAP.md, issues are never copied into the vault.

## Hard rules — do not violate these without explicit user sign-off

1. **Three field categories, three writers, never mixed:**
   - *Judgment* (`status`, `priority`, `target_quarter`, `summary`) — human-edited only, directly in Obsidian. No script or agent ever writes these.
   - *Computed* (everything nested under the single `computed:` frontmatter key) — owned entirely by `sync/sync_computed_fields.py`, rewritten wholesale each run, never hand-edited.
   - *Agent-appended* (`stage`, `changelog`) — written only through `portfolio_updater/update.py`, never through free-form note edits.
2. **The sync job touches only the `computed:` key** — parse → replace that one key → serialize. Before pointing any sync change at real notes, prove on a throwaway note that a hand-edited `status` survives a run.
3. **`depends_on` is stored as real `[[wikilinks]]`** from the very first note — that is what makes Obsidian's graph view a free dependency map. Never plain strings.
4. **A repo's `ROADMAP.md` stays authoritative** for delivery-level roadmap. Notes store only `roadmap_source` + `roadmap_link` pointers and a computed staleness date — never roadmap content.
5. **Bootstrap produces drafts, not finished notes** (`_draft: true` marker). `status` / `priority` / `target_quarter` are set in the human review pass — never auto-finalized by a script or agent.
6. **The Obsidian Git plugin is enabled on the vault before anything writes to it.** It is the recovery safety net for rule 2.
7. **Agents update notes only via `portfolio_updater/update.py`** — enum `stage` plus a ≤140-char timestamped `changelog` append; it never accepts `summary` or `status`. Any subagent definition that touches the portfolio calls this tool, not note edits.
8. **Headroom is watch-list only** (proposal §10, `HANDOFF.md` §6.5): never register it, wrap calls with it, or run `headroom learn --apply` here unless the user explicitly asks for that pilot in a given session.

## Schema quick reference

```yaml
status:             roadmapped | planned | in-flight | on-hold | shipped | maintained | archived   # human-only
priority:           high | medium | low                                                            # human-only
stage:              research | design | development | testing | deployment | support               # portfolio-updater only
activity_state:     active (<60d) | idle (60-180d) | stale (>180d)                                 # computed, from last_commit
summary_confidence: high (0-1 missing signals) | medium (2-3) | low (4+)                           # computed
```

Full frontmatter shape and the confidence-signal table: `HANDOFF.md` §2.

## Conventions

- One concern per module: `bootstrap/` (enumerate → filter_defaults → ingest, in that order), `sync/`, `portfolio_updater/`.
- `common/` holds the portfolio-internal shared helpers — the byte-preserving frontmatter splice engine (frontmatter.py, the F6 piece: textual key-span splicing, never a YAML round-trip, `verify_untouched()` before every write), vault access, confidence signals, and the GitHub/fixture data sources. Shared within this subtree only; never imported from `../harness`. Tests: `python3 -m pytest portfolio/tests`.
- Secrets (`GITHUB_TOKEN`, `OBSIDIAN_API_KEY`, `OBSIDIAN_VAULT_PATH`) come from the gitignored `.env` — see `.env.example`.
- Cross-system: the harness (`../harness/`) exposes cost/team-status read-interfaces; **this** subtree's sync job is what will eventually write `computed.cost_by_stage`, `computed.cost_total_mtd`, `computed.team_status` into the vault (see `../harness/HANDOFF-agentic-harness.md` §5). Nothing here imports from `../harness/`.

## Current phase

Phase 0 — pilot set resolved (D1): **RTest, homelab, FamilyWorkspace**. Off-site build pass done 2026-07-23: the updater, sync engine (splice + no-op guard + dashboard markers), unclaimed-repos, and the bootstrap trio are implemented and fixture-tested (`--source fixture:PATH` runs the whole pipeline offline). ⚠ Still pending on-site: the live GitHub REST client is unverified until Stage 3, and real enumeration runs on the dev machine (plan F5). Stop and confirm with the user before Task 4 (the human review pass is theirs, never auto-approved) and before Task 8 (rollout beyond the pilot).
