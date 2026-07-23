"""Sync engine: single-writer discipline, no-op guard, dashboard markers."""

import datetime as dt
import io
import json
from pathlib import Path

from common import frontmatter as fmt
from common.github_api import FixtureSource
from sync import sync_computed_fields as sync
from sync import unclaimed_repos as unclaimed

TODAY = dt.date(2026, 7, 23)
NOW = dt.datetime(2026, 7, 23, 6, 0, 0)
FIXTURE = str(Path(__file__).resolve().parents[1] / "sync" / "fixture.example.json")

NOTE = """---
project: FamilyWorkspace
source: personal
repo: mmackelprang/FamilyWorkspace
visibility: private

# judgment — human-only
status: in-flight            # roadmapped | planned | in-flight | on-hold
priority: high
target_quarter: 2026-Q3
owner: you
summary: >
  Human-approved paragraph. Sacred.
depends_on: ["[[homelab]]"]
roadmap_source: repo
roadmap_link: "mmackelprang/FamilyWorkspace/ROADMAP.md"

stage: development
changelog: []

computed:
  last_commit: 2020-01-01
  open_issues: 999
  last_synced: 2020-01-01T00:00:00
---

## Summary

Body. Also sacred.
"""


def source():
    return FixtureSource(FIXTURE)


def test_sync_note_rewrites_only_computed():
    facts = source().fetch("mmackelprang/FamilyWorkspace")
    new_text, changed = sync.sync_note_text(NOTE, facts, TODAY, NOW)
    assert changed
    head, fm, tail = fmt.split_note(new_text)
    old_head, old_fm, old_tail = fmt.split_note(NOTE)
    assert head == old_head and tail == old_tail
    # bytes before the computed span identical:
    span_old = fmt.key_span(old_fm, "computed")
    span_new = fmt.key_span(fm, "computed")
    old_lines = old_fm.splitlines(keepends=True)
    new_lines = fm.splitlines(keepends=True)
    assert old_lines[: span_old[0]] == new_lines[: span_new[0]]
    parsed = fmt.parse(fm)["computed"]
    assert parsed["last_commit"] == dt.date(2026, 7, 20)
    assert parsed["open_issues"] == 4
    assert parsed["activity_state"] == "active"
    assert parsed["summary_confidence"] == "medium"  # no CONTRIBUTING, no ARCHITECTURE
    assert parsed["missing_signals"] == ["no CONTRIBUTING.md", "no ARCHITECTURE.md"]
    assert parsed["latest_release"] == "v2.3.1"
    assert fmt.parse(fm)["status"] == "in-flight"


def test_noop_guard_skips_when_only_last_synced_changes():
    facts = source().fetch("mmackelprang/FamilyWorkspace")
    first, changed1 = sync.sync_note_text(NOTE, facts, TODAY, NOW)
    assert changed1
    later = dt.datetime(2026, 7, 24, 6, 0, 0)
    second, changed2 = sync.sync_note_text(first, facts, TODAY, later)
    assert not changed2
    assert second == first  # untouched, timestamp and all (F7)


def test_activity_and_confidence_derivations():
    facts = source().fetch("mmackelprang/RTest")
    computed = sync.build_computed(facts, TODAY, NOW)
    # README last touched 2025-11-01 vs last commit 2026-07-22 -> stale README
    assert computed["missing_signals"] == ["README appears stale"]
    assert computed["summary_confidence"] == "high"
    facts_hl = source().fetch("mmackelprang/homelab")
    computed_hl = sync.build_computed(facts_hl, TODAY, NOW)
    assert computed_hl["activity_state"] == "active"
    assert computed_hl["summary_confidence"] == "low"
    assert "no tests directory detected" in computed_hl["missing_signals"]


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "FamilyWorkspace.md").write_text(NOTE, encoding="utf-8")
    (vault / "roadmap-idea.md").write_text(
        "---\nproject: someday-project\nstatus: roadmapped\n---\nbody\n",
        encoding="utf-8",
    )
    draft = NOTE.replace("---\nproject:", "---\n_draft: true\nproject:", 1).replace(
        "project: FamilyWorkspace", "project: RTest", 1
    ).replace("repo: mmackelprang/FamilyWorkspace", "repo: mmackelprang/RTest", 1)
    (vault / "RTest.md").write_text(draft, encoding="utf-8")
    (vault / "dashboard.md").write_text(
        "# Dashboard\n\nHuman text.\n\n<!-- sync:last-run -->\n_never_\n<!-- /sync:last-run -->\n"
        "\n<!-- sync:unclaimed -->\n_none yet_\n<!-- /sync:unclaimed -->\n",
        encoding="utf-8",
    )
    return vault


