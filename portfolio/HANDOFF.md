# Handoff: Project Portfolio System — Kickoff Brief for Claude Code

> **Repo note (2026-07-23):** this system lives in the `portfolio/` subtree of the `aiteam` repo, alongside its companion system in `../harness/`. Both systems were originally designed as two separate repos; they share this one starting repo, one self-contained subtree each, so a later split stays trivial. All paths in this doc are relative to `portfolio/`.

**How to use this doc:** paste/drop this file into a new, blank repo and open Claude Code in that directory. This file is written to be self-contained — it does not assume Claude Code has any other context from prior conversations. Start the session with something like: *"Read HANDOFF.md and start on Phase 0, Task 1."*

**Companion system:** the [Agentic Team Harness](../harness/HANDOFF-agentic-harness.md) runs per-project AI teams that report status/cost up into this repo's sync job. That repo's cost-rollup and team-status features extend *this* repo's `sync/sync_computed_fields.py` — see its §5 cross-repo note. Not required to build this repo; relevant if a session here is asked to add Paperclip as a data source later.

---

## 0. What this system is (context, in case you're a fresh session)

A thin tracking/documentation layer sitting above ~20 existing GitHub repos (org and/or personal). GitHub stays the source of truth for all project detail (README, ADRs, ROADMAP.md, issues). This system adds:

- One lightweight **project note per repo** in an Obsidian vault — status, priority, target quarter, links out to GitHub — never a copy of the repo's actual documentation.
- A **portfolio dashboard** rolling all project notes into one view (grouped by status, flagged by activity/freshness).
- A repeatable **bootstrap flow** to pull in existing repos, draft summaries, and let a human confirm what only a human can judge (status, priority, timing).
- A narrow, structured way for **working agents** (research/design/dev/test/deploy/support subagents) to update status/stage without producing unreviewed prose dumps.

Full rationale and the review process that shaped these decisions live in `docs/proposal.md` (copy your proposal doc into this repo before starting — see Task 0 below). This handoff doc is the actionable subset; the proposal doc is the "why."

---

## 1. Non-negotiable design constraints

These came out of an adversarial review round and should not be re-litigated without discussion — build to them:

1. **Three field categories, three different writers, never mixed:**
   - *Judgment* (`status`, `priority`, `target_quarter`, `summary`) — human-edited only, in Obsidian directly. No script or agent ever writes these.
   - *Computed* (nested under a single `computed:` frontmatter key) — owned entirely by the nightly sync job. Rewritten wholesale on every run. Never hand-edited.
   - *Agent-appended* (`stage`, `changelog`) — written only through the narrow `portfolio-updater` tool (see §5), never through free-form note edits by an agent.
2. **The sync job touches only the `computed:` key.** Parse → replace that one key → serialize. This is the fix for the "sync clobbers manual edits" risk — treat it as a hard requirement of the sync script's implementation, not a nice-to-have.
3. **`depends_on` is stored as real `[[wikilinks]]`**, not plain strings — this gives a free dependency graph via Obsidian's native graph view. Do this from the first note created, not retrofitted later.
4. **`ROADMAP.md` in a repo stays authoritative for delivery-level roadmap.** The project note only stores a `roadmap_source` + `roadmap_link` pointer and a computed staleness date — never a copy of roadmap content.
5. **Bootstrap produces drafts, not finished notes.** Never silently auto-finalize `status`/`priority`/`target_quarter` — always require the human review pass (Phase 0, Task 4).
6. **Enable the Obsidian Git plugin on the vault before running anything that writes to it.** This is the recovery safety net if anything ever goes wrong with #2.

---

## 2. Schema — full spec

Every project note is a single markdown file with this frontmatter shape:

