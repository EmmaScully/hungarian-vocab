"""Send the weekly word list and mp3 to a Telegram chat via a bot."""

import os
from pathlib import Path

import httpx

from vocab.models import WordList
from vocab.notify.message import telegram_text

MAX_MESSAGE = 4096


def send_telegram(word_list: WordList, site_url: str, audio: Path | None) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    base = f"https://api.telegram.org/bot{token}"

    with httpx.Client(timeout=120) as client:
        r = client.post(
            f"{base}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": telegram_text(word_list, site_url)[:MAX_MESSAGE],
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
        r.raise_for_status()

        if audio is not None and audio.exists():
            with audio.open("rb") as f:
                r = client.post(
                    f"{base}/sendAudio",
                    data={
                        "chat_id": chat_id,
                        "title": f"Hungarian vocab {word_list.id}",
                        "performer": "hungarian-vocab",
                    },
                    files={"audio": (audio.name, f, "audio/mpeg")},
                )
            r.raise_for_status()
