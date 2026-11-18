# gaptek-agent

Usability QA that simulates a non-technical ("gaptek") Indonesian user trying to finish a task in
your web app, in a real browser. It finds friction that normal automated tests miss: jargon,
English labels, icon-only buttons, tiny text, unclear next steps.

Realism comes from **code constraints, not prompting**: the tester model only ever sees a filtered,
plain-Indonesian description of the screen. Words outside the persona's vocabulary become `???`,
icon-only buttons lose their hidden labels, small text may go unnoticed, long text is cut off, and
taps/typing get seeded fat-finger noise. A separate, stronger analyst model reads the trace afterwards
and writes findings for developers.

> Results are a simulation. Treat them as hypotheses to check with real people (see
> `docs/VALIDATION.md`).

## Setup

```bash
uv sync && uv run playwright install chromium
cp .env.example .env                  # then set models + API keys
```

### Models and providers

Models are named `provider:model` and set in `.env` (or the environment, or `--tester-model` /
`--analyst-model`):

```bash
GAPTEK_TESTER_MODEL=anthropic:claude-haiku-5-5   # small on purpose
GAPTEK_ANALYST_MODEL=anthropic:claude-opus-5-5   # strong
```

| Provider | Example model | Key |
|---|---|---|
| `anthropic` | `anthropic:claude-haiku-5-5` (bare names also mean anthropic) | `ANTHROPIC_API_KEY` |
| `openai` | `openai:gpt-5-mini` | `OPENAI_API_KEY` |
| `gemini` | `gemini:gemini-2.5-flash` | `GEMINI_API_KEY` |
| `openrouter` | `openrouter:meta-llama/llama-3.3-70b-instruct` | `OPENROUTER_API_KEY` |
| `groq` | `groq:llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| `deepseek` | `deepseek:deepseek-chat` | `DEEPSEEK_API_KEY` |
| `ollama` | `ollama:qwen3:8b` (local, no key) | - |

Everything except `anthropic` uses the OpenAI-compatible chat API with structured outputs, so the
model must support JSON-schema output. `<PROVIDER>_BASE_URL` overrides an endpoint;
`OPENAI_BASE_URL` points `openai:` at any other OpenAI-compatible server (vLLM, LM Studio...).

## Try it on the demo app

```bash
cd demo_app && python -m http.server 8000      # in another terminal
uv run gaptek observe --persona personas/bu-sri.yaml --url "http://localhost:8000/#/form"
uv run gaptek run --persona personas/bu-sri.yaml --task tasks/example.yaml --seed 1
uv run gaptek run --persona personas/kontrol-melek-teknologi.yaml --task tasks/example.yaml
```

`observe` needs no API key: it prints what is really on the page next to what the persona perceives.

Each run writes `runs/<timestamp>-<task>-<persona>-s<seed>/`:
`trace.jsonl`, `screenshots/step-NNN.png`, `run.json`, `findings.json`, `report.html`.

## Commands

```
gaptek observe --persona P --url U [--seed N]
gaptek run     --persona P --task T [--seed N] [--headed] [--tester-model M] [--analyst-model M] [--no-analyze]
gaptek report  <run_dir> [--reanalyze]
gaptek batch   --personas personas/ --task T [--runs-per-persona 3] [--seed N]
```

Defaults: tester `anthropic:claude-haiku-5-5`, analyst `anthropic:claude-opus-5-5` (see above).
The same `--seed` gives the same misclick / typo / missed-element decisions.

## Personas and tasks

Personas live in `personas/*.yaml`; every behavior knob (vocabulary, recognized icons, reading
limit, font-size threshold, miss rate, misclick/typo rates, patience) is there.
`kontrol-melek-teknologi` has no filters and no noise: if it fails, the flow or the success
criteria are broken, not the UX.

A task (`tasks/*.yaml`):

```yaml
id: order-food
url: http://localhost:5173
goal_for_persona: "Kamu mau pesan nasi goreng buat makan siang, terus bayar."
success:
  url_contains: "/order/success"   # and/or text_visible: "Pesanan berhasil"
progress_hints: ["/menu", "/cart", "/payment"]
max_steps: 40
```

Success is judged by the runner from the page, never by the tester's claim.

## Use from Claude Code (MCP)

```bash
claude mcp add gaptek --env GAPTEK_HOME=/path/to/gaptek-agent -- \
  uv --directory /path/to/gaptek-agent run gaptek-mcp
```

The server reads models and API keys from `$GAPTEK_HOME/.env`, so no `--env` keys are needed.

Tools: `list_personas`, `run_test(persona, task, seed?, analyze?)` (returns a `run_id` and runs in
the background; `task` is a YAML path or inline YAML), `get_findings(run_id)`.

For the guided workflow, copy the skill into your project or user skills:

```bash
cp -r skills/gaptek-test ~/.claude/skills/        # or <your-app>/.claude/skills/
```

Then ask Claude Code: *"test the checkout flow as Bu Sri"*.

## Development

```bash
uv run pytest            # unit tests + browser tests against demo_app (no API key needed)
uv run ruff check . && uv run ruff format .
uv run mypy src
```

Design: `docs/SPEC.md`. Validation protocol: `docs/VALIDATION.md`.
