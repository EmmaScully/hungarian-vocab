"""Load config.toml into typed settings."""

import tomllib
from pathlib import Path

from pydantic import BaseModel

DEFAULT_CONFIG = Path("config.toml")


class GeneralConfig(BaseModel):
    site_url: str = ""
    data_dir: Path = Path("data")
    build_dir: Path = Path("build")


class GeneratorConfig(BaseModel):
    n_words: int = 20
    review_ratio: float = 0.5
    topics: list[str] = []
    level: str = "beginner to lower-intermediate (CEFR A1–B1)"


class LLMConfig(BaseModel):
    provider: str = "claude"
    model: str = "claude-opus-5-5"
    effort: str = "low"


class AudioConfig(BaseModel):
    provider: str = "edge"
    voice_en: str = "en-GB-SoniaNeural"
    voice_hu: str = "hu-HU-NoemiNeural"
    pause_after_en: float = 1.5
    pause_after_hu: float = 3.0
    repeat_hu_slow: bool = True
    slow_rate: str = "-30%"


class NotifyConfig(BaseModel):
    email: bool = True
    telegram: bool = True


class Config(BaseModel):
    general: GeneralConfig = GeneralConfig()
    generator: GeneratorConfig = GeneratorConfig()
    llm: LLMConfig = LLMConfig()
    audio: AudioConfig = AudioConfig()
    notify: NotifyConfig = NotifyConfig()


def load_config(path: Path = DEFAULT_CONFIG) -> Config:
    if not path.exists():
        return Config()
    with path.open("rb") as f:
        return Config.model_validate(tomllib.load(f))
