# Tier-0 permission presets — per role (D4 / plan F10)

**What these are.** Tier 0 ("no `dangerouslySkipPermissions`, all actions
gated") is operationalized as a **curated minimal allowlist per role**,
because an interactive permission prompt with nobody watching just parks an
unattended agent. Each `tier0-<role>.settings.json` is a drop-in
`.claude/settings.json` for that role's worktree on the appserver
(engineer/qa/release get worktrees of the pilot repo; the others run
without a code cwd).

**The overflow rule.** Anything outside the allowlist is NOT silently
retried or worked around: the role's prompt instructs the agent to call
`tools/raise_for_review.py` describing what it needed and why (hard rule
#1 — that's the flag-for-review path). The `deny` list additionally hard-
blocks operations Tier 0 must never do even with a human watching
(push/deploy/destructive/network-egress).

**Tier changes are Board-granted only** (hard rule #2). Tier 1/2 become
additional preset files here when first granted — versioned, diffable,
revertible — and the grant is recorded per project+role in
`../trust_tiers/`.

**⚠ Reconcile at Stage 5:** permission-rule syntax evolves with Claude
Code releases, and the build/test commands are per-repo (these presets
assume the FamilyWorkspace pilot — Python + Node). Validate each file
against the Claude Code version installed on the appserver before first
run, and tune the command lists to the pilot repo (D2).

| Preset | Beyond the common read-only base |
|---|---|
| `tier0-project-lead` | run the harness tools (raise_for_review, team_status pause) + portfolio-updater |
| `tier0-research` | web search/fetch |
| `tier0-design` | (base only) |
| `tier0-engineer` | edit/write files, local git (add/commit/checkout — never push), build + test commands |
| `tier0-qa` | edit/write (tests are code), test commands |
| `tier0-release` | build commands only — releases/deploys are proposed via review at Tier 0, never executed |
| `tier0-support` | (base only) |

Common base (in every file): `Read`, `Glob`, `Grep`, and read-only git
(`status`, `log`, `diff`, `show`, `branch`). Common denies:
`git push`, `sudo`, `rm`, `docker`, `ssh`, `curl`, `wget`.
