"""The F6 acceptance criterion, as executable tests: every byte outside the
spliced key's span survives, including comments, quoting, and blank lines."""

import datetime as dt

import pytest
import yaml

from common import frontmatter as fmt

GNARLY = """---
project: acme-billing-service
source: org                 # org | personal
repo: "acme-inc/acme-billing-service"
visibility: private

# judgment — human-only (weird spacing kept   on purpose)
status: in-flight            # roadmapped | planned | in-flight | on-hold
priority:   high
target_quarter: 2026-Q3
owner: you
summary: >
  Curated paragraph with unicode — émojis 🚀, a colon: and a #hash that is
  part of the text, not a comment.
depends_on: ["[[acme-auth-service]]", "[[weird #name]]"]
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
  activity_state: active
  summary_confidence: medium
  missing_signals: ["no CONTRIBUTING.md"]
  roadmap_last_updated: 2026-06-01
  last_synced: 2026-07-22T06:00:00
---

## Summary

Body text stays body text — including a stray `---` in prose?

---

That horizontal rule above must never be mistaken for a fence.
"""


def test_split_join_identity():
    head, fm, tail = fmt.split_note(GNARLY)
    assert fmt.join_note(head, fm, tail) == GNARLY
    assert head == "---\n"
    assert tail.startswith("---\n\n## Summary")


def test_split_bom_preserved():
    text = "﻿" + GNARLY
    head, fm, tail = fmt.split_note(text)
    assert head.startswith("﻿")
    assert fmt.join_note(head, fm, tail) == text


def test_split_rejects_fenceless():
    with pytest.raises(fmt.FrontmatterError):
        fmt.split_note("# just a doc\n")
    with pytest.raises(fmt.FrontmatterError):
        fmt.split_note("---\nnever: closed\n")


def test_key_span_shapes():
    _, fm, _ = fmt.split_note(GNARLY)
    lines = fm.splitlines(keepends=True)
    s, e = fmt.key_span(fm, "stage")
    assert e - s == 1 and lines[s].startswith("stage: development")
    s, e = fmt.key_span(fm, "changelog")
    assert e - s == 2  # key line + one item; the section comment below is NOT included
    s, e = fmt.key_span(fm, "summary")
    assert e - s == 3  # folded scalar continuation lines belong to the block
    s, e = fmt.key_span(fm, "computed")
    assert lines[s] == "computed:\n" and e == len(lines)
    assert fmt.key_span(fm, "nonexistent") is None


def test_replace_computed_touches_only_computed_bytes():
    head, fm, tail = fmt.split_note(GNARLY)
    span = fmt.key_span(fm, "computed")
    lines = fm.splitlines(keepends=True)
    prefix = "".join(lines[: span[0]])

    new_block = fmt.emit_mapping_block(
        "computed",
        {
            "last_commit": dt.date(2026, 7, 23),
            "open_issues": 7,
            "latest_release": None,
            "language": "TypeScript",
            "archived_on_github": False,
            "activity_state": "active",
            "summary_confidence": "high",
            "missing_signals": [],
            "roadmap_last_updated": None,
            "last_synced": dt.datetime(2026, 7, 23, 6, 0, 0),
        },
    )
    new_fm = fmt.replace_key_block(fm, "computed", new_block)

    # Byte-identity outside the span (F6's strengthened acceptance criterion):
    assert new_fm.startswith(prefix)
    assert new_fm[len(prefix):] == new_block
    # Judgment fields still parse identically:
    fmt.verify_untouched(fm, new_fm, {"computed"})
    # And the result is valid YAML with the new values:
    parsed = fmt.parse(new_fm)
    assert parsed["computed"]["open_issues"] == 7
    assert parsed["computed"]["latest_release"] is None
    assert parsed["status"] == "in-flight"


def test_replace_preserves_gap_blank_lines():
    fm = "a: 1\n\nb:\n  - x\n\n\nc: 3\n"
    out = fmt.replace_key_block(fm, "b", "b: [y]\n")
    assert out == "a: 1\n\nb: [y]\n\n\nc: 3\n"


def test_insert_block_after():
    fm = "a: 1\nb: 2\nc: 3\n"
    out = fmt.insert_block_after(fm, "b", "new:\n  - 1\n")
    assert out == "a: 1\nb: 2\nnew:\n  - 1\nc: 3\n"
    out2 = fmt.insert_block_after(fm, "zzz", "tail: 9\n")
    assert out2 == fm + "tail: 9\n"


def test_set_scalar_preserves_inline_comment():
    _, fm, _ = fmt.split_note(GNARLY)
    out = fmt.set_scalar(fm, "stage", "testing")
    assert "stage: testing            # research | design | development" in out
    # nothing else moved:
    fmt.verify_untouched(fm, out, {"stage"})
    diff = [
        (a, b)
        for a, b in zip(fm.splitlines(), out.splitlines())
        if a != b
    ]
    assert len(diff) == 1 and diff[0][0].startswith("stage:")


def test_set_scalar_without_comment():
    fm = "stage: research\n"
    assert fmt.set_scalar(fm, "stage", "design") == "stage: design\n"


def test_set_scalar_refuses_block_keys():
    _, fm, _ = fmt.split_note(GNARLY)
    with pytest.raises(fmt.FrontmatterError):
        fmt.set_scalar(fm, "changelog", "nope")
    with pytest.raises(fmt.FrontmatterError):
        fmt.set_scalar(fm, "missing_key", "x")


def test_crlf_notes_keep_crlf():
    crlf = GNARLY.replace("\n", "\r\n")
    head, fm, tail = fmt.split_note(crlf)
    assert fmt.join_note(head, fm, tail) == crlf
    nl = fmt.newline_of(fm)
    assert nl == "\r\n"
    block = fmt.emit_mapping_block("computed", {"open_issues": 1}, nl=nl)
    out = fmt.replace_key_block(fm, "computed", block)
    assert "\r\ncomputed:\r\n  open_issues: 1\r\n" in "\r\n" + out


def test_emit_scalar_quoting():
    assert fmt.emit_scalar("TypeScript") == "TypeScript"
    assert fmt.emit_scalar("no CI config detected") == '"no CI config detected"'
    assert fmt.emit_scalar("true") == '"true"'
    assert fmt.emit_scalar("1.5") == '"1.5"'
    assert fmt.emit_scalar(None) == ""
    assert fmt.emit_scalar(False) == "false"
    assert fmt.emit_scalar(dt.date(2026, 1, 2)) == "2026-01-02"
    assert fmt.emit_scalar('say "hi" # not a comment') == '"say \\"hi\\" # not a comment"'


def test_emit_mapping_block_round_trips_via_yaml():
    data = {
        "cost_total_mtd": 12.5,
        "cost_by_stage": {"development": 8.0, "testing": 4.5},
        "team_status": "automated-active",
        "open_reviews": [
            {"id": "PC-12", "priority": "high", "age_days": 2},
        ],
        "missing_signals": ["no README", "no CI config detected"],
    }
    block = fmt.emit_mapping_block("computed", data)
    parsed = yaml.safe_load(block)["computed"]
    assert parsed == data


def test_verify_untouched_catches_drift():
    fm_before = "status: in-flight\ncomputed:\n  a: 1\n"
    fm_after = "status: shipped\ncomputed:\n  a: 2\n"
    with pytest.raises(fmt.FrontmatterError, match="status"):
        fmt.verify_untouched(fm_before, fm_after, {"computed"})
    fmt.verify_untouched(fm_before, "status: in-flight\ncomputed:\n  a: 9\n", {"computed"})