```yaml
---
project: acme-billing-service
source: org                 # org | personal
repo: acme-inc/acme-billing-service     # blank/omitted if pre-repo (roadmap idea)
visibility: private

# judgment — human-only
status: in-flight            # roadmapped | planned | in-flight | on-hold | shipped | maintained | archived
priority: high                # high | medium | low
target_quarter: 2026-Q3
owner: you
summary: >
  One paragraph, human-approved, on what this is and why it matters.
depends_on: ["[[acme-auth-service]]"]
roadmap_source: repo          # repo | portfolio | external-tool | none
roadmap_link: "acme-inc/acme-billing-service/ROADMAP.md"

# agent-appended — via portfolio-updater tool only
stage: development            # research | design | development | testing | deployment | support
changelog:
  - { date: 2026-07-20, note: "Deploy subagent shipped v2.3.1 to staging" }

# computed — sync job only, rewritten wholesale each run
computed:
  last_commit: 2026-07-20
  open_issues: 4
  latest_release: v2.3.1
  language: TypeScript
  archived_on_github: false
  activity_state: active       # active (<60d) | idle (60-180d) | stale (>180d), derived from last_commit
  summary_confidence: medium   # high | medium | low — see §4 signal table
  missing_signals: ["no CONTRIBUTING.md", "no tests directory detected"]
  roadmap_last_updated: 2026-06-01
  last_synced: 2026-07-22T06:00:00
---

## Summary
(same content as frontmatter `summary`, written out in full for readability in Obsidian's editor view)

## Links
- Repo: https://github.com/acme-inc/acme-billing-service
- Roadmap: https://github.com/acme-inc/acme-billing-service/blob/main/ROADMAP.md
```

**Confidence signal table** (drives `summary_confidence` and `missing_signals`):

| Signal checked | If missing, record |
|---|---|
| README present | `no README` |
| README updated within ~1 release/commit-era of latest code | `README appears stale` |
| CONTRIBUTING.md present | `no CONTRIBUTING.md` |
| ARCHITECTURE.md (or equivalent doc) present | `no ARCHITECTURE.md` |
| Commits in last 90 days | `no recent commit activity` |
| Tests directory detected | `no tests directory detected` |
| CI config present (`.github/workflows/*`, etc.) | `no CI config detected` |
| Releases/tags present | `no releases tagged` |

Scoring: 0–1 missing → `high` confidence, 2–3 → `medium`, 4+ → `low`.

---

## 3. Repo structure to scaffold

```
/ (this repo)
├── HANDOFF.md                  (this file)
├── docs/
│   └── proposal.md             (paste the full proposal doc here before starting)
├── bootstrap/
│   ├── enumerate.py             # Step 1: pull repo lists from GitHub (org + personal)
│   ├── filter_defaults.py       # Step 2: apply default excludes (archived/forks/2yr-stale)
│   ├── ingest.py                # Step 3: signal check + confidence scoring + draft note generation
│   └── select.md                # notes/output: the human-reviewable selection + draft list
├── sync/
│   ├── sync_computed_fields.py  # nightly job: rewrites only the `computed:` key per note
│   └── unclaimed_repos.py       # diffs GitHub account repo list vs vault notes -> dashboard queue
├── portfolio_updater/
│   └── update.py                # the narrow tool: enum `stage` + ≤140-char changelog append only
├── templates/
│   ├── project-note.md          # Obsidian template for a bootstrapped project
│   ├── roadmap-idea.md          # Obsidian template for a pre-repo roadmap item (/add-roadmap-project)
│   └── dashboard.md             # Bases view config + (later) Dataview queries
├── vault-config/
│   └── README.md                # instructions for pointing Obsidian at the vault + which plugins to enable
└── CLAUDE.md                    # project memory for future Claude Code sessions on this repo
```

---

## 4. Installation — tooling checklist

Work through this before/alongside Phase 0. Note your OS where it matters (macOS/Linux/Windows) — commands below assume macOS/Linux; note Windows variants where given.

### 4.1 Obsidian (the vault)

1. Download and install Obsidian: https://obsidian.md (available macOS/Windows/Linux).
2. Create or open the vault you want to use for this system (recommend a dedicated vault, stored on the NAS path you sync to your dev machine).
3. Enable **Community plugins**: Settings → Community plugins → turn on.
4. Install these community plugins (Settings → Community plugins → Browse):
   - **Local REST API** (by coddingtonbear) — required for MCP access. After installing, enable it, and copy the generated API key (Settings → Local REST API) — you'll need it below.
   - **Obsidian Git** — auto-commits vault changes; this is the recovery safety net from constraint #6.
   - **Dataview** — not needed for Phase 0, but install now so Phase 2 doesn't need a second round of setup.
   - **Templater** (optional but recommended) — powers the `/add-roadmap-project` quick-capture template.
