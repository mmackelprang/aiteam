"""notify — render the one review_item schema per channel, then send.

HARD RULES (CLAUDE.md #4, #5):
- One schema (tools/review_schema.py), rendered per channel. Add a
  renderer HERE for a new channel; never fork the shape or hand-build a
  payload elsewhere.
- Google Chat is one-way webhook only in Phase 0/1. Per-agent identity
  comes from *named webhooks* (F14 tier 1): a Chat space holds one webhook
  per team-lead/PM (name + avatar set at webhook creation), mapped by
  raising role in config/notification_routing/<project>.yaml. The two-way
  Chat app is Phase 2, on explicit approval only.

Every rendering includes a clickable link for each `documents` entry plus
the primary "Open in Paperclip" link — which is also the answer path while
notifications are one-way (F12; off-LAN over the tailnet).

Committed routing configs reference env vars (``${VAR}``) — webhook URLs
embed key+token and are secrets (F3). notify.py resolves them at send
time from the environment.

⚠ The two send functions are LIVE-UNVERIFIED (written off-site; no tokens
here). Renderers + routing selection are fully tested; exercise real sends
at Stage 6.

Contract: HANDOFF-agentic-harness.md §6, Task 4 (Task 5 adds SLA
escalation + the daily digest on top).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.review_schema import ReviewItem  # noqa: E402

PRIORITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}


class NotifyError(RuntimeError):
    pass


# --- routing config ----------------------------------------------------------

_ENV_REF = re.compile(r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}")


def load_routing(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "notification_routing" not in data:
        raise NotifyError(f"{path}: expected a top-level notification_routing key (§2.2)")
    return data["notification_routing"]


def expand_env(value: str, *, context: str) -> str:
    def repl(m: re.Match) -> str:
        name = m.group("name")
        if name not in os.environ:
            raise NotifyError(
                f"environment variable {name} is not set (referenced by {context}) — "
                "webhook URLs are secrets and live in the env, not the config (F3)"
            )
        return os.environ[name]

    return _ENV_REF.sub(repl, value)


def select_google_webhook(routing: dict, raised_by: str) -> str:
    gc = routing.get("google_chat") or {}
    webhooks = gc.get("webhooks") or {}
    project = routing.get("project", "?")
    if raised_by in webhooks:
        return expand_env(str(webhooks[raised_by]),
                          context=f"google_chat.webhooks.{raised_by} for {project}")
    if gc.get("webhook_url"):
        return expand_env(str(gc["webhook_url"]),
                          context=f"google_chat.webhook_url for {project}")
    configured = ", ".join(sorted(webhooks)) or "(none)"
    raise NotifyError(
        f"no Google Chat webhook for role {raised_by!r} on project {project!r} "
        f"(configured roles: {configured}; no webhook_url fallback)"
    )


# --- renderers (the only place channel payloads exist — hard rule #4) --------

def _sla_line(item: ReviewItem) -> str:
    due = item.sla_due_at.strftime("%Y-%m-%d %H:%M UTC") if item.sla_due_at else "n/a"
    return due


def render_slack(item: ReviewItem, paperclip_base: str) -> dict:
    """Slack Block Kit. Every document is a clickable button; Paperclip is
    the primary action."""
    emoji = PRIORITY_EMOJI.get(item.priority, "")
    buttons = [
        {
            "type": "button",
            "style": "primary",
            "text": {"type": "plain_text", "text": "Open in Paperclip", "emoji": True},
            "url": item.paperclip_url(paperclip_base),
        }
    ]
    for doc in item.documents:
        buttons.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": doc.label[:75], "emoji": True},
                "url": doc.url,
            }
        )
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {item.priority.upper()} · {item.project} · {item.type}",
                "emoji": True,
            },
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{item.summary}*"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"_Why:_ {item.reasoning}"}},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"raised by *{item.raised_by}* · confidence "
                        f"{float(item.confidence_score):.0%} · SLA due {_sla_line(item)}"
                        + (f" · `{item.id}`" if item.id else "")
                    ),
                }
            ],
        },
        {"type": "actions", "elements": buttons},
    ]
    return {
        "text": f"[{item.priority.upper()}] {item.project}: {item.summary}",
        "blocks": blocks,
    }


def render_google_chat(item: ReviewItem, paperclip_base: str) -> dict:
    """Google Chat Cards v2 (one-way webhook payload). Sender identity comes
    from the named webhook itself (F14 tier 1), not this payload."""
    emoji = PRIORITY_EMOJI.get(item.priority, "")
    buttons = [
        {
            "text": "Open in Paperclip",
            "onClick": {"openLink": {"url": item.paperclip_url(paperclip_base)}},
        }
    ] + [
        {"text": doc.label, "onClick": {"openLink": {"url": doc.url}}}
        for doc in item.documents
    ]
    card = {
        "header": {
            "title": f"{emoji} {item.priority.upper()} · {item.type}",
            "subtitle": f"{item.project} · raised by {item.raised_by}",
        },
        "sections": [
            {
                "widgets": [
                    {"textParagraph": {"text": f"<b>{item.summary}</b>"}},
                    {"textParagraph": {"text": f"<i>Why:</i> {item.reasoning}"}},
                    {
                        "decoratedText": {
                            "topLabel": "SLA due",
                            "text": _sla_line(item),
                            "bottomLabel": f"confidence {float(item.confidence_score):.0%}",
                        }
                    },
                ]
            },
            {"widgets": [{"buttonList": {"buttons": buttons}}]},
        ],
    }
    return {
        "text": f"[{item.priority.upper()}] {item.project}: {item.summary}",
        "cardsV2": [{"cardId": item.id or "review-item", "card": card}],
    }


# --- senders (⚠ LIVE-UNVERIFIED — exercised at Stage 6) ----------------------

def _post_json(url: str, payload: dict, headers: dict | None = None) -> int:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=UTF-8", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


def send_slack(payload: dict, target: str) -> None:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise NotifyError("SLACK_BOT_TOKEN is not set")
    body = {"channel": target, **payload}
    status = _post_json(
        "https://slack.com/api/chat.postMessage", body,
        {"Authorization": f"Bearer {token}"},
    )
    if status != 200:
        raise NotifyError(f"Slack send failed with HTTP {status}")


def send_google_chat(payload: dict, webhook_url: str) -> None:
    status = _post_json(webhook_url, payload)
    if status != 200:
        raise NotifyError(f"Google Chat send failed with HTTP {status}")


# --- orchestration -----------------------------------------------------------

def notify(item: ReviewItem, routing: dict, *, paperclip_base: str,
           dry_run: bool = False) -> list[tuple[str, str, dict]]:
    """Render for every configured channel; send unless dry_run.

    Returns [(channel, target, payload)] for inspection/testing either way.
    """
    item.validate()
    channels = routing.get("channels") or []
    out: list[tuple[str, str, dict]] = []
    for channel in channels:
        if channel == "slack":
            target = (routing.get("slack") or {}).get("target")
            if not target:
                raise NotifyError(f"channels includes slack but slack.target is missing "
                                  f"for {routing.get('project')!r}")
            payload = render_slack(item, paperclip_base)
            out.append(("slack", target, payload))
            if not dry_run:
                send_slack(payload, target)
        elif channel == "google_chat":
            url = select_google_webhook(routing, item.raised_by)
            payload = render_google_chat(item, paperclip_base)
            out.append(("google_chat", url, payload))
            if not dry_run:
                send_google_chat(payload, url)
        else:
            raise NotifyError(f"unknown channel {channel!r} — add a renderer here, "
                              "never a side-channel payload (hard rule #4)")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="notify", description=__doc__.splitlines()[0])
    ap.add_argument("--item", required=True, type=Path, help="review_item JSON file")
    ap.add_argument("--routing", required=True, type=Path)
    ap.add_argument("--paperclip-url", default="http://localhost:3100")
    ap.add_argument("--dry-run", action="store_true", help="print payloads, send nothing")
    args = ap.parse_args(argv)

    try:
        item = ReviewItem.from_dict(json.loads(args.item.read_text(encoding="utf-8")))
        routing = load_routing(args.routing)
        results = notify(item, routing, paperclip_base=args.paperclip_url,
                         dry_run=args.dry_run)
    except (NotifyError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for channel, target, payload in results:
        shown = target if channel == "slack" else "<webhook url redacted>"
        print(f"--- {channel} -> {shown}")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
