"""Azure AI Speech REST TTS (free F0 tier: 500k characters/month)."""

import os
from pathlib import Path
from xml.sax.saxutils import escape

import httpx


class AzureTTS:
    def __init__(self, key: str, region: str):
        self.key = key
        self.url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"

    @classmethod
    def from_env(cls) -> "AzureTTS":
        return cls(os.environ["AZURE_SPEECH_KEY"], os.environ["AZURE_SPEECH_REGION"])

    def synthesize(self, text: str, voice: str, out_path: Path, rate: str = "+0%") -> None:
        lang = "-".join(voice.split("-")[:2])
        ssml = (
            f'<speak version="1.0" xml:lang="{lang}"><voice name="{voice}">'
            f'<prosody rate="{rate}">{escape(text)}</prosody></voice></speak>'
        )
        response = httpx.post(
            self.url,
            content=ssml.encode("utf-8"),
            headers={
                "Ocp-Apim-Subscription-Key": self.key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
                "User-Agent": "hungarian-vocab",
            },
            timeout=60,
        )
        response.raise_for_status()
        out_path.write_bytes(response.content)
