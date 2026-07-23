"""Cost events + rollup: tagging enforced from event one, MTD filters,
per-role/kind buckets, notional pricing honesty."""

import datetime as dt

import pytest

from tools import cost_summary as cs
from tools.cost_events import CostEvent, CostEventError, append_event, read_events

UTC = dt.timezone.utc


def ev(role="engineer", task="PC-1", kind="task", tin=1000, tout=200,
       ts=dt.datetime(2026, 7, 23, 12, 0, tzinfo=UTC), project="familyworkspace",
       model="claude-test-model"):
    return CostEvent(project=project, agent_role=role, task_id=task, model=model,
                     input_tokens=tin, output_tokens=tout, timestamp=ts,
                     event_kind=kind)


def test_tags_required_from_first_event():
    with pytest.raises(CostEventError, match="hard rule #6"):
        ev(project="").validate()
    with pytest.raises(CostEventError, match="hard rule #6"):
        ev(task="").validate()
    with pytest.raises(CostEventError, match="timezone-aware"):
        ev(ts=dt.datetime(2026, 7, 23, 12, 0)).validate()
    with pytest.raises(CostEventError, match="event_kind"):
        ev(kind="misc").validate()


def test_wire_format_uses_otel_genai_names():
    wire = ev().to_wire()
    assert wire["gen_ai.system"] == "anthropic"
    assert wire["gen_ai.usage.input_tokens"] == 1000
    assert wire["aiteam.project"] == "familyworkspace"
    assert wire["aiteam.agent_role"] == "engineer"
    assert wire["aiteam.task_id"] == "PC-1"
    assert CostEvent.from_wire(wire) == ev()


def test_append_and_read_roundtrip(tmp_path):
    log = tmp_path / "events.jsonl"
    append_event(log, ev())
    append_event(log, ev(role="qa", task="PC-2", tin=500, tout=50))
    log.open("a").write("not json\n")  # corruption must not kill the reader
    events = list(read_events(log))
    assert len(events) == 2
    assert events[1].agent_role == "qa"


def test_rollup_buckets_and_month_filter(tmp_path):
    events = [
        ev(),
        ev(role="qa", task="PC-2", tin=500, tout=50),
        ev(kind="heartbeat", task="hb", tin=3000, tout=10),
        ev(ts=dt.datetime(2026, 6, 30, 23, 0, tzinfo=UTC), tin=99999),  # June
        ev(project="other-project", tin=77777),
    ]
    s = cs.rollup(events, project="familyworkspace", month="2026-07")
    assert s["events"] == 3
    assert s["input_tokens"] == 1000 + 500 + 3000
    assert s["by_role"]["engineer"]["events"] == 2
    assert s["by_role"]["qa"]["output_tokens"] == 50
    # F13: heartbeat overhead is directly measurable
    assert s["by_kind"]["heartbeat"]["input_tokens"] == 3000
    assert "cost_usd_notional" not in s  # no pricing table -> tokens only


def test_notional_pricing_and_incompleteness():
    pricing = {"claude-test-model": {"input_per_mtok": 3.0, "output_per_mtok": 15.0}}
    events = [ev(), ev(model="claude-unpriced", tin=1000, tout=1000)]
    s = cs.rollup(events, pricing=pricing)
    # 1000 in * $3/M + 200 out * $15/M = 0.003 + 0.003 = 0.006
    assert s["cost_usd_notional"] == 0.006
    assert s["cost_usd_incomplete"] is True
    s2 = cs.rollup([ev()], pricing=pricing)
    assert s2["cost_usd_incomplete"] is False
    assert s2["by_role"]["engineer"]["cost_usd"] == 0.006


def test_cli_json(tmp_path, capsys):
    log = tmp_path / "events.jsonl"
    append_event(log, ev())
    rc = cs.main(["--events", str(log), "--project", "familyworkspace",
                  "--month", "2026-07", "--format", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"events": 1' in out and '"engineer"' in out


def test_example_pricing_file_loads():
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / "config" / "pricing.example.yaml"
    assert cs.load_pricing(example) == {}  # placeholders only — by design
