# Project Portfolio System — Proposal (v2)

A thin tracking/documentation layer above your GitHub repos (org and/or personal), bootstrapped from existing repos, that gives you a single point-in-time view across ~20 projects without duplicating per-project documentation.

*v2 changelog: incorporates round-1 adversarial review findings — see §7 for what changed and why.*

---

## 1. Design principles

1. **GitHub stays the source of truth for project detail.** READMEs, ADRs, changelogs, issues, ROADMAP.md — never copied elsewhere.
2. **Obsidian holds one pointer/summary note per project**, not documentation. Small enough to stay current.
3. **A single dashboard rolls all pointer notes up into one view** — by status, stage, priority, target quarter, and now activity/freshness.
4. **Bootstrapping is a repeatable process, not a one-time script.** New repos appear; the system needs a way to notice and re-run selection, not just an initial import.
5. **Fields split into three kinds**, tracked and written by different actors:
   - *Judgment* — only a human sets these (status, priority, target quarter, the curated summary paragraph).
   - *Computed* — derived mechanically from GitHub/repo state, rewritten wholesale on each sync run, never hand-edited (last commit, open issues, activity state, confidence signals).
   - *Agent-appended* — a narrow, structured channel agents may write to during normal work (changelog entries, stage transitions) — never the judgment fields, never free prose into the summary.

---

## 2. Tooling stack

| Component | Tool | Where it runs |
|---|---|---|
| Repo enumeration + metadata | GitHub MCP connector (or `gh` CLI as fallback) | Dev machine / bootstrap session |
| Vault | Obsidian, vault stored on NAS, synced to dev machine | NAS |
| Vault version safety net | Obsidian Git plugin (auto-commit on change) | NAS / dev machine |
| Vault access for Claude | `mcp-obsidian` (Local REST API-based) | Dev machine |
| Portfolio table/board view | **Bases** (core, no-code, filter/group by frontmatter) — Phase 0 | Obsidian |
| Narrative dashboard + rollups | **Dataview** (query language) — Phase 2+ | Obsidian plugin |
| Dependency visualization | Obsidian's native graph view, filtered to project notes (free, if `depends_on` uses real `[[wikilinks]]`) | Obsidian |
| Scheduled computed-field sync | Script (cron/systemd timer), writes only the nested `computed:` block | Appserver (container) |
| Ongoing status updates | A dedicated **portfolio-updater** tool, called by working subagents at end of session — not free-form note editing | Dev machine |

---

## 3. Schema (frontmatter on each project note)

```yaml
---
project: acme-billing-service
source: org                 # org | personal
repo: acme-inc/acme-billing-service     # blank if pre-repo (roadmap item)
visibility: private

# --- judgment: human-set, agents never overwrite ---
status: in-flight            # roadmapped | planned | in-flight | on-hold | shipped | maintained | archived
priority: high
target_quarter: 2026-Q3
owner: you
summary: >
  One paragraph, human-approved, on what this is and why it matters.
depends_on: ["[[acme-auth-service]]"]     # real wikilinks -> free graph view, manual, reviewed periodically (see §6)
roadmap_source: repo         # repo | portfolio | external-tool | none
roadmap_link: "acme-inc/acme-billing-service/ROADMAP.md"

# --- agent-appended: narrow, structured, append-only ---
stage: development            # research | design | development | testing | deployment | support — agents may set via portfolio-updater
changelog:
  - { date: 2026-07-20, note: "Deploy subagent shipped v2.3.1 to staging" }
  - { date: 2026-07-18, note: "Test subagent: integration suite green" }

# --- computed: sync-job owned, rewritten wholesale each run, never hand-edited ---
computed:
  last_commit: 2026-07-20
  open_issues: 4
  latest_release: v2.3.1
  language: TypeScript
  archived_on_github: false
  activity_state: active       # active | idle | stale — derived from last_commit vs threshold
  summary_confidence: medium   # high | medium | low — see §5.2
  missing_signals: ["no CONTRIBUTING.md", "no tests directory detected"]
  last_synced: 2026-07-22T06:00:00
---
```

Nesting computed fields under `computed:` (rather than mixing them flat with judgment fields) means the sync job can safely do "parse → replace the `computed` key → write" without any risk of touching `status`, `summary`, or anything else a human set. This is the fix for round-1 finding #4 — see §7.

---

## 4. Bootstrap flow

