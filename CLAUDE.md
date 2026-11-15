# CLAUDE.md — gaptek-agent

## What this project is
`gaptek-agent` is a usability QA tool that simulates a non-technical ("orang awam" / "gaptek") Indonesian user
trying to complete a task in a web app. It finds UX friction that normal automated tests miss.

Core idea: **realism comes from code constraints, not from prompting.** The tester LLM must be
mechanically limited in what it can perceive and do. Never rely on "pretend you don't understand" prompts alone.

Read before working:
- `docs/SPEC.md` — architecture, modules, data formats (source of truth)
- `docs/PLAN.md` — phased build plan with acceptance criteria. Work phase by phase; do not skip ahead.

## Stack
- Python 3.12, managed with `uv`
- Playwright (Python, async) for browser control
- Anthropic SDK for LLM calls (tester model and analyst model are configurable separately)
- Pydantic v2 for all configs and data models
- Typer for the CLI
- FastMCP for the MCP server (Phase 4)
- Jinja2 for HTML reports
- pytest + pytest-asyncio for tests

## Commands
- Install: `uv sync && uv run playwright install chromium`
- Run: `uv run gaptek run --persona personas/bu-sri.yaml --task tasks/example.yaml`
- Test: `uv run pytest`
- Lint/format: `uv run ruff check . && uv run ruff format .`
- Types: `uv run mypy src`

## Rules
- The tester agent must ONLY see the filtered observation produced by `perception/`. Never pass raw HTML,
  raw accessibility tree, URLs, or selectors to the tester model.
- The tester agent never receives the app's source code or any developer context.
- All persona behavior knobs live in persona YAML. No hardcoded persona logic in the agent loop.
- Randomness (misclicks, impatience) must be seeded via `--seed` so runs are reproducible.
- Every step is logged (observation, model reasoning, action, screenshot path) to the run directory.
- Keep modules small and pure where possible; perception filters must be unit-testable without a browser.
- User-facing persona text and reasoning are in Indonesian; code, comments, and docs are in English.
- Do not add features outside the current phase in `docs/PLAN.md`.
