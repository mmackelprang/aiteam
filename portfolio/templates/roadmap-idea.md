<%*
/* /add-roadmap-project — quick capture for a pre-repo roadmap idea
   (HANDOFF.md §5 Task 8; proposal §5.4). Prompts only for what a human can
   answer in seconds; everything else waits until a repo exists and the full
   bootstrap flow runs. Requires the Templater community plugin.
   No Templater? Copy from the first "---" down and fill the fields by hand. */
const name = await tp.system.prompt("Project name (kebab-case)");
const why = await tp.system.prompt("One-line rationale — why does this matter?");
const quarter = await tp.system.prompt("Rough target quarter (e.g. 2026-Q4)", "");
await tp.file.rename(name);
-%>
---
project: <% name %>
source: personal
status: roadmapped
priority:
target_quarter: <% quarter %>
owner: you
summary: >
  <% why %>
depends_on: []
roadmap_source: portfolio
stage: research
changelog: []
---

## Summary

<% why %>

## Links

_No repo yet — captured via /add-roadmap-project. Run the bootstrap flow once a repo exists._
