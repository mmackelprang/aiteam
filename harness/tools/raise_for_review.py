"""raise-for-review — the ONLY path that creates a review item.

Wraps Paperclip's Issues API, enforces the §2.1 schema (tools/
review_schema.py), and hands the created item to tools/notify.py for
channel rendering.

HARD RULE (CLAUDE.md #1): no agent, script, or session writes directly to
a Paperclip issue for review purposes outside this tool. If something
needs to be "flagged for review", the answer is: call this tool. Agents
blocked by a Tier-0 permission denial use this too (plan F10 / D4).

    raise_for_review.py --project familyworkspace --type question \
        --priority high --raised-by engineer \
        --summary "Should X use the existing queue or a new topic?" \
        --reasoning "Tried A and B; both conflict with the retention policy." \
        --confidence 0.4 \
        --document "Design note=https://example.com/doc" \
        [--routing config/notification_routing/familyworkspace.yaml] \
        [--dry-run] [--no-notify]

⚠ The HTTP client is a stub: Paperclip's real Issues API shape is
reconciled at install time (Stage 5) — until then only --dry-run and the
in-memory client (tests) run end to end. Everything schema-side is final.

Contract: HANDOFF-agentic-harness.md §6, Task 3.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.review_schema import (  # noqa: E402
    PRIORITIES, ROLES, TYPES, Document, ReviewItem, SchemaError,
)


class PaperclipError(RuntimeError):
    pass


class InMemoryPaperclipClient:
    """Test double: assigns sequential ids, remembers items."""

    def __init__(self):
        self.items: list[ReviewItem] = []

    def create_issue(self, item: ReviewItem) -> str:
        issue_id = f"PC-{len(self.items) + 1}"
        self.items.append(item)
        return issue_id


class HttpPaperclipClient:
    """⚠ STUB — Paperclip's Issues API shape is unknown until it's installed
    (Stage 5). Reconcile endpoint/payload then; keep the create_issue()
    signature. Never bypass this client to write issues some other way
    (hard rule #1)."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def create_issue(self, item: ReviewItem) -> str:
        raise NotImplementedError(
            "HttpPaperclipClient.create_issue: reconcile with the real Paperclip "
            "Issues API at Stage 5 (docs/implementation-plan.md) — use --dry-run "
            "until then"
        )


def raise_item(item: ReviewItem, client, notifier=None) -> ReviewItem:
    """Create the review item via `client`, then notify. Returns item with id."""
    item.validate()
    item.id = client.create_issue(item)
    if notifier is not None:
        notifier(item)
    return item


def parse_document(spec: str) -> Document:
    if "=" not in spec:
        raise SchemaError(f"--document must be LABEL=URL, got {spec!r}")
    label, url = spec.split("=", 1)
    return Document(label=label.strip(), url=url.strip())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="raise-for-review", description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--type", required=True, choices=TYPES)
    ap.add_argument("--priority", required=True, choices=PRIORITIES)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--reasoning", required=True)
    ap.add_argument("--confidence", type=float, default=0.5)
    ap.add_argument("--raised-by", default="project-lead", choices=ROLES)
    ap.add_argument("--document", action="append", default=[], metavar="LABEL=URL")
    ap.add_argument("--paperclip-url", default="http://localhost:3100",
                    help="Paperclip base URL (LAN/tailnet only — never public)")
    ap.add_argument("--routing", type=Path,
                    help="notification routing YAML; omit to skip notifying")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate + print the item JSON; create nothing, send nothing")
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args(argv)

    try:
        item = ReviewItem.new(
            project=args.project,
            type=args.type,
            priority=args.priority,
            summary=args.summary,
            reasoning=args.reasoning,
            confidence_score=args.confidence,
            raised_by=args.raised_by,
            documents=[parse_document(d) for d in args.document],
        )
    except SchemaError as exc:
        print(f"schema error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(item.to_json())
        return 0

    notifier = None
    if args.routing and not args.no_notify:
        from tools import notify as notify_mod

        routing = notify_mod.load_routing(args.routing)

        def notifier(created: ReviewItem) -> None:
            notify_mod.notify(created, routing, paperclip_base=args.paperclip_url)

    try:
        raise_item(item, HttpPaperclipClient(args.paperclip_url), notifier)
    except NotImplementedError as exc:
        print(f"not yet wired: {exc}", file=sys.stderr)
        return 3
    print(f"created {item.id} ({item.priority} {item.type}) for {item.project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
