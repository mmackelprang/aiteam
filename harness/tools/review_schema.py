"""The ONE review_item schema (HANDOFF §2.1) — shared by raise_for_review.py
(the only creator) and notify.py (the only renderer home).

Hard rule #4: one notification schema, rendered per channel. Anything that
needs a new field extends THIS dataclass; nothing hand-builds payloads.

Schema extension over §2.1 (documented in plan F14): ``raised_by`` — the
raising agent-role — so per-agent named webhooks can be selected per role.

SLA thresholds by priority: critical 4h, high 1 day, medium 3 days,
low 1 week. Past due + still pending → escalate, never silent.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field

TYPES = ["question", "design-decision", "roadmap-direction", "doc-review"]
PRIORITIES = ["critical", "high", "medium", "low"]
STATUSES = ["pending", "answered", "expired"]
ROLES = ["project-lead", "research", "design", "engineer", "qa", "release", "support"]

SLA = {
    "critical": dt.timedelta(hours=4),
    "high": dt.timedelta(days=1),
    "medium": dt.timedelta(days=3),
    "low": dt.timedelta(weeks=1),
}

SUMMARY_MAX = 400  # "1-2 sentences" — soft cap so summaries stay summaries


class SchemaError(ValueError):
    pass


@dataclass
class Document:
    label: str
    url: str


@dataclass
class ReviewItem:
    project: str
    type: str
    priority: str
    summary: str
    reasoning: str
    confidence_score: float = 0.5
    documents: list[Document] = field(default_factory=list)
    raised_by: str = "project-lead"   # F14 extension — selects the per-agent webhook
    id: str | None = None             # Paperclip issue id, set on create
    status: str = "pending"
    raised_at: dt.datetime | None = None
    sla_due_at: dt.datetime | None = None
    answered_at: dt.datetime | None = None

    # -- construction ---------------------------------------------------------
    @classmethod
    def new(cls, *, now: dt.datetime | None = None, **kwargs) -> "ReviewItem":
        """Build a pending item with raised_at/sla_due_at derived from now."""
        item = cls(**kwargs)
        item.raised_at = (now or dt.datetime.now(dt.timezone.utc)).replace(microsecond=0)
        item.sla_due_at = item.raised_at + SLA.get(item.priority, SLA["low"])
        item.validate()
        return item

    # -- validation -----------------------------------------------------------
    def validate(self) -> None:
        problems: list[str] = []
        if not self.project or not str(self.project).strip():
            problems.append("project is required")
        if self.type not in TYPES:
            problems.append(f"type must be one of {TYPES}, got {self.type!r}")
        if self.priority not in PRIORITIES:
            problems.append(f"priority must be one of {PRIORITIES}, got {self.priority!r}")
        if self.status not in STATUSES:
            problems.append(f"status must be one of {STATUSES}, got {self.status!r}")
        if self.raised_by not in ROLES:
            problems.append(f"raised_by must be one of {ROLES}, got {self.raised_by!r}")
        if not self.summary or not self.summary.strip():
            problems.append("summary is required (1-2 sentences)")
        elif len(self.summary) > SUMMARY_MAX:
            problems.append(f"summary is {len(self.summary)} chars; cap {SUMMARY_MAX} — it's a summary, not the reasoning")
        if not self.reasoning or not self.reasoning.strip():
            problems.append("reasoning is required (why the agent is asking, what it already tried)")
        try:
            c = float(self.confidence_score)
            if not (0.0 <= c <= 1.0):
                problems.append(f"confidence_score must be 0.0-1.0, got {c}")
        except (TypeError, ValueError):
            problems.append(f"confidence_score must be a number, got {self.confidence_score!r}")
        for i, doc in enumerate(self.documents):
            if not doc.label or not doc.label.strip():
                problems.append(f"documents[{i}].label is required")
            if not str(doc.url).startswith(("http://", "https://")):
                problems.append(f"documents[{i}].url must be http(s), got {doc.url!r}")
        if problems:
            raise SchemaError("; ".join(problems))

    # -- behaviour ------------------------------------------------------------
    def is_past_sla(self, now: dt.datetime | None = None) -> bool:
        if self.status != "pending" or self.sla_due_at is None:
            return False
        now = now or dt.datetime.now(dt.timezone.utc)
        return now > self.sla_due_at

    def paperclip_url(self, base: str) -> str:
        base = base.rstrip("/")
        return f"{base}/issues/{self.id}" if self.id else base

    # -- (de)serialization ----------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        for key in ("raised_at", "sla_due_at", "answered_at"):
            if d[key] is not None:
                d[key] = d[key].isoformat()
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "ReviewItem":
        d = dict(d)
        d["documents"] = [Document(**doc) if isinstance(doc, dict) else doc
                          for doc in d.get("documents", [])]
        for key in ("raised_at", "sla_due_at", "answered_at"):
            if d.get(key):
                d[key] = dt.datetime.fromisoformat(d[key])
        item = cls(**d)
        item.validate()
        return item