**Set expectations up front.** Bootstrap produces drafts, not finished notes. The review pass in Step 4 is real work, and its length depends entirely on how well-documented your repos already are — a repo with a solid README and CONTRIBUTING doc might need 30 seconds of review; one with neither could need you to write the summary from scratch. Plan for an afternoon the first time, not five minutes. (This callout should also appear verbatim in the dashboard's onboarding note and in the "add a new project" doc — see §5.4.)

**Step 0 — Connect.** Authorize the GitHub MCP connector against your org account and/or personal account.

**Step 1 — Enumerate.** Pull the full repo list per account: name, description, visibility, language, last push, archived flag, fork flag, and whether a `ROADMAP.md` exists.

**Step 2 — Filter defaults, then select.** Exclude archived repos, forks, and repos with zero commits in 2+ years by default, then present the remainder for inclusion/exclusion. Re-run periodically — see §5.4 for how you're prompted to.

**Step 3 — Ingest + draft summary, with a confidence rating.** For each selected repo, check for the presence and freshness of a defined set of signals, and record what's missing rather than passing a vague judgment:

| Signal checked | Missing → recorded as |
|---|---|
| README present | "no README" |
| README updated within 1 commit-era of latest code | "README appears stale" |
| CONTRIBUTING.md / ARCHITECTURE.md present | "no CONTRIBUTING.md" / "no ARCHITECTURE.md" |
| Commits in last 90 days | "no recent commit activity" |
| Tests directory detected | "no tests directory detected" |
| CI config present (`.github/workflows`, etc.) | "no CI config detected" |
| Releases/tags present | "no releases tagged" |
| `ROADMAP.md` present | flagged for §6 roadmap handling, not a confidence penalty |

`summary_confidence` is a simple rollup: 0–1 missing signals → `high`, 2–3 → `medium`, 4+ → `low`. The point isn't to score the repo — it's to tell your future self, during the review pass, which drafts to read carefully and which to skim-confirm.

**Step 4 — Human review pass.** Walk through drafts sorted by `summary_confidence` (low first, since those need the most attention). Confirm/edit the summary, and set what nothing can infer: `status`, `priority`, `target_quarter`.

**Step 5 — Write + build views.** Create the notes, build the Bases portfolio view (group by `status`), and — once you're past Phase 0 — the Dataview dashboard.

**Step 6 — Schedule sync + version safety net.** Stand up the computed-field sync job on the appserver (nightly), and enable the Obsidian Git plugin on the vault so every change — sync job or human — is auto-committed. If anything ever gets clobbered, `git diff`/`git revert` recovers it; this is the practical backstop for finding #4, on top of the schema-level fix.

---

## 5. Ongoing operation

### 5.1 Status/stage updates — avoiding the "wall of subagent prose" problem

Rather than letting each working subagent (research/design/dev/test/deploy/support) freely edit the project note, they call a single narrow **portfolio-updater** tool with a constrained input shape:

```
update(project, stage?: enum, changelog_note?: string ≤140 chars)
```

- `stage` is one of the fixed enum values — no free text.
- `changelog_note`, if given, is *appended* to the `changelog` array with a timestamp — it never rewrites `summary`.
- `summary` and `status` are never touched by this tool at all; they stay human-only, edited directly in Obsidian.

This keeps the note's curated narrative stable while still getting a live, low-noise trail of what happened and when — the changelog becomes a nice-to-read audit log, not a place prose accumulates unchecked.

### 5.2 Sync job mechanics

Nightly job: for each project note with a `repo` set, hit the GitHub API, build a fresh `computed:` block, and replace only that key in the frontmatter (parse → merge on the single key → serialize). Never touches `status`, `summary`, `depends_on`, `changelog`, or anything else. Confidence signals (§4, Step 3) are recomputed the same way on every run, so a project's `summary_confidence` can improve over time as you add tests/CI/docs — a small extra incentive to keep repos tidy.

### 5.3 Activity state instead of forcing "completed"

Many of these projects won't have a clean "done" — they become long-lived services. Rather than forcing everything into `completed`, the `status` enum now uses `shipped` / `maintained` / `archived` for the different flavors of "not actively being built," and a separate **computed, non-judgment** field, `activity_state`, flags freshness automatically:

- `active` — last commit within 60 days
- `idle` — 60–180 days
- `stale` — 180+ days

`activity_state` never overwrites `status` — it's a second signal shown alongside it on the dashboard ("in-flight, but stale" is a useful and different thing to notice than "in-flight and active"). This also gives you a natural dashboard filter for the retirement question from round 1 (finding #9): anything `stale` and not `archived` is a prompt to go decide what it actually is, rather than an automatic reclassification.

### 5.4 "Add a new project" — surfaced in the dashboard, not just docs

Two entry points, both visible directly on the dashboard note (not buried in separate documentation you have to remember exists):

- **Existing repo, not yet tracked:** the nightly sync job also diffs your GitHub account's repo list against what's already in the vault, and writes a small "Unclaimed repos" list into the dashboard — a queue of repos found but not yet bootstrapped, so new work doesn't silently sit outside the system.
- **No repo yet (roadmap idea):** a `/add-roadmap-project` quick-capture template creates a note directly with `status: roadmapped` and no `repo` field — a couple of prompted fields (name, one-line rationale, rough target quarter), not the full bootstrap flow, since there's nothing to ingest yet.

---

## 6. Roadmap governance (round-1 finding #3)

Many of your repos already have a `ROADMAP.md`. Rather than inventing a new place for delivery-level roadmap detail, the practice borrowed from teams juggling repo docs *and* a separate roadmap/PM tool is: **pick one authoritative artifact per "shape" of roadmap, and make everything else a link, not a copy.**

There are really two different shapes of "roadmap," and conflating them is where teams get roadmap sprawl and duplicate, drifting truth:

- **Delivery roadmap** (near-term, engineering-driven — "what ships next, in what order") — this is what a repo's `ROADMAP.md` is naturally good at, since it lives next to the code and updates alongside it. **Keep this authoritative in the repo.**
- **Strategic/portfolio roadmap** (should this project exist, when does it start, how does it compare in priority to the other 19) — this is what your Obsidian dashboard is for, and GitHub has no way to represent it.

Given that split, the project note's job is just: `roadmap_source: repo` + a `roadmap_link` pointer, plus a computed `roadmap_last_updated` (from the sync job, tracking the file's last-modified date so a stale `ROADMAP.md` is visible without opening it). If a project's delivery roadmap genuinely lives somewhere else (Jira, Trello, Linear) instead of a repo file, `roadmap_source` records that instead — but the rule stays the same: exactly one authoritative place per project for "what ships next," linked from the portfolio, never re-typed into it.

