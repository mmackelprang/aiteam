"""Bootstrap trio: enumerate cache/worksheet, filter checklist, ingest drafts —
plus the end-to-end drill: ingest → human confirm → update → sync."""

import datetime as dt
import json
from pathlib import Path

from bootstrap import filter_defaults as fd
from bootstrap import ingest
from bootstrap.enumerate import main as enumerate_main
from common import frontmatter as fmt
from common.github_api import FixtureSource
from portfolio_updater import update as upd
from sync import sync_computed_fields as sync

FIXTURE = str(Path(__file__).resolve().parents[1] / "sync" / "fixture.example.json")
TODAY = "2026-07-23"


def test_enumerate_writes_cache_and_worksheet(tmp_path):
    cache = tmp_path / "enumerated.json"
    out = tmp_path / "select.md"
    rc = enumerate_main(
        ["--source", f"fixture:{FIXTURE}", "--cache", str(cache), "--out", str(out)]
    )
    assert rc == 0
    # cache doubles as a FixtureSource input:
    src = FixtureSource(cache)
    assert src.fetch("mmackelprang/RTest").language == "C#"
    text = out.read_text(encoding="utf-8")
    assert "`mmackelprang/old-experiment`" in text and "archived" in text
    assert "| yes |" in text  # ROADMAP column


def test_filter_excludes_and_prechecks(tmp_path):
    cache = tmp_path / "enumerated.json"
    out = tmp_path / "select.md"
    enumerate_main(["--source", f"fixture:{FIXTURE}", "--cache", str(cache), "--out", str(out)])
    rc = fd.main(
        ["--cache", str(cache), "--out", str(out), "--today", TODAY,
         "--check", "RTest", "--check", "homelab", "--check", "FamilyWorkspace"]
    )
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "- [x] `mmackelprang/RTest`" in text
    assert "- [x] `mmackelprang/homelab`" in text
    assert "- [x] `mmackelprang/FamilyWorkspace`" in text
    assert "- `mmackelprang/old-experiment` — archived, no push in 2+ years" in text


def test_filter_preserves_human_checkbox_state(tmp_path):
    cache = tmp_path / "enumerated.json"
    out = tmp_path / "select.md"
    enumerate_main(["--source", f"fixture:{FIXTURE}", "--cache", str(cache), "--out", str(out)])
    fd.main(["--cache", str(cache), "--out", str(out), "--today", TODAY,
             "--check", "RTest", "--check", "homelab"])
    # human unticks homelab by hand:
    text = out.read_text(encoding="utf-8").replace(
        "- [x] `mmackelprang/homelab`", "- [ ] `mmackelprang/homelab`"
    )
    out.write_text(text, encoding="utf-8")
    fd.main(["--cache", str(cache), "--out", str(out), "--today", TODAY])
    text2 = out.read_text(encoding="utf-8")
    assert "- [x] `mmackelprang/RTest`" in text2
    assert "- [ ] `mmackelprang/homelab`" in text2


def test_ingest_renders_valid_drafts(tmp_path):
    vault = tmp_path / "vault"
    rc = ingest.main(
        ["--vault", str(vault), "--source", f"fixture:{FIXTURE}", "--today", TODAY,
         "--personal-owner", "mmackelprang",
         "--repos", "mmackelprang/FamilyWorkspace", "mmackelprang/homelab"]
    )
    assert rc == 0
    note = (vault / "FamilyWorkspace.md").read_text(encoding="utf-8")
    _, fm, _ = fmt.split_note(note)
    parsed = fmt.parse(fm)
    assert parsed["_draft"] is True
    assert parsed["project"] == "FamilyWorkspace"
    assert parsed["source"] == "personal"
    assert parsed["status"] is None and parsed["priority"] is None  # judgment left blank
    assert parsed["stage"] == "development"
    assert parsed["roadmap_source"] == "repo"
    assert parsed["computed"]["open_issues"] == 4
    assert parsed["computed"]["summary_confidence"] == "medium"
    assert "Family workspace app stack" in note
    hl = fmt.parse(fmt.split_note((vault / "homelab.md").read_text(encoding="utf-8"))[1])
    assert hl["computed"]["summary_confidence"] == "low"
    assert hl["roadmap_source"] == "none"


def test_ingest_overwrite_policy(tmp_path):
    vault = tmp_path / "vault"
    args = ["--vault", str(vault), "--source", f"fixture:{FIXTURE}", "--today", TODAY,
            "--repos", "mmackelprang/FamilyWorkspace"]
    ingest.main(args)
    # second run without --force skips the draft (exit 0, unchanged):
    before = (vault / "FamilyWorkspace.md").read_text(encoding="utf-8")
    assert ingest.main(args) == 0
    assert (vault / "FamilyWorkspace.md").read_text(encoding="utf-8") == before
    # --force rewrites a draft:
    assert ingest.main(args + ["--force"]) == 0
    # human confirms the note (removes _draft) -> bootstrap refuses even --force:
    confirmed = before.replace("_draft: true\n", "").replace(
        "status:\n", "status: in-flight\n"
    )
    (vault / "FamilyWorkspace.md").write_text(confirmed, encoding="utf-8")
    assert ingest.main(args + ["--force"]) == 0
    assert (vault / "FamilyWorkspace.md").read_text(encoding="utf-8") == confirmed


def test_end_to_end_ingest_confirm_update_sync(tmp_path):
    """The Phase 0 drill, fully offline: draft → human review → agent update
    → nightly sync — with the note's human territory intact throughout."""
    vault = tmp_path / "vault"
    ingest.main(
        ["--vault", str(vault), "--source", f"fixture:{FIXTURE}", "--today", TODAY,
         "--repos", "mmackelprang/FamilyWorkspace"]
    )
    path = vault / "FamilyWorkspace.md"

    # updater refuses drafts:
    rc = upd.main(["--vault", str(vault), "--project", "FamilyWorkspace", "--stage", "testing"])
    assert rc == 2

    # "human review pass": set judgment fields, drop the marker
    text = path.read_text(encoding="utf-8")
    text = text.replace("_draft: true\n", "")
    text = text.replace("status:\n", "status: in-flight\n")
    text = text.replace("priority:\n", "priority: high\n")
    text = text.replace("target_quarter:\n", "target_quarter: 2026-Q3\n")
    path.write_text(text, encoding="utf-8")

    # agent updates via the narrow tool:
    rc = upd.main(["--vault", str(vault), "--project", "FamilyWorkspace",
                   "--stage", "testing", "--changelog-note", "pilot dry-run"])
    assert rc == 0

    # nightly sync leaves judgment + changelog + stage alone:
    report = sync.run(vault, FixtureSource(FIXTURE), today=dt.date(2026, 7, 23),
                      now=dt.datetime(2026, 7, 23, 6, 0))
    assert not report.errors
    final = path.read_text(encoding="utf-8")
    parsed = fmt.parse(fmt.split_note(final)[1])
    assert parsed["status"] == "in-flight"
    assert parsed["priority"] == "high"
    assert parsed["stage"] == "testing"
    assert parsed["changelog"][0]["note"] == "pilot dry-run"
    assert parsed["computed"]["open_issues"] == 4
