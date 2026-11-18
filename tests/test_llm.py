import pytest

from gaptek.config import RunConfig
from gaptek.llm import split_model, structured


def test_split_model() -> None:
    assert split_model("claude-haiku-5-5") == ("anthropic", "claude-haiku-5-5")
    assert split_model("anthropic:claude-opus-5-5") == ("anthropic", "claude-opus-5-5")
    assert split_model("openai:gpt-5-mini") == ("openai", "gpt-5-mini")
    assert split_model("ollama:qwen3:8b") == ("ollama", "qwen3:8b")
    with pytest.raises(ValueError, match="unknown provider"):
        split_model("mistral:large")


def test_models_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GAPTEK_TESTER_MODEL", "gemini:gemini-2.5-flash")
    monkeypatch.delenv("GAPTEK_ANALYST_MODEL", raising=False)
    cfg = RunConfig()
    assert cfg.tester_model == "gemini:gemini-2.5-flash"
    assert cfg.analyst_model == "anthropic:claude-opus-5-5"


async def test_missing_key_is_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
        await structured("openai:gpt-5-mini", "s", "u", RunConfig, 10)
