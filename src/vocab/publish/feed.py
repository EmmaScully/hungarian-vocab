"""Podcast RSS feed of the weekly mp3s, served from GitHub Pages at data/feed.xml.

Subscribe to it once in any podcast app and each Monday's audio downloads automatically.
"""

from email.utils import format_datetime
from xml.sax.saxutils import escape

from vocab.models import ListIndex


def build_feed(index: ListIndex, site_url: str) -> str:
    site_url = site_url.rstrip("/") + "/"
    items = []
    for entry in sorted(index.lists, key=lambda e: e.created, reverse=True):
        if not entry.audio_url:
            continue
        duration = f"<itunes:duration>{int(entry.audio_duration_s or 0)}</itunes:duration>"
        items.append(
            "    <item>\n"
            f"      <title>Hungarian vocabulary {escape(entry.id)}</title>\n"
            f"      <description>{entry.n_cards} words: English, then Hungarian."
            "</description>\n"
            f"      <guid isPermaLink=\"false\">hungarian-vocab-{escape(entry.id)}</guid>\n"
            f"      <pubDate>{format_datetime(entry.created)}</pubDate>\n"
            f'      <enclosure url="{escape(entry.audio_url)}" '
            f'length="{entry.audio_bytes or 0}" type="audio/mpeg"/>\n'
            f"      {duration}\n"
            "    </item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">\n'
        "  <channel>\n"
        "    <title>Hungarian Vocab — Weekly Audio</title>\n"
        f"    <link>{escape(site_url)}</link>\n"
        "    <description>Weekly English→Hungarian vocabulary practice.</description>\n"
        "    <language>hu</language>\n"
        "    <itunes:category text=\"Education\"/>\n"
        "    <itunes:explicit>false</itunes:explicit>\n"
        + "\n".join(items)
        + "\n  </channel>\n</rss>\n"
    )
