# Portfolio dashboard — Bases config + setup notes

Phase 0 dashboard (HANDOFF.md §5, Task 5). Bases is a core Obsidian feature
(built in since 1.9.10 — confirm it's on under Settings → Core plugins).
Views are configured through the Obsidian UI — the YAML below is a starting
point to adapt, and a short manual setup pass is expected here.

> **Bootstrap expectation (proposal §4, verbatim by design):** Bootstrap
> produces drafts, not finished notes. The review pass is real work, and its
> length depends entirely on how well-documented your repos already are — a
> repo with a solid README and CONTRIBUTING doc might need 30 seconds of
> review; one with neither could need you to write the summary from scratch.
> Plan for an afternoon the first time, not five minutes.

## View 1 — Portfolio by status

Table/board of all project notes grouped by `status`, showing `priority`,
`target_quarter`, `stage`, and `computed.activity_state`.

## View 2 — Freshness & confidence

Same set, sorted/filtered to surface `computed.activity_state` and
`computed.summary_confidence`. "In-flight but stale" and low-confidence
drafts are what this view exists to catch.

## View 3 — Drafts awaiting review

Filter `_draft = true`, sorted by `computed.summary_confidence` (low first) —
this is the Task 4 review worklist. Views 1 and 2 should filter drafts out.

Starting-point Bases config (adjust in the UI; verify field syntax against
your Obsidian version during Task 5):

```yaml
filters:
  and:
    - project != null
views:
  - type: table
    name: By status
    group_by: status
    order:
      - priority
      - target_quarter
      - stage
      - computed.activity_state
  - type: table
    name: Freshness & confidence
    order:
      - computed.activity_state
      - computed.summary_confidence
      - computed.last_commit
      - status
  - type: table
    name: Drafts awaiting review
    filters:
      and:
        - _draft == true
    order:
      - computed.summary_confidence
```

## Unclaimed repos

Written nightly by `sync/unclaimed_repos.py` (Task 8) — repos found on the
GitHub account but not yet tracked in the vault.

_Nothing yet — sync job not built._

## Add a new project

- **Existing repo:** it will surface under "Unclaimed repos" above — run the
  bootstrap flow for it.
- **No repo yet:** use the `/add-roadmap-project` quick-capture template
  (`templates/roadmap-idea.md`).

## Phase 2 (later — Dataview)

Narrative "state of the portfolio" rollups, plus the monthly
dependency-review query (all projects with a non-empty `depends_on`) —
proposal §7 and §8.
