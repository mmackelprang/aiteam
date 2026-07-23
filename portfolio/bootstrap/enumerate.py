"""Bootstrap step 1 — enumerate repos.

Pull the repo list for the org and/or personal account via the GitHub MCP
connector (`gh` CLI as fallback): name, description, visibility, language,
last push date, archived flag, fork flag, and whether `ROADMAP.md` exists.
Write raw, human-readable output to `bootstrap/select.md` — no filtering yet
(that is `filter_defaults.py`'s job).

Contract: HANDOFF.md §5, Task 1.
"""

if __name__ == "__main__":
    raise SystemExit("Not implemented yet — scaffold stub. See portfolio/HANDOFF.md §5, Task 1.")
