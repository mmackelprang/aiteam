"""cost-summary — READ-interface for per-project cost data.

Rolls up the tagged cost-event log (tools/cost_events.py) into the shapes
the portfolio sync job consumes: total MTD, by agent-role, by task, by
event kind (heartbeat overhead per F13 falls out of this for free).

HARD RULE (CLAUDE.md #3): this repo exposes read-interfaces only. The
write into the portfolio vault's `computed:` block (cost_by_stage,
cost_total_mtd) happens in ../../portfolio/sync/sync_computed_fields.py,
per that system's single-writer rule. Never build a vault write path here.

Dollars are notional (D5: subscription auth) — derived at read time from
an optional pricing YAML (config/pricing.yaml, see pricing.example.yaml;
prices per million tokens). No pricing file → token counts only, which
are the ground truth either way. Budget alerting (F11: flag at 80%) works
on whichever unit the budget is expressed in.

Paperclip's own cost-events API becomes a second input at Stage 5+ —
same rollup shapes, same read-only stance.

CLI:
    cost_summary.py --events /data/aiteam/cost-events/events.jsonl \
        --project familyworkspace [--month 2026-07] [--pricing config/pricing.yaml] \
        [--format json|text]

Contract: HANDOFF-agentic-harness.md §5 + §6, Task 6.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.cost_events import CostEvent, read_events  # noqa: E402


def load_pricing(path: str | Path | None) -> dict:
    """{model: {input_per_mtok: float, output_per_mtok: float}} or {}."""
    if path is None:
        return {}
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return data.get("models") or {}


def notional_cost_usd(event: CostEvent, pricing: dict) -> float | None:
    p = pricing.get(event.model)
    if not p:
        return None
    return (
        event.input_tokens * float(p.get("input_per_mtok", 0)) / 1_000_000
        + event.output_tokens * float(p.get("output_per_mtok", 0)) / 1_000_000
    )


def in_month(ts: dt.datetime, month: str) -> bool:
    return ts.strftime("%Y-%m") == month


def rollup(events, *, project: str | None = None, month: str | None = None,
           pricing: dict | None = None) -> dict:
    """Aggregate events → the read-interface shape the portfolio sync reads.

    Priced totals appear only when every model involved has pricing; a
    partial pricing table yields cost_usd_incomplete: true so a rollup
    never silently understates spend.
    """
    pricing = pricing or {}
    out = {
        "project": project,
        "month": month,
        "events": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "by_role": defaultdict(lambda: {"events": 0, "input_tokens": 0, "output_tokens": 0}),
        "by_task": defaultdict(lambda: {"events": 0, "input_tokens": 0, "output_tokens": 0}),
        "by_kind": defaultdict(lambda: {"events": 0, "input_tokens": 0, "output_tokens": 0}),
    }
    cost_total = 0.0
    unpriced = 0
    for e in events:
        if project and e.project != project:
            continue
        if month and not in_month(e.timestamp, month):
            continue
        out["events"] += 1
        out["input_tokens"] += e.input_tokens
        out["output_tokens"] += e.output_tokens
        for bucket, key in (("by_role", e.agent_role), ("by_task", e.task_id),
                            ("by_kind", e.event_kind)):
            b = out[bucket][key]
            b["events"] += 1
            b["input_tokens"] += e.input_tokens
            b["output_tokens"] += e.output_tokens
        c = notional_cost_usd(e, pricing)
        if c is None:
            unpriced += 1
        else:
            cost_total += c
            for bucket, key in (("by_role", e.agent_role), ("by_kind", e.event_kind)):
                out[bucket][key].setdefault("cost_usd", 0.0)
                out[bucket][key]["cost_usd"] = round(out[bucket][key]["cost_usd"] + c, 4)
    out["by_role"] = dict(sorted(out["by_role"].items()))
    out["by_task"] = dict(sorted(out["by_task"].items()))
    out["by_kind"] = dict(sorted(out["by_kind"].items()))
    if pricing:
        out["cost_usd_notional"] = round(cost_total, 4)
        out["cost_usd_incomplete"] = unpriced > 0
    return out


def render_text(summary: dict) -> str:
    lines = [
        f"project: {summary['project'] or '(all)'}   month: {summary['month'] or '(all)'}",
        f"events: {summary['events']}   tokens in/out: "
        f"{summary['input_tokens']:,}/{summary['output_tokens']:,}",
    ]
    if "cost_usd_notional" in summary:
        star = " (incomplete pricing!)" if summary["cost_usd_incomplete"] else ""
        lines.append(f"notional cost: ${summary['cost_usd_notional']:.2f}{star}")
    lines.append("by role:")
    for role, b in summary["by_role"].items():
        cost = f"  ${b['cost_usd']:.2f}" if "cost_usd" in b else ""
        lines.append(
            f"  {role:<14} {b['events']:>4} ev  {b['input_tokens']:>10,} in "
            f"{b['output_tokens']:>9,} out{cost}"
        )
    lines.append("by kind:")
    for kind, b in summary["by_kind"].items():
        lines.append(f"  {kind:<14} {b['events']:>4} ev  {b['input_tokens']:>10,} in "
                     f"{b['output_tokens']:>9,} out")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cost-summary", description=__doc__.splitlines()[0])
    ap.add_argument("--events", required=True, type=Path, help="JSONL event log")
    ap.add_argument("--project")
    ap.add_argument("--month", help="YYYY-MM (default: current month)")
    ap.add_argument("--all-time", action="store_true", help="ignore --month")
    ap.add_argument("--pricing", type=Path, help="pricing YAML (see config/pricing.example.yaml)")
    ap.add_argument("--format", choices=["json", "text"], default="text")
    args = ap.parse_args(argv)

    month = None if args.all_time else (args.month or dt.date.today().strftime("%Y-%m"))
    try:
        pricing = load_pricing(args.pricing)
    except (OSError, yaml.YAMLError) as exc:
        print(f"error: bad pricing file: {exc}", file=sys.stderr)
        return 2
    summary = rollup(read_events(args.events), project=args.project, month=month,
                     pricing=pricing)
    print(json.dumps(summary, indent=2) if args.format == "json" else render_text(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
