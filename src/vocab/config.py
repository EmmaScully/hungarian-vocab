"""Load config.toml into typed settings."""

import tomllib
from datetime import time
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
    provider: str = "gemini"
    model: str = "gemini-3.8-flash"
    fallback_models: list[str] = []
    effort: str = "low"


class AudioConfig(BaseModel):
    provider: str = "edge"
    voice_en: str = "en-GB-SoniaNeural"
    voice_hu: str = "hu-HU-NoemiNeural"
    pause_after_en: float = 2.0
    pause_after_hu: float = 2.0
    hu_rate: str = "-30%"


class SentencesConfig(BaseModel):
    n: int = 10


class WritingConfig(BaseModel):
    level: str = "B1–B2"
    short_questions: int = 4
    long_questions: int = 2


class ScheduleConfig(BaseModel):
    # Scheduled runs only generate a default list if none was made by hand by this local time.
    timezone: str = "Australia/Melbourne"
    deadline: time = time(21, 0)


class NotifyConfig(BaseModel):
    email: bool = True
    telegram: bool = False


class Config(BaseModel):
    general: GeneralConfig = GeneralConfig()
    generator: GeneratorConfig = GeneratorConfig()
    llm: LLMConfig = LLMConfig()
    audio: AudioConfig = AudioConfig()
    sentences: SentencesConfig = SentencesConfig()
    writing: WritingConfig = WritingConfig()
    schedule: ScheduleConfig = ScheduleConfig()
    notify: NotifyConfig = NotifyConfig()


def load_config(path: Path = DEFAULT_CONFIG) -> Config:
    if not path.exists():
        return Config()
    with path.open("rb") as f:
        return Config.model_validate(tomllib.load(f))
