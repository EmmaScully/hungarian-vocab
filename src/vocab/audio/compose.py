"""Build the weekly practice mp3: English, pause, Hungarian, pause (and optionally slow Hungarian).

Every clip is normalised to 24 kHz mono WAV, joined with ffmpeg's concat demuxer, then encoded
to mp3 once, so clips from any TTS provider join cleanly.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from vocab.audio.base import TTSProvider
from vocab.config import AudioConfig
from vocab.models import WordList

SAMPLE_RATE = 24000


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def _to_wav(src: Path, dst: Path) -> None:
    _ffmpeg("-i", str(src), "-ar", str(SAMPLE_RATE), "-ac", "1", str(dst))


def _silence(seconds: float, dst: Path) -> None:
    _ffmpeg(
        "-f", "lavfi", "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono",
        "-t", f"{seconds}", str(dst),
    )


def duration_seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def build_audio(word_list: WordList, tts: TTSProvider, config: AudioConfig, out: Path) -> Path:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required for audio generation (apt install ffmpeg)")

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        segments: list[Path] = []
        counter = 0

        def speak(text: str, voice: str, rate: str = "+0%") -> Path:
            nonlocal counter
            counter += 1
            mp3, wav = tmp / f"{counter:04d}.mp3", tmp / f"{counter:04d}.wav"
            tts.synthesize(text, voice, mp3, rate=rate)
            _to_wav(mp3, wav)
            return wav

        pause_en, pause_hu, pause_gap = tmp / "p_en.wav", tmp / "p_hu.wav", tmp / "p_gap.wav"
        _silence(config.pause_after_en, pause_en)
        _silence(config.pause_after_hu, pause_hu)
        _silence(1.0, pause_gap)

        segments += [speak(f"Hungarian vocabulary, {word_list.id}.", config.voice_en), pause_gap]
        for card in word_list.cards:
            segments += [speak(card.front_en, config.voice_en), pause_en]
            segments += [speak(card.back_hu, config.voice_hu), pause_hu]
            if config.repeat_hu_slow:
                segments += [speak(card.back_hu, config.voice_hu, config.slow_rate), pause_hu]

        concat_list = tmp / "concat.txt"
        concat_list.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments))
        _ffmpeg(
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c:a", "libmp3lame", "-b:a", "64k",
            "-metadata", f"title=Hungarian vocabulary {word_list.id}",
            "-metadata", "artist=hungarian-vocab",
            str(out),
        )
    return out
