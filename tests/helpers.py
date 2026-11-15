from pathlib import Path
from typing import Any

from gaptek.config import Persona, load_persona
from gaptek.perception.extract import Element

ROOT = Path(__file__).parent.parent


def el(id: int = 0, **kw: Any) -> Element:
    base: dict[str, Any] = {"kind": "text", "x": 10, "y": 100, "w": 200, "h": 40, "font_size": 16}
    return Element(id=id, **(base | kw))


def bu_sri() -> Persona:
    return load_persona(ROOT / "personas/bu-sri.yaml")
