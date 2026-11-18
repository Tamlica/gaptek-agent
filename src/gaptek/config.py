"""Pydantic models for persona, task and run config, plus YAML loading."""

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class _Strict(BaseModel):
    # Typos in YAML keys must fail loudly, not silently fall back to defaults.
    model_config = ConfigDict(extra="forbid")


class Vocabulary(_Strict):
    base: str = "indonesian_common"
    knows_words: list[str] = []
    unknown_terms: list[str] = []
    unknown_english_default: bool = True


class Perception(_Strict):
    vocabulary: Vocabulary = Vocabulary()
    icon_blindness: bool = True  # icon-only elements lose their hidden label
    recognized_icons: list[str] = []
    max_words_read: int = Field(default=6, ge=1)
    min_noticed_font_px: float = Field(default=14, ge=0)
    small_element_miss_rate: float = Field(default=0.0, ge=0, le=1)
    scrolls_spontaneously: bool = False


class Behavior(_Strict):
    misclick_rate: float = Field(default=0.0, ge=0, le=1)
    typo_rate: float = Field(default=0.0, ge=0, le=1)
    # new values need a matching sentence in agent/tester.py _PREFERS
    prefers: Literal["big_colorful_buttons"] | None = None
    uses_back_button_when_confused: bool = False


class Patience(_Strict):
    patience_max: int = Field(default=5, ge=1)
    max_steps: int = Field(default=40, ge=1)


class Persona(_Strict):
    id: str
    name: str
    background: str
    language: Literal["id"] = "id"
    device: str = "android_midrange"
    perception: Perception = Perception()
    behavior: Behavior = Behavior()
    patience: Patience = Patience()
    tester_prompt_notes: str = ""


class SuccessCriteria(_Strict):
    url_contains: str | None = None
    text_visible: str | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> "SuccessCriteria":
        if not (self.url_contains or self.text_visible):
            raise ValueError("success needs url_contains and/or text_visible")
        return self


class Task(_Strict):
    id: str
    url: str
    goal_for_persona: str
    success: SuccessCriteria
    progress_hints: list[str] = []
    max_steps: int = Field(default=40, ge=1)


class RunConfig(_Strict):
    seed: int = 0
    headed: bool = False
    # "provider:model" (see llm.py); overridable via env / .env
    tester_model: str = Field(
        default_factory=lambda: os.environ.get("GAPTEK_TESTER_MODEL", "anthropic:claude-haiku-5-5")
    )
    analyst_model: str = Field(
        default_factory=lambda: os.environ.get("GAPTEK_ANALYST_MODEL", "anthropic:claude-opus-5-5")
    )
    runs_dir: Path = Path("runs")


class ConfigError(Exception):
    """Raised when a YAML config file is missing, malformed, or fails validation."""


def _load[M: BaseModel](path: Path, model: type[M]) -> M:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except OSError as e:
        raise ConfigError(f"{path}: cannot read file ({e.strerror})") from e
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: invalid YAML\n{e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping at top level, got {type(data).__name__}")
    try:
        return model.model_validate(data)
    except ValidationError as e:
        lines = [
            f"  - {'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
            for err in e.errors()
        ]
        raise ConfigError(f"{path}: invalid {model.__name__}\n" + "\n".join(lines)) from e


def load_persona(path: Path) -> Persona:
    return _load(path, Persona)


def load_task(path: Path) -> Task:
    return _load(path, Task)
