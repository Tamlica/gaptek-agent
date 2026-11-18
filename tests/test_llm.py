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


class _FakeClient:
    """Stands in for openai.AsyncOpenAI: returns canned text from chat.completions.create."""

    def __init__(self, content: str) -> None:
        from types import SimpleNamespace as NS

        async def create(**_: object) -> object:
            return NS(choices=[NS(message=NS(content=content), finish_reason="stop")])

        self.chat = NS(completions=NS(create=create))


async def test_json_in_prompt_fallback() -> None:
    from gaptek.agent.tester import Intent
    from gaptek.llm import _json_in_prompt

    fenced = (
        '```json\n{"pikiran": "ok", "perasaan": "tenang", "aksi": "tekan", "target": "E1"}\n```'
    )
    out, reason = await _json_in_prompt(_FakeClient(fenced), "m", "s", "u", Intent, 10)  # type: ignore[arg-type]
    assert out is not None and out.target == "E1" and reason == "stop"

    out, reason = await _json_in_prompt(
        _FakeClient("Saya tekan tombol hijau."), "m", "s", "u", Intent, 10
    )  # type: ignore[arg-type]
    assert out is None and reason == "invalid_json"
