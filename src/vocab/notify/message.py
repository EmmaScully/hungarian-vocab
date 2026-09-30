"""Content of the weekly notification, shared by the email and Telegram senders."""

from html import escape

from vocab.models import WordList


def site_link(site_url: str) -> str:
    return site_url.rstrip("/") + "/"


def feed_link(site_url: str) -> str:
    return site_link(site_url) + "data/feed.xml"


def email_subject(word_list: WordList) -> str:
    return f"🇭🇺 Hungarian words for {word_list.id} ({len(word_list.cards)} words)"


def email_html(word_list: WordList, site_url: str) -> str:
    rows = "".join(
        "<tr>"
        f"<td style='padding:6px 10px'>{escape(c.front_en)}</td>"
        f"<td style='padding:6px 10px'><b>{escape(c.back_hu)}</b></td>"
        f"<td style='padding:6px 10px;color:#666'>{escape(c.example_hu or '')}"
        f"<br><i>{escape(c.example_en or '')}</i></td>"
        f"<td style='padding:6px 10px;color:#999'>{'review' if c.source == 'review' else ''}</td>"
        "</tr>"
        for c in word_list.cards
    )
    audio = (
        f"<a href='{escape(word_list.audio_url)}'>Download this week's mp3</a> · "
        if word_list.audio_url
        else ""
    )
    return f"""\
<div style="font-family:system-ui,sans-serif;max-width:720px">
  <h2>Your Hungarian words for {escape(word_list.id)}</h2>
  <p>
    <a href="{site_link(site_url)}">Open flashcards</a> ·
    {audio}<a href="{feed_link(site_url)}">Podcast feed</a>
  </p>
  <table style="border-collapse:collapse;font-size:15px">
    <tr style="text-align:left;border-bottom:1px solid #ddd">
      <th style="padding:6px 10px">English</th><th style="padding:6px 10px">Magyar</th>
      <th style="padding:6px 10px">Example</th><th></th>
    </tr>
    {rows}
  </table>
  <p style="color:#666">Revise during the week, then take the <b>test</b> before next Monday
  so the word bank knows what to bring back.</p>
</div>"""


def email_text(word_list: WordList, site_url: str) -> str:
    lines = [f"Your Hungarian words for {word_list.id}", ""]
    lines += [f"{c.front_en} — {c.back_hu}" for c in word_list.cards]
    lines += ["", f"Flashcards: {site_link(site_url)}"]
    if word_list.audio_url:
        lines.append(f"Audio: {word_list.audio_url}")
    lines.append("Take the test before next Monday.")
    return "\n".join(lines)


def telegram_text(word_list: WordList, site_url: str) -> str:
    words = "\n".join(
        f"• {escape(c.front_en)} — <b>{escape(c.back_hu)}</b>" for c in word_list.cards
    )
    return (
        f"🇭🇺 <b>Hungarian words for {escape(word_list.id)}</b>\n\n{words}\n\n"
        f'<a href="{site_link(site_url)}">Flashcards</a> · take the test before Monday.'
    )
