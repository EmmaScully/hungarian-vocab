"""Text-to-speech provider interface."""

from pathlib import Path
from typing import Protocol

from vocab.config import AudioConfig


class TTSProvider(Protocol):
    def synthesize(self, text: str, voice: str, out_path: Path, rate: str = "+0%") -> None:
        """Write spoken `text` to `out_path` (mp3). `rate` is a relative speed like "-30%"."""
        ...


def get_tts(config: AudioConfig) -> TTSProvider:
    if config.provider == "edge":
        from vocab.audio.edge import EdgeTTS

        return EdgeTTS()
    if config.provider == "azure":
        from vocab.audio.azure import AzureTTS

        return AzureTTS.from_env()
    raise ValueError(f"Unknown TTS provider: {config.provider!r}")
