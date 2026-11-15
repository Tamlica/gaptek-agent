from pathlib import Path

import pytest

from gaptek.config import ConfigError, load_persona, load_task

ROOT = Path(__file__).parent.parent


def test_bundled_configs_load() -> None:
    p = load_persona(ROOT / "personas/bu-sri.yaml")
    assert p.perception.max_words_read == 6
    assert "otp" in p.perception.vocabulary.unknown_terms
    t = load_task(ROOT / "tasks/example.yaml")
    assert t.success.url_contains == "#/success"


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("id: x\nname: [unclosed", "invalid YAML"),
        ("- just\n- a list", "expected a mapping"),
        ("id: x\nname: X\nbackground: b\nbehavior:\n  misclick_rate: 2", "behavior.misclick_rate"),
        ("id: x\nname: X\nbackground: b\nperceptoin: {}", "perceptoin"),  # typo'd key
        ("id: x\nname: X", "background"),  # missing required
    ],
)
def test_invalid_persona_gives_clear_error(tmp_path: Path, content: str, expected: str) -> None:
    f = tmp_path / "p.yaml"
    f.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError, match=expected):
        load_persona(f)


def test_task_requires_success_criterion(tmp_path: Path) -> None:
    f = tmp_path / "t.yaml"
    f.write_text("id: t\nurl: http://x\ngoal_for_persona: g\nsuccess: {}", encoding="utf-8")
    with pytest.raises(ConfigError, match="url_contains and/or text_visible"):
        load_task(f)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot read"):
        load_persona(tmp_path / "nope.yaml")


@pytest.mark.parametrize("f", sorted((ROOT / "personas").glob("*.yaml")), ids=lambda p: p.stem)
def test_all_personas_load(f: Path) -> None:
    assert load_persona(f).id == f.stem
