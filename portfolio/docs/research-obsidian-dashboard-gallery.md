# Research — InlitX/Obsidian-Dashboard-Gallery: applicable patterns for the portfolio dashboard

**Date:** 2026-08-08 · **Status:** research only — nothing adopted yet; decision tracked as plan D11 (finding F20 in `../../docs/implementation-plan.md`)
**Source:** https://github.com/InlitX/Obsidian-Dashboard-Gallery (MIT license, ~536 stars at time of reading)

## TL;DR

The gallery is four polished "home page" dashboards for Obsidian (Atlas, Zen, Brutalist, Komorebi), each implemented as a single large DataviewJS block in a markdown note plus a paired CSS snippet. It targets personal PKM homepages, not project portfolios, so nothing is adoptable wholesale — but it is a useful pattern library for this system's **Phase 2 Dataview dashboard**, and its packaging pattern (dashboard note + CSS snippet as versioned artifacts copied into the vault) is worth adopting as early as the Bases-era bootstrap. It also validates, by counter-example, the design decision to keep computation in the sync job rather than the view layer (proposal §8).

## What the repo is

- Four dashboards under `dashboards/` (`Dashboard-Atlas.md`, `-Zen.md`, `-Brutalist.md`, `-Komorebi.md`), each pairing with a CSS snippet of the same name under `.obsidian/snippets/`.
- Each dashboard note carries `cssclasses` frontmatter and one ~400-line `dataviewjs` code block that builds the entire UI via `dv.container.createDiv()` — no HTML files, no plugin beyond Dataview (with **JavaScript queries enabled**; QuickAdd optional in one).
- Install model: "copy the .md and the .css into your vault." Docs in four languages; PRs welcome; MIT.
- Widget inventory across the four: time-based greeting, stat tiles ("stat cubes") with progress bars, tag-pill filtering with client-side re-render, recently-edited list, "jump back in" (workspace recent files), pinned notes (Bookmarks plugin), "on this day" (ctime match), 18-week activity heatmap (from note `mtime`), daily-note calendar, focus timer, scratchpad, habit tracker, task pipeline over `dv.pages().file.tasks`, quick capture appending to an inbox note, random-note "serendipity" card, weather/clock (OpenWeatherMap key pasted into the note).
- State model: all user preference and widget state lives in `localStorage` (accent color, active tag filter, banner text, habits); customization is modal-driven; theming via CSS custom properties with an Obsidian-theme-following fallback.

## Patterns worth taking

### 1. Packaging: the dashboard as a versioned, deployed artifact *(adoptable pre-Phase-2)*

The gallery treats a dashboard as a repo-versioned artifact **deployed into the vault** — markdown note + paired CSS snippet, copied in at install time. That maps directly onto our bootstrap flow: keep the portfolio dashboard note (and an optional CSS snippet) as templates inside `portfolio/`, have bootstrap (P-Task 5) copy them into the vault, and let `vault.git` (hard rule #6) track drift. The dashboard becomes reproducible instead of hand-built once in Obsidian. Zero architectural cost; applies to the Bases-era dashboard note just as well as the Phase 2 Dataview one.

### 2. Client-side pill filtering (Atlas)

Tag pills that filter and re-render a note list without touching any data; filter state persisted in `localStorage`. Portfolio equivalent: `status` / `stage` / `priority` / `activity_state` pills on the Phase 2 dashboard filtering the project table client-side. Fully compatible with the three-writer model — the view writes nothing into notes, and `localStorage` is exactly the right (and wrong-to-sync) home for view preference: per-device, cosmetic, never canonical.

### 3. Stat tiles + conditional rendering

Zen's header stat cubes (counts computed once, rendered as tiles with progress bars) are a ready skeleton for the "state of the portfolio" numbers the proposal defers to Phase 2 — total tracked, in-flight, `stale`-and-not-`archived`, low-confidence summaries. Atlas's render-only-when-non-empty habit is exactly right for the "Unclaimed repos" queue: an empty queue should be invisible, not an empty section.

### 4. "Serendipity" → a retirement-review nudge

Zen surfaces one random vault note per load. Adapted here: a small card spotlighting one rotating project that is `stale` and not `archived` — a passive prompt for the retirement question (proposal round-1 finding #9), lighter-weight than and complementary to the monthly dependency-review ritual.

### 5. Small robustness idioms (MIT — copy freely, with attribution)

- `setIcon` wrapped in try/catch with a text fallback.
- `window.moment` if present, `Date.toLocaleString()` otherwise.
- A single unified modal helper (text / grid / suggest input types) instead of ad-hoc dialogs.

## What it teaches by counter-example

### The heatmap is the sharpest lesson

Atlas builds its activity heatmap from note `mtime` — reasonable in a PKM vault, **actively misleading in ours**: the nightly sync rewrites every note's `computed:` block, so every note's `mtime` would read "last sync run." A portfolio heatmap must be driven by `computed.last_commit` / commit-activity data the sync job writes — never file metadata. More broadly, the gallery computes everything in the view layer at render time (tag counts, stats, heatmaps); our design deliberately moved computation into the sync job so Bases/Dataview only *display* (proposal §8). The gallery is what the view-layer-computation alternative looks like: fine for one personal vault, unauditable and duplicated for this setup. Take its presentation and interaction ideas; leave its data-flow architecture.

### Dashboard-initiated writes

Atlas's quick-capture appends to an inbox note via `app.vault.create()`/append. Even targeting only an inbox, a dashboard with vault write access is a **fourth writer** the three-writer model doesn't have. Keep it out — capture belongs in `bin/new-project` and the updater, not the view.

### Injection caution for a future DataviewJS dashboard

The sync job writes the "Unclaimed repos" list into the dashboard between markers. If the Phase 2 dashboard becomes a DataviewJS note, those markers must stay in a plain-markdown region **outside any code fence** — sync-written text landing inside a `dataviewjs` block would be content injection into executed JavaScript. One line for the Phase 2 spec.

### Maintainability of the monolith

A single ~400-line `dataviewjs` block inside a vault note is hard to review and version. If we build one, prefer keeping the JS in the repo and deploying it via the pattern in §1 (or `dv.view()` loading from a vault file), so changes go through git review rather than in-app edits.

### Not applicable

Weather/clock widgets (an OpenWeatherMap key pasted into a note also violates the secrets convention), habit tracking, task pipelines over vault checkboxes, QuickAdd. The gallery ignores Bases entirely — it neither supports nor undermines the Bases-first Phase 0 sequencing.

## Where this slots in

| Item | Earliest slot | Notes |
|---|---|---|
| §1 packaging (dashboard + CSS as bootstrap-deployed templates) | Stage 2 (P-Task 5) | Works for the Bases dashboard note today |
| §3 conditional rendering for "Unclaimed repos" | Stage 3 (P-Task 8) | Presentation detail of the existing queue |
| §2 pill filtering, §3 stat tiles, §4 stale-project spotlight | Phase 2 (Dataview dashboard) | All read-only over `computed:` fields |
| Injection caution (§ counter-examples) | Phase 2 spec | Markers stay outside code fences |

Adopt/review/defer is a user call — tracked as **D11** in the implementation plan. Nothing here is load-bearing for Phase 0 acceptance.