5. Enable **Bases** — this is a core Obsidian feature (built in since 1.9.10), no plugin install needed; just confirm it's on under Settings → Core plugins.

### 4.2 Node.js and Python

- **Node.js** (v18+): needed for `npx`/`uvx`-based MCP servers. Install via https://nodejs.org or your package manager (`brew install node` / `apt install nodejs npm`).
- **Python** (3.10+) with `pip`: needed for the bootstrap/sync/portfolio-updater scripts. Install via your package manager or https://python.org.
- **uv/uvx** (used to launch the Obsidian MCP server): `curl -LsSf https://astral.sh/uv/install.sh | sh` (macOS/Linux) or see https://docs.astral.sh/uv/getting-started/installation/ for Windows.

### 4.3 GitHub access (for the GitHub MCP connector)

1. Generate a GitHub Personal Access Token with read access to the repos you'll be tracking (org + personal, as needed). GitHub → Settings → Developer settings → Personal access tokens.
2. Register the official GitHub MCP server with Claude Code:
   ```
   claude mcp add --transport http github https://api.githubcopilot.com/mcp -H "Authorization: Bearer YOUR_GITHUB_PAT"
   ```
3. Verify: `claude mcp list` should show `github` connected.

### 4.4 Obsidian MCP connector (for Claude Code to read/write vault notes)

1. With the Local REST API plugin installed and enabled (§4.1), note the API key it generated and the port it's running on (default `127.0.0.1:27124`, HTTPS with a self-signed cert).
2. Register the Obsidian MCP server:
   ```
   claude mcp add obsidian uvx mcp-obsidian -e OBSIDIAN_API_KEY=your-key-here
   ```
3. Verify: `claude mcp list` should show `obsidian` connected. If it fails to connect, confirm Obsidian is running (the REST API only serves while the app is open) and that the port isn't blocked by a firewall.

### 4.5 Appserver setup (for the nightly sync job)

1. Confirm Docker (or your container runtime of choice) is installed and running on the appserver.
2. Build a small container image for `sync/sync_computed_fields.py` and `sync/unclaimed_repos.py` (Task list below covers the script content; containerizing is a later Phase 0 task once the scripts exist and are tested locally).
3. Schedule it as a systemd timer or cron job, nightly, e.g.:
   ```
   # /etc/systemd/system/portfolio-sync.timer
   [Timer]
   OnCalendar=daily
   Persistent=true
   ```
   (or a crontab entry: `0 6 * * * docker run --rm portfolio-sync:latest`)
4. The container needs: the GitHub PAT (as an env var, not committed), the vault's Local REST API key and reachable address (if the appserver can reach your dev machine/NAS — otherwise run the sync job on the dev machine instead, which is simpler for a v1 and worth doing first).

### 4.6 Secrets

Do not commit any of these. Use a `.env` file (gitignored) or your secret manager of choice:
```
GITHUB_TOKEN=...
OBSIDIAN_API_KEY=...
OBSIDIAN_VAULT_PATH=/path/to/vault    # if a filesystem-based fallback is ever needed
```

---

## 5. Phase 0 task list (pilot — 3 to 5 repos)

Work these roughly in order. Stop and confirm with the user before Task 4 (the human review pass is explicitly theirs, not something to auto-approve) and before Task 8 (rolling out beyond the pilot set).

**Task 0 — Scaffold.** Create the repo structure in §3. Copy the full proposal document into `docs/proposal.md`. Write an initial `CLAUDE.md` for this repo capturing the constraints in §1 so future sessions don't need this whole handoff re-read.

**Task 1 — `bootstrap/enumerate.py`.** Using the GitHub MCP connector, pull the repo list for the org and/or personal account: name, description, visibility, language, last push date, archived flag, fork flag, whether `ROADMAP.md` exists. Write raw output to `bootstrap/select.md` for now (human-readable, not yet filtered).

**Task 2 — `bootstrap/filter_defaults.py`.** Apply default excludes: archived, forks, zero commits in 2+ years. Present the remainder in `bootstrap/select.md` as a checklist for the user to mark include/exclude. **Confirm the pilot set of 3–5 with the user here before continuing.**

