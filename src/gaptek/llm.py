"""One structured-output call over several LLM providers.

A model is named "provider:model", e.g. "anthropic:claude-haiku-5-5", "openai:gpt-5-mini",
"ollama:qwen3:8b". A bare name ("claude-haiku-5-5") means anthropic.
Everything except anthropic goes through the OpenAI-compatible chat API.
"""

import json
import os
import re
from typing import TYPE_CHECKING, NamedTuple

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    import openai


class Provider(NamedTuple):
    base_url: str | None  # None: SDK default (OPENAI_BASE_URL env, else api.openai.com)
    key_env: str
    default_key: str | None = None  # for local servers that ignore the key


OPENAI_COMPATIBLE: dict[str, Provider] = {
    "openai": Provider(None, "OPENAI_API_KEY"),
    "gemini": Provider(
        "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"
    ),
    "openrouter": Provider("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "groq": Provider("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "deepseek": Provider("https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    "ollama": Provider("http://localhost:11434/v1", "OLLAMA_API_KEY", "ollama"),
}
PROVIDERS = ["anthropic", *OPENAI_COMPATIBLE]


def split_model(spec: str) -> tuple[str, str]:
    provider, sep, name = spec.partition(":")
    if not sep:
        return "anthropic", spec
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r} in {spec!r}; use one of {PROVIDERS}")
    return provider, name


async def structured[M: BaseModel](
    model: str, system: str, user: str, schema: type[M], max_tokens: int
) -> tuple[M | None, str]:
    """Ask `model` for an instance of `schema`. Returns (parsed or None, stop reason)."""
    provider, name = split_model(model)
    if provider == "anthropic":
        import anthropic

        resp = await anthropic.AsyncAnthropic().messages.parse(
            model=name,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        return resp.parsed_output, str(resp.stop_reason)

    import openai

    p = OPENAI_COMPATIBLE[provider]
    key = os.environ.get(p.key_env) or p.default_key
    if key is None:
        raise RuntimeError(f"{p.key_env} is not set (needed for {model!r})")
    base_url = os.environ.get(f"{provider.upper()}_BASE_URL") or p.base_url
    client = openai.AsyncOpenAI(api_key=key, base_url=base_url)
    try:
        completion = await client.chat.completions.parse(
            model=name,
            max_completion_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format=schema,
        )
    except openai.LengthFinishReasonError:
        return None, "length"
    except openai.ContentFilterFinishReasonError:
        return None, "content_filter"
    except (ValidationError, openai.BadRequestError):
        # Model or proxy (e.g. LiteLLM routers) ignored/rejected json_schema: ask in the prompt.
        return await _json_in_prompt(client, name, system, user, schema, max_tokens)
    choice = completion.choices[0]
    reason = "refusal" if choice.message.refusal else str(choice.finish_reason)
    return choice.message.parsed, reason


_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


async def _json_in_prompt[M: BaseModel](
    client: "openai.AsyncOpenAI",
    name: str,
    system: str,
    user: str,
    schema: type[M],
    max_tokens: int,
) -> tuple[M | None, str]:
    system += (
        "\n\nReply with ONLY one JSON object matching this JSON schema, no other text:\n"
        + json.dumps(schema.model_json_schema())
    )
    completion = await client.chat.completions.create(
        model=name,
        max_completion_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    choice = completion.choices[0]
    m = _JSON_OBJECT.search(choice.message.content or "")  # tolerate ```json fences / chatter
    try:
        return schema.model_validate_json(m[0] if m else ""), str(choice.finish_reason)
    except ValidationError:
        return None, "invalid_json"