---

## 7. Dependency tracking (round-1 finding #7) — what teams actually do

Worth being honest about this one: even mature teams with paid tooling (Jira + BigPicture/Advanced Link Manager, dedicated Gantt add-ons) don't have a solved version of this. Native issue links in Jira are flat, don't detect cycles, and require opening each issue to understand relationships — the standard complaints track almost exactly what you'd worry about with a hand-maintained `depends_on` field. Nobody's shipping a tool where cross-project dependencies just stay accurate on their own.

The practical pattern teams that manage this reasonably well converge on, and what fits your scale:

1. **Treat a high dependency count as a design smell, not a tracking problem to solve better.** Fewer cross-project dependencies is the actual fix; better visualization is a distant second.
2. **`depends_on` is an advisory pointer, not a scheduler.** It won't auto-update when a dependency clears — that's expected, not a bug to engineer around.
3. **A recurring, scheduled review is the real mechanism**, not automation. Add one Dataview query to the dashboard once you're in Phase 2 — "all projects with a non-empty `depends_on`" — and make checking it a monthly five-minute habit, the same way teams do a periodic dependency-review ritual in Jira-based shops.
4. **Store `depends_on` as real `[[wikilinks]]`** (already reflected in §3's schema) so Obsidian's built-in graph view, filtered to your project notes, gives you a free visual dependency map with zero extra tooling — this is the one piece of "visualization" you get essentially for free that Jira shops have to pay for.

---

## 8. Bases-first phasing (round-1 finding #8) — what you give up short-term

Doing Bases in Phase 0 and Dataview later is a reasonable sequencing decision. Concretely, here's what's *not* available until Dataview lands, and why it's a manageable gap given the rest of the design:

- **No live computed columns or cross-note rollups** in Bases — but this design already puts computation in the sync job (`computed:` block, activity state, confidence rating), not in the view layer, so this mostly doesn't bite you. Bases just displays what the sync job already calculated.
- **No native aggregation** like "% of dependencies shipped" as a live formula — you won't have this until Dataview, and even then it needs care given §7's honesty about dependency staleness.
- **No narrative "state of the portfolio" text** ("3 projects roadmapped for Q4...") — Bases gives you a browsable table/board, not prose; that's exactly the gap Dataview fills in Phase 2.
- **The one thing worth doing now, not later, to avoid rework:** store `depends_on` as real wikilinks from day one (§3, §7). That's a schema decision, not a Bases-vs-Dataview one, and retrofitting plain-string dependency fields into links later is the kind of migration cost worth avoiding upfront.

---

## 9. Round-1 findings → resolutions (summary)

| # | Finding | Resolution |
|---|---|---|
| 1 | Bootstrap sounds more automated than it is | Explicit expectations callout in Step 3/4 and dashboard onboarding note |
| 2 | "This repo sucks" isn't actionable | Concrete missing-signal checklist + confidence tier (§4, Step 3) |
| 3 | Roadmap items have no bootstrap path / ROADMAP.md conflict | Roadmap governance rule: one authoritative artifact per roadmap "shape" (§6) |
| 4 | Sync job could clobber manual edits | Nested `computed:` key, single-key replace, plus Obsidian Git as a recovery safety net (§3, §5.2, §4 Step 6) |
| 5 | No re-entry point for new repos | "Unclaimed repos" queue surfaced directly on the dashboard (§5.4) |
| 6 | Subagent updates risk becoming unstructured prose dumps | Narrow `portfolio-updater` tool: enum stage + capped append-only changelog note, summary/status untouched (§5.1) |
| 7 | Dependency tracking best practices? | Industry-honest answer: minimize deps, treat as advisory, add a recurring manual review ritual, use real wikilinks for free graph visualization (§7) |
| 8 | Bases-only Phase 0 downsides for complex projects | Mostly mitigated since computation already lives in the sync job, not the view; one schema decision (wikilinks) worth doing now (§8) |
| 9 | Does "completed" even apply? | Split into human `status` (shipped/maintained/archived) + computed `activity_state` (active/idle/stale) — no forced auto-reclassification (§5.3) |

---

## 10. Tooling to watch, not yet adopted — Headroom (context compression)

[Headroom](https://headroom-docs.vercel.app/docs) is a context-compression layer (proxy, SDK wrapper, or MCP tool) that compresses tool outputs, logs, JSON/API responses, and file reads before they reach the model — 60–95% token reduction claimed depending on content type, with a reversible store-and-retrieve design (CCR) so compressed content can be pulled back in full if the model asks for it. It's an actively maintained, real open-source project (Apache-2.0), not a toy.

Two features are a plausible fit for this system specifically:

- **SharedContext** — built to compress what moves between agents in a handoff, which maps onto the research → design → dev → test → deploy → support pipeline.
- **Failure Learning** (`headroom learn`) — scans past Claude Code sessions and writes environment/path/command corrections into `CLAUDE.md`/`MEMORY.md`.

**Not adopting it yet, for reasons specific to this system's design:**

1. **It writes into the same `CLAUDE.md` this system treats as single-writer territory.** `headroom learn --apply` auto-populates a marker-delimited block in `CLAUDE.md`/`MEMORY.md` — a second automated writer to a file this proposal has deliberately scoped (§1's judgment/computed/agent-appended split exists precisely to prevent uncoordinated writers). There's a documented precedent of this exact feature overwriting memory files before an upstream fix landed.
2. **Its compression heuristics are tuned for generic logs/API traffic, not this system's schema fidelity needs.** The bootstrap/sync/portfolio-updater pipeline depends on exact GitHub metadata and exact Obsidian API responses — not the kind of content Headroom's statistical retention was designed to summarize safely.
3. **Its own docs rate plain-text/documentation compression as the weakest case** (30–50%, "adds latency, cost savings only") — which is precisely the research subagent's main workload (reading READMEs, ROADMAP.md content) during bootstrap.

**What would make it worth a real pilot:** scoping it narrowly — routed only through the dev/test/support subagents' incidental tool noise (build logs, generic file reads, search results), explicitly excluded from the bootstrap/sync/portfolio-updater pipeline, and with `headroom learn --apply` never run unattended against this system's own `CLAUDE.md` (dry-run and manual diff review only, same as any other automated PR). SharedContext is the single feature worth testing first, independent of the rest.

**Revisit this when:** the project has more track record (it's ~6 months old as of this writing), or when a specific pain point emerges — e.g., a working subagent's context is visibly dominated by noisy tool output rather than curated project content — that a narrowly-scoped pilot could address.

---

## 11. Open questions for the next round

- `portfolio-updater`'s changelog cap is set at 140 characters — too tight, too loose, or fine as a starting point?
- Confidence-signal checklist (§4) — anything specific to your repos (e.g., a Terraform/infra convention, a specific test framework marker) worth adding as its own signal?
- Monthly dependency-review ritual (§7) — worth a scheduled reminder/task somewhere, or is "it's on the dashboard when I look" good enough?
- Ready to pick a pilot set of 3–5 repos and actually run Steps 0–4 against them, or more to refine first?
