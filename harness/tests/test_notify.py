"""Renderers + routing: the acceptance criteria as tests — every document
clickable on every channel, Paperclip link primary, per-role webhooks."""

import datetime as dt
import json

import pytest

from tools import notify
from tools.review_schema import Document, ReviewItem

NOW = dt.datetime(2026, 7, 23, 12, 0, tzinfo=dt.timezone.utc)
PC = "http://appserver:3100"


def make_item(**over):
    kwargs = dict(
        project="familyworkspace",
        type="design-decision",
        priority="critical",
        summary="Queue vs topic for X?",
        reasoning="Both prototyped; retention conflicts.",
        confidence_score=0.35,
        raised_by="engineer",
        documents=[
            Document("Design note", "https://example.com/design"),
            Document("Spike results", "https://example.com/spike"),
        ],
    )
    kwargs.update(over)
    item = ReviewItem.new(now=NOW, **kwargs)
    item.id = "PC-7"
    return item


def _urls_in(obj) -> set:
    urls = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "url" and isinstance(v, str):
                urls.add(v)
            else:
                urls |= _urls_in(v)
    elif isinstance(obj, list):
        for v in obj:
            urls |= _urls_in(v)
    return urls


def test_slack_rendering_has_all_links_and_priority():
    payload = notify.render_slack(make_item(), PC)
    urls = _urls_in(payload["blocks"])
    assert "https://example.com/design" in urls
    assert "https://example.com/spike" in urls
    assert f"{PC}/issues/PC-7" in urls
    header = payload["blocks"][0]["text"]["text"]
    assert "CRITICAL" in header and "familyworkspace" in header and "🔴" in header
    primary = [b for b in payload["blocks"][-1]["elements"] if b.get("style") == "primary"]
    assert len(primary) == 1 and primary[0]["url"].endswith("/issues/PC-7")
    assert "SLA due 2026-07-23 16:00 UTC" in json.dumps(payload)  # critical = +4h
    assert payload["text"].startswith("[CRITICAL] familyworkspace:")


def test_google_chat_rendering_has_all_links_and_headers():
    payload = notify.render_google_chat(make_item(), PC)
    urls = _urls_in(payload["cardsV2"])
    assert {"https://example.com/design", "https://example.com/spike",
            f"{PC}/issues/PC-7"} <= urls
    card = payload["cardsV2"][0]["card"]
    assert "CRITICAL" in card["header"]["title"]
    assert "raised by engineer" in card["header"]["subtitle"]
    buttons = card["sections"][1]["widgets"][0]["buttonList"]["buttons"]
    assert buttons[0]["text"] == "Open in Paperclip"
    assert payload["cardsV2"][0]["cardId"] == "PC-7"


ROUTING = {
    "project": "familyworkspace",
    "channels": ["slack", "google_chat"],
    "slack": {"target": "#familyworkspace-reviews"},
    "google_chat": {
        "webhooks": {
            "project-lead": "${GC_HOOK_FW_LEAD}",
            "engineer": "${GC_HOOK_FW_ENG}",
        },
    },
}


def test_webhook_selected_per_raising_role(monkeypatch):
    monkeypatch.setenv("GC_HOOK_FW_LEAD", "https://chat.googleapis.com/v1/spaces/A/messages?key=k1")
    monkeypatch.setenv("GC_HOOK_FW_ENG", "https://chat.googleapis.com/v1/spaces/A/messages?key=k2")
    assert notify.select_google_webhook(ROUTING, "engineer").endswith("key=k2")
    assert notify.select_google_webhook(ROUTING, "project-lead").endswith("key=k1")


def test_webhook_missing_role_falls_back_then_errors(monkeypatch):
    monkeypatch.setenv("GC_HOOK_FW_LEAD", "https://x.example/lead")
    with pytest.raises(notify.NotifyError, match="no Google Chat webhook for role 'qa'"):
        notify.select_google_webhook(ROUTING, "qa")
    fallback = {**ROUTING, "google_chat": {"webhook_url": "${GC_HOOK_FW_LEAD}"}}
    assert notify.select_google_webhook(fallback, "qa") == "https://x.example/lead"


def test_unset_env_var_names_the_variable(monkeypatch):
    monkeypatch.delenv("GC_HOOK_FW_ENG", raising=False)
    with pytest.raises(notify.NotifyError, match="GC_HOOK_FW_ENG"):
        notify.select_google_webhook(ROUTING, "engineer")


def test_notify_dry_run_renders_both_channels(monkeypatch):
    monkeypatch.setenv("GC_HOOK_FW_LEAD", "https://x.example/lead")
    monkeypatch.setenv("GC_HOOK_FW_ENG", "https://x.example/eng")
    results = notify.notify(make_item(), ROUTING, paperclip_base=PC, dry_run=True)
    assert [(c, t) for c, t, _ in results] == [
        ("slack", "#familyworkspace-reviews"),
        ("google_chat", "https://x.example/eng"),
    ]


def test_notify_rejects_unknown_channel():
    bad = {**ROUTING, "channels": ["carrier_pigeon"]}
    with pytest.raises(notify.NotifyError, match="hard rule #4"):
        notify.notify(make_item(), bad, paperclip_base=PC, dry_run=True)


def test_example_routing_file_loads_and_selects(monkeypatch, tmp_path):
    """The committed _example.yaml stays a working, loadable reference."""
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / "config" / "notification_routing" / "_example.yaml"
    routing = notify.load_routing(example)
    assert routing["project"] == "example-project"
    monkeypatch.setenv("GOOGLE_CHAT_WEBHOOK_URL__EXAMPLE_PROJECT__PROJECT_LEAD", "https://x.example/pl")
    assert notify.select_google_webhook(routing, "project-lead") == "https://x.example/pl"


def test_cli_dry_run(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("GC_HOOK_FW_ENG", "https://x.example/eng")
    item_file = tmp_path / "item.json"
    item_file.write_text(json.dumps(make_item().to_dict()), encoding="utf-8")
    routing_file = tmp_path / "routing.yaml"
    routing_file.write_text(
        "notification_routing:\n"
        "  project: familyworkspace\n"
        "  channels: [google_chat]\n"
        "  google_chat:\n"
        "    webhooks:\n"
        "      engineer: ${GC_HOOK_FW_ENG}\n",
        encoding="utf-8",
    )
    rc = notify.main(["--item", str(item_file), "--routing", str(routing_file),
                      "--paperclip-url", PC, "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "google_chat" in out and "redacted" in out and "Queue vs topic" in out
