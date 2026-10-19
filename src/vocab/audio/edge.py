"""Free Microsoft Edge "Read aloud" neural voices via the edge-tts package (no API key).

Unofficial endpoint: if it breaks, switch `audio.provider` to "azure" — same voices, official API.
"""

import asyncio
import time
from pathlib import Path

import edge_tts

RETRY_DELAYS = (2, 5)  # seconds; covers brief network blips, not a blocked endpoint


class EdgeTTS:
    def synthesize(self, text: str, voice: str, out_path: Path, rate: str = "+0%") -> None:
        for delay in (*RETRY_DELAYS, None):
            try:
                asyncio.run(edge_tts.Communicate(text, voice, rate=rate).save(str(out_path)))
                return
            except Exception:
                if delay is None:
                    raise
                time.sleep(delay)
