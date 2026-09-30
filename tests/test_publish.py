from datetime import UTC, datetime
from xml.etree import ElementTree

from vocab.models import Card, ListIndex, ListIndexEntry, WordList
from vocab.notify.message import email_html, telegram_text
from vocab.publish.feed import build_feed


def test_feed_includes_only_lists_with_audio():
    index = ListIndex(
        lists=[
            ListIndexEntry(id="2026-W40", created=datetime(2026, 9, 28, tzinfo=UTC), n_cards=20,
                           audio_url="https://example.com/a&b.mp3", audio_bytes=123,
                           topics=["food & drink"]),
            ListIndexEntry(id="2026-W41", created=datetime(2026, 10, 5, tzinfo=UTC), n_cards=20),
        ]
    )
    root = ElementTree.fromstring(build_feed(index, "https://me.github.io/hv"))
    items = root.findall("./channel/item")
    assert len(items) == 1
    assert items[0].find("enclosure").get("url") == "https://example.com/a&b.mp3"


def test_messages_escape_html():
    wl = WordList(
        id="2026-W40",
        created=datetime(2026, 9, 28, tzinfo=UTC),
        cards=[Card(id="x", front_en="<b>", back_hu="és & vagy", word_ids=["x"])],
    )
    assert "&lt;b&gt;" in email_html(wl, "https://me.github.io/hv")
    assert "és &amp; vagy" in telegram_text(wl, "https://me.github.io/hv")
