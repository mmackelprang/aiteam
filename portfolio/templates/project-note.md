<!--
Obsidian template for a bootstrapped project note (HANDOFF.md §2).
`bootstrap/ingest.py` fills the {{placeholders}} and strips this comment.

Field-writer rules (CLAUDE.md hard rule #1):
  judgment (status/priority/target_quarter/summary) -> human-only, set in the Task 4 review pass
  stage / changelog -> portfolio_updater/update.py only
  computed -> sync/sync_computed_fields.py only, rewritten wholesale
`_draft: true` is removed by the human review pass, never by a script.
-->
---
_draft: true
project: {{project}}
source: {{source}}                  # org | personal
repo: {{repo}}                      # blank/omitted if pre-repo (roadmap idea)
visibility: {{visibility}}

# judgment — human-only (drafts leave these unset; set in the Task 4 review pass)
status:
priority:
target_quarter:
owner: you
summary: >
  {{draft_summary}}
depends_on: []                      # real [[wikilinks]] only, e.g. ["[[acme-auth-service]]"]
roadmap_source: {{roadmap_source}}  # repo | portfolio | external-tool | none
roadmap_link: "{{roadmap_link}}"

# agent-appended — via portfolio-updater tool only
stage: {{stage}}                    # research | design | development | testing | deployment | support
changelog: []

# computed — sync job only, rewritten wholesale each run
computed:
  last_commit: {{last_commit}}
  open_issues: {{open_issues}}
  latest_release: {{latest_release}}
  language: {{language}}
  archived_on_github: {{archived_on_github}}
  activity_state: {{activity_state}}          # active (<60d) | idle (60-180d) | stale (>180d)
  summary_confidence: {{summary_confidence}}  # high | medium | low
  missing_signals: {{missing_signals}}
  roadmap_last_updated: {{roadmap_last_updated}}
  last_synced: {{last_synced}}
---

## Summary

{{draft_summary}}

## Links

- Repo: https://github.com/{{repo}}
- Roadmap: {{roadmap_url}}
