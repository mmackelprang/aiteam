"""cost-events — the tagged event log every cost consumer reads.

HARD RULE (CLAUDE.md #6): every cost event is tagged with project id,
agent-role, and task id from the very first event, using OpenTelemetry
GenAI semantic-convention attribute names as the shape. That tagging is
what makes graduating to a real chargeback tool (Langfuse-class) a swap,
not a re-instrumentation.

Storage is one JSONL file (append-only) on the appserver —
``/data/aiteam/cost-events/events.jsonl`` in production, archived to the
NAS. One event per agent run/heartbeat:

    {"timestamp": "2026-07-23T12:00:00+00:00",
     "gen_ai.system": "anthropic",
     "gen_ai.request.model": "claude-x",
     "gen_ai.usage.input_tokens": 1200,
     "gen_ai.usage.output_tokens": 300,
     "aiteam.project": "familyworkspace",
     "aiteam.agent_role": "engineer",
     "aiteam.task_id": "PC-12",
     "aiteam.event_kind": "heartbeat" | "task" | ...}

Dollar costs are NOT stored on events (subscription auth makes them
notional — D5); they're derived at read time by cost_summary.py from an
optional pricing file. Token counts are the ground truth.

Also the home of heartbeat instrumentation (F13): log every heartbeat as
an event with event_kind="heartbeat" and the re-context token overhead is
measurable per role from day one.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

SYSTEM = "anthropic"
EVENT_KINDS = ["task", "heartbeat", "review", "other"]


class CostEventError(ValueError):
    pass


@dataclass
class CostEvent:
    project: str
    agent_role: str
    task_id: str
    model: str
    input_tokens: int
    output_tokens: int
    timestamp: dt.datetime
    event_kind: str = "task"
    cache_read_tokens: int = 0
    attributes: dict = field(default_factory=dict)

    def validate(self) -> None:
        problems = []
        for name in ("project", "agent_role", "task_id", "model"):
            if not getattr(self, name) or not str(getattr(self, name)).strip():
                problems.append(f"{name} is required from the first event (hard rule #6)")
        for name in ("input_tokens", "output_tokens", "cache_read_tokens"):
            v = getattr(self, name)
            if not isinstance(v, int) or v < 0:
                problems.append(f"{name} must be a non-negative int, got {v!r}")
        if self.event_kind not in EVENT_KINDS:
            problems.append(f"event_kind must be one of {EVENT_KINDS}, got {self.event_kind!r}")
        if self.timestamp.tzinfo is None:
            problems.append("timestamp must be timezone-aware (UTC)")
        if problems:
            raise CostEventError("; ".join(problems))

    # -- OTel GenAI-shaped wire format ---------------------------------------
    def to_wire(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "gen_ai.system": SYSTEM,
            "gen_ai.request.model": self.model,
            "gen_ai.usage.input_tokens": self.input_tokens,
            "gen_ai.usage.output_tokens": self.output_tokens,
            "gen_ai.usage.cache_read_tokens": self.cache_read_tokens,
            "aiteam.project": self.project,
            "aiteam.agent_role": self.agent_role,
            "aiteam.task_id": self.task_id,
            "aiteam.event_kind": self.event_kind,
            **{f"aiteam.attr.{k}": v for k, v in self.attributes.items()},
        }

    @classmethod
    def from_wire(cls, d: dict) -> "CostEvent":
        try:
            event = cls(
                project=d["aiteam.project"],
                agent_role=d["aiteam.agent_role"],
                task_id=d["aiteam.task_id"],
                model=d["gen_ai.request.model"],
                input_tokens=int(d["gen_ai.usage.input_tokens"]),
                output_tokens=int(d["gen_ai.usage.output_tokens"]),
                cache_read_tokens=int(d.get("gen_ai.usage.cache_read_tokens", 0)),
                timestamp=dt.datetime.fromisoformat(d["timestamp"]),
                event_kind=d.get("aiteam.event_kind", "task"),
                attributes={
                    k.removeprefix("aiteam.attr."): v
                    for k, v in d.items() if k.startswith("aiteam.attr.")
                },
            )
        except KeyError as exc:
            raise CostEventError(f"event missing required key: {exc}") from exc
        event.validate()
        return event


def append_event(path: str | Path, event: CostEvent) -> None:
    """Validate + append one event (atomic enough: single-line O_APPEND write)."""
    event.validate()
    line = json.dumps(event.to_wire(), ensure_ascii=False)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o640)
    try:
        os.write(fd, (line + "\n").encode("utf-8"))
    finally:
        os.close(fd)


def read_events(path: str | Path) -> Iterator[CostEvent]:
    """Yield valid events; malformed lines are reported, never fatal."""
    path = Path(path)
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield CostEvent.from_wire(json.loads(line))
            except (json.JSONDecodeError, CostEventError) as exc:
                import sys

                print(f"warning: {path}:{lineno}: skipping bad event: {exc}",
                      file=sys.stderr)