**Task 3 — `bootstrap/ingest.py`.** For each selected repo: run the signal checks from §2's confidence table, compute `summary_confidence` and `missing_signals`, and draft a project note (using `templates/project-note.md`) with a best-effort `summary` paragraph and inferred `stage`. Flag every draft clearly as unreviewed (e.g. a `_draft: true` marker, removed in Task 4).

**Task 4 — Human review pass.** Present drafts sorted by `summary_confidence` (low first). For each: user confirms/edits `summary`, sets `status`, `priority`, `target_quarter`. Remove the `_draft` marker once confirmed. **This step is manual by design — do not skip or auto-fill judgment fields.**

**Task 5 — Write notes + build the Phase 0 dashboard.** Write confirmed notes into the vault. Build a Bases view grouped by `status`, another (or the same, filtered) surfacing `activity_state` and `summary_confidence`. Bases config lives in `templates/dashboard.md` alongside setup instructions (Bases views are configured through the Obsidian UI — script what you can, but expect a short manual setup pass here).

**Task 6 — `sync/sync_computed_fields.py`.** Nightly job logic: for each project note with a `repo` set, hit the GitHub API, rebuild the `computed:` block (including `activity_state` from `last_commit` thresholds — 60/180 days), and replace only that key in the note's frontmatter. Test this thoroughly against a throwaway note before pointing it at real ones — verify a manually-edited `status` survives a sync run untouched.

**Task 7 — `portfolio_updater/update.py`.** Implement the narrow tool: accepts `project`, optional `stage` (enum only), optional `changelog_note` (≤140 chars, appended with a timestamp). Explicitly does not accept or touch `summary` or `status`. This is the only way agents should ever modify a project note going forward — document this clearly in `CLAUDE.md` so future subagent definitions call this tool rather than editing notes directly.

**Task 8 — Unclaimed-repos + roadmap-idea entry points.** Implement `sync/unclaimed_repos.py` (diffs GitHub account repos vs. tracked notes, writes a list to the dashboard). Build the `templates/roadmap-idea.md` Templater template for pre-repo ideas (`status: roadmapped`, no `repo` field, minimal prompted fields).

**Task 9 — Wrap-up.** Confirm with the user: does the pilot behave as expected end-to-end (bootstrap → review → dashboard → a simulated sync run → a simulated portfolio-updater call)? Only after this confirmation, discuss rolling out to the remaining ~15 repos.

---

## 6. Acceptance criteria for Phase 0

- 3–5 real project notes exist in the vault, judgment fields set by the human reviewer, computed fields populated by a real (not simulated) sync run.
- Re-running the sync job a second time changes only the `computed:` key — a manually-set `status` is provably untouched (show a before/after diff).
- The Bases dashboard shows all pilot projects grouped by status, with `activity_state` and `summary_confidence` visible.
- At least one `depends_on` relationship exists as a real wikilink and shows up in Obsidian's graph view.
- The `portfolio-updater` tool successfully appends a changelog entry and sets `stage` on a note without altering `summary` or `status`.
- The "unclaimed repos" list correctly surfaces at least one real repo not yet in the pilot set.

---

## 6.5 Tooling explicitly not in scope for Phase 0

**Headroom** (context-compression proxy/MCP tool, see `docs/proposal.md` §10) is a documented watch-list candidate, not an approved dependency. Do not add it to `claude mcp add`, wrap any script's model calls with it, or run `headroom learn --apply` against this repo's `CLAUDE.md`, unless the user explicitly asks for that pilot in a given session. If asked to "speed up" or "reduce token use" in a way that seems to call for a compression layer, surface Headroom as an option and cite §10's scoping caveats rather than integrating it directly.

## 7. Open questions to raise with the user during this build (don't guess silently on these)

- Where exactly should the sync job run for Phase 0 — dev machine (simpler, start here) or appserver (Phase 1+)?
- `portfolio-updater`'s 140-character changelog cap — keep, or adjust once real usage shows it's too tight/loose?
- Any repo-specific confidence signals worth adding (e.g., an infra/Terraform convention, a specific test framework marker) beyond the default table in §2?
- Confirm the pilot's 3–5 repos before Task 3 actually runs ingestion against them.
