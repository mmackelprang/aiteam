"""review_item schema: validation, SLA math, the single create path."""

import datetime as dt

import pytest

from tools import raise_for_review as rfr
from tools.review_schema import SLA, Document, ReviewItem, SchemaError

NOW = dt.datetime(2026, 7, 23, 12, 0, tzinfo=dt.timezone.utc)


def make_item(**over):
    kwargs = dict(
        project="familyworkspace",
        type="question",
        priority="high",
        summary="Should X use the existing queue?",
        reasoning="Tried A and B; both conflict with retention.",
        confidence_score=0.4,
        raised_by="engineer",
        documents=[Document("Design note", "https://example.com/doc")],
    )
    kwargs.update(over)
    return ReviewItem.new(now=NOW, **kwargs)


def test_new_derives_sla_from_priority():
    for priority, delta in SLA.items():
        item = make_item(priority=priority)
        assert item.raised_at == NOW
        assert item.sla_due_at == NOW + delta
    assert make_item(priority="critical").sla_due_at == NOW + dt.timedelta(hours=4)
    assert make_item(priority="low").sla_due_at == NOW + dt.timedelta(weeks=1)


def test_past_sla_only_when_pending():
    item = make_item(priority="critical")
    assert not item.is_past_sla(NOW + dt.timedelta(hours=3))
    assert item.is_past_sla(NOW + dt.timedelta(hours=5))
    item.status = "answered"
    assert not item.is_past_sla(NOW + dt.timedelta(days=30))


@pytest.mark.parametrize(
    "over,fragment",
    [
        ({"type": "musing"}, "type must be one of"),
        ({"priority": "urgent"}, "priority must be one of"),
        ({"summary": ""}, "summary is required"),
        ({"summary": "x" * 401}, "cap 400"),
        ({"reasoning": " "}, "reasoning is required"),
        ({"confidence_score": 1.5}, "0.0-1.0"),
        ({"raised_by": "cto"}, "raised_by must be one of"),
        ({"documents": [Document("", "https://x.example")]}, "label is required"),
        ({"documents": [Document("doc", "ftp://x.example")]}, "must be http(s)"),
    ],
)
def test_validation_failures(over, fragment):
    with pytest.raises(SchemaError, match=fragment.replace("(", "\\(").replace(")", "\\)")):
        make_item(**over)


def test_round_trip_dict():
    item = make_item()
    item.id = "PC-9"
    again = ReviewItem.from_dict(item.to_dict())
    assert again == item


def test_paperclip_url():
    item = make_item()
    assert item.paperclip_url("http://appserver:3100/") == "http://appserver:3100"
    item.id = "PC-4"
    assert item.paperclip_url("http://appserver:3100") == "http://appserver:3100/issues/PC-4"


def test_raise_item_assigns_id_and_notifies():
    client = rfr.InMemoryPaperclipClient()
    seen = []
    item = rfr.raise_item(make_item(), client, notifier=seen.append)
    assert item.id == "PC-1"
    assert client.items == [item]
    assert seen == [item]


def test_http_client_is_an_honest_stub():
    with pytest.raises(NotImplementedError, match="Stage 5"):
        rfr.HttpPaperclipClient("http://x:3100").create_issue(make_item())


def test_cli_dry_run_prints_valid_item(capsys):
    rc = rfr.main(
        ["--project", "familyworkspace", "--type", "question", "--priority", "high",
         "--summary", "s", "--reasoning", "r", "--raised-by", "qa",
         "--document", "Doc=https://example.com/d", "--dry-run"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    item = ReviewItem.from_dict(__import__("json").loads(out))
    assert item.raised_by == "qa" and item.status == "pending"


def test_cli_rejects_bad_schema(capsys):
    rc = rfr.main(
        ["--project", "p", "--type", "question", "--priority", "high",
         "--summary", "s", "--reasoning", "r", "--confidence", "3",
         "--dry-run"]
    )
    assert rc == 2
    assert "confidence" in capsys.readouterr().err
