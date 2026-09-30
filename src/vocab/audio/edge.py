"""Free Microsoft Edge "Read aloud" neural voices via the edge-tts package (no API key).

Unofficial endpoint: if it breaks, switch `audio.provider` to "azure" — same voices, official API.
"""

import asyncio
from pathlib import Path

import edge_tts


class EdgeTTS:
    def synthesize(self, text: str, voice: str, out_path: Path, rate: str = "+0%") -> None:
        asyncio.run(edge_tts.Communicate(text, voice, rate=rate).save(str(out_path)))