def test_run_writes_notes_and_dashboard(tmp_path):
    vault = _make_vault(tmp_path)
    report = sync.run(vault, source(), today=TODAY, now=NOW)
    assert report.checked == 2  # FamilyWorkspace + RTest draft (F8: drafts sync too)
    assert report.updated == 2
    assert report.skipped_no_repo == 1  # roadmap idea has no repo
    assert not report.errors
    fw = (vault / "FamilyWorkspace.md").read_text(encoding="utf-8")
    assert "open_issues: 4" in fw and "Human-approved paragraph. Sacred." in fw
    draft_text = (vault / "RTest.md").read_text(encoding="utf-8")
    assert "_draft: true" in draft_text and "open_issues: 12" in draft_text
    dash = (vault / "dashboard.md").read_text(encoding="utf-8")
    assert "Last sync: 2026-07-23 06:00:00 — 2 checked, 2 updated" in dash
    assert "Human text." in dash


def test_run_second_pass_is_all_noops(tmp_path):
    vault = _make_vault(tmp_path)
    sync.run(vault, source(), today=TODAY, now=NOW)
    before = {p.name: p.read_text(encoding="utf-8") for p in vault.glob("*.md")}
    report = sync.run(vault, source(), today=TODAY, now=dt.datetime(2026, 7, 24, 6, 0))
    assert report.updated == 0 and report.unchanged == 2
    after = {p.name: p.read_text(encoding="utf-8") for p in vault.glob("*.md")}
    # notes byte-identical; dashboard timestamp refreshed is the ONLY change
    for name in before:
        if name == "dashboard.md":
            continue
        assert before[name] == after[name]


def test_run_dry_run_writes_nothing(tmp_path):
    vault = _make_vault(tmp_path)
    before = {p.name: p.read_text(encoding="utf-8") for p in vault.glob("*.md")}
    buf = io.StringIO()
    report = sync.run(vault, source(), today=TODAY, now=NOW, dry_run=True, out=buf)
    assert report.updated == 2
    assert {p.name: p.read_text(encoding="utf-8") for p in vault.glob("*.md")} == before
    assert "+  open_issues: 4" in buf.getvalue()


def test_run_source_error_skips_note_and_flags(tmp_path):
    vault = _make_vault(tmp_path)
    (vault / "ghost.md").write_text(
        "---\nproject: ghost\nrepo: mmackelprang/ghost\nstatus: planned\ncomputed:\n  a: 1\n---\n",
        encoding="utf-8",
    )
    before = (vault / "ghost.md").read_text(encoding="utf-8")
    report = sync.run(vault, source(), today=TODAY, now=NOW)
    assert [p for p, _ in report.errors] == ["ghost"]
    assert (vault / "ghost.md").read_text(encoding="utf-8") == before


def test_cli_exit_codes(tmp_path, capsys):
    vault = _make_vault(tmp_path)
    rc = sync.main(["--vault", str(vault), "--source", f"fixture:{FIXTURE}", "--today", "2026-07-23"])
    assert rc == 0
    assert "checked=2 updated=2" in capsys.readouterr().out


# --- unclaimed repos ---------------------------------------------------------

def test_unclaimed_diff_and_render(tmp_path):
    vault = _make_vault(tmp_path)
    recs = source().list_repos()
    tracked = unclaimed.tracked_repos(vault)
    assert tracked == {"mmackelprang/FamilyWorkspace", "mmackelprang/RTest"}
    un = unclaimed.compute_unclaimed(recs, tracked)
    assert [r.repo for r in un] == ["mmackelprang/homelab"]  # archived excluded
    un_all = unclaimed.compute_unclaimed(recs, tracked, include_archived=True)
    assert {r.repo for r in un_all} == {"mmackelprang/homelab", "mmackelprang/old-experiment"}
    text = unclaimed.render(un)
    assert "`mmackelprang/homelab`" in text and "last push 2026-07-18" in text


def test_unclaimed_cli_updates_dashboard(tmp_path):
    vault = _make_vault(tmp_path)
    rc = unclaimed.main(["--vault", str(vault), "--source", f"fixture:{FIXTURE}"])
    assert rc == 0
    dash = (vault / "dashboard.md").read_text(encoding="utf-8")
    assert "`mmackelprang/homelab`" in dash
    assert "_none yet_" not in dash
    assert "Human text." in dash


def test_fixture_example_is_valid_json():
    data = json.loads(Path(FIXTURE).read_text(encoding="utf-8"))
    assert "repos" in data and len(data["repos"]) >= 3
