"""portfolio-updater: the narrow write-path's guarantees, as tests."""

import datetime as dt
from pathlib import Path

import pytest

from common import frontmatter as fmt
from portfolio_updater import update as upd

TODAY = dt.date(2026, 7, 23)


def make_note(changelog: str = "changelog: []\n", draft: bool = False) -> str:
    draft_line = "_draft: true\n" if draft else ""
    return (
        "---\n"
        f"{draft_line}"
        "project: acme-billing-service\n"
        "status: in-flight            # human-only\n"
        "priority: high\n"
        "summary: >\n"
        "  Human words. Never touched.\n"
        "stage: development            # research | design | development | testing | deployment | support\n"
        f"{changelog}"
        "computed:\n"
        "  last_commit: 2026-07-20\n"
        "---\n"
        "\n## Summary\n\nHuman words. Never touched.\n"
    )


def test_stage_change_touches_one_line_only():
    before = make_note()
    after = upd.apply_update(before, stage="testing", today=TODAY)
    changed = [
        (a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b
    ]
    assert changed == [
        (
            "stage: development            # research | design | development | testing | deployment | support",
            "stage: testing            # research | design | development | testing | deployment | support",
        )
    ]
    assert len(before.splitlines()) == len(after.splitlines())


def test_invalid_stage_rejected():
    with pytest.raises(upd.UpdateError, match="invalid stage"):
        upd.apply_update(make_note(), stage="shipping", today=TODAY)


def test_changelog_append_to_flow_empty():
    after = upd.apply_update(make_note(), changelog_note="QA suite green", today=TODAY)
    assert 'changelog:\n  - { date: 2026-07-23, note: "QA suite green" }\n' in after
    parsed = fmt.parse(fmt.split_note(after)[1])
    assert parsed["changelog"] == [{"date": TODAY, "note": "QA suite green"}]


def test_changelog_append_to_block_list_appends_at_end():
    existing = (
        "changelog:\n"
        '  - { date: 2026-07-20, note: "Deploy subagent shipped v2.3.1" }\n'
    )
    after = upd.apply_update(make_note(existing), changelog_note="Next entry", today=TODAY)
    parsed = fmt.parse(fmt.split_note(after)[1])
    assert [e["note"] for e in parsed["changelog"]] == [
        "Deploy subagent shipped v2.3.1",
        "Next entry",
    ]
    # original entry's bytes untouched:
    assert '  - { date: 2026-07-20, note: "Deploy subagent shipped v2.3.1" }\n' in after


def test_changelog_flow_nonempty_converted_to_block():
    existing = 'changelog: [{ date: 2026-07-01, note: "old" }]\n'
    after = upd.apply_update(make_note(existing), changelog_note="new", today=TODAY)
    parsed = fmt.parse(fmt.split_note(after)[1])
    assert [e["note"] for e in parsed["changelog"]] == ["old", "new"]


def test_changelog_created_after_stage_when_missing():
    note = make_note(changelog="")
    after = upd.apply_update(note, changelog_note="first", today=TODAY)
    fm = fmt.split_note(after)[1]
    stage_span = fmt.key_span(fm, "stage")
    log_span = fmt.key_span(fm, "changelog")
    assert log_span[0] == stage_span[1]


def test_note_cap_140():
    ok = "x" * 140
    too_long = "x" * 141
    upd.apply_update(make_note(), changelog_note=ok, today=TODAY)
    with pytest.raises(upd.UpdateError, match="cap is 140"):
        upd.apply_update(make_note(), changelog_note=too_long, today=TODAY)


def test_quotes_in_note_are_escaped():
    after = upd.apply_update(make_note(), changelog_note='shipped "v2" today', today=TODAY)
    parsed = fmt.parse(fmt.split_note(after)[1])
    assert parsed["changelog"][0]["note"] == 'shipped "v2" today'


def test_draft_notes_refused():
    with pytest.raises(upd.UpdateError, match="draft"):
        upd.apply_update(make_note(draft=True), stage="testing", today=TODAY)


def test_judgment_and_body_bytes_identical():
    before = make_note()
    after = upd.apply_update(before, stage="testing", changelog_note="n", today=TODAY)
    for fragment in [
        "status: in-flight            # human-only\n",
        "priority: high\n",
        "summary: >\n  Human words. Never touched.\n",
        "\n## Summary\n\nHuman words. Never touched.\n",
        "computed:\n  last_commit: 2026-07-20\n",
    ]:
        assert fragment in after


def test_nothing_to_do_rejected():
    with pytest.raises(upd.UpdateError, match="nothing to do"):
        upd.apply_update(make_note(), today=TODAY)


# --- CLI ---------------------------------------------------------------------

def _write_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "acme-billing-service.md").write_text(make_note(), encoding="utf-8")
    return vault


def test_cli_dry_run_writes_nothing(tmp_path, capsys):
    vault = _write_vault(tmp_path)
    before = (vault / "acme-billing-service.md").read_text(encoding="utf-8")
    rc = upd.main(
        ["--vault", str(vault), "--project", "acme-billing-service",
         "--stage", "testing", "--dry-run"]
    )
    assert rc == 0
    assert (vault / "acme-billing-service.md").read_text(encoding="utf-8") == before
    out = capsys.readouterr().out
    assert "-stage: development" in out and "+stage: testing" in out


def test_cli_writes_and_reports(tmp_path, capsys):
    vault = _write_vault(tmp_path)
    rc = upd.main(
        ["--vault", str(vault), "--project", "acme-billing-service",
         "--stage", "testing", "--changelog-note", "integration suite green"]
    )
    assert rc == 0
    text = (vault / "acme-billing-service.md").read_text(encoding="utf-8")
    assert "stage: testing" in text and "integration suite green" in text
    assert "stage -> testing" in capsys.readouterr().out


def test_cli_unknown_project_lists_known(tmp_path, capsys):
    vault = _write_vault(tmp_path)
    rc = upd.main(["--vault", str(vault), "--project", "nope", "--stage", "testing"])
    assert rc == 2
    assert "acme-billing-service" in capsys.readouterr().err
