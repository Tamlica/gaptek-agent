# gaptek-agent — Build Plan

Work strictly phase by phase. Each phase ends with its acceptance criteria passing and a short
note appended to `docs/CHANGELOG.md`. Ask the user before starting the next phase.

---

## Phase 0 — Scaffold (½ day)
- `uv init`, package `src/gaptek/`, ruff, mypy, pytest config
- Pydantic models in `config.py` for Persona, Task, RunConfig; load + validate YAML
- Copy `personas/bu-sri.yaml`; create `tasks/example.yaml`
- Tiny demo target app in `demo_app/` (single static HTML/JS site, 3 screens: menu → form with
  "Verifikasi OTP" + icon-only buttons → success). Deliberately has jargon and an icon-only submit.
  Serve with `python -m http.server`.

**Done when:** `uv run pytest` passes, invalid YAML gives a clear error, demo app runs locally.

## Phase 1 — Perception (1–2 days) ← most important phase
- `perception/extract.py`: Playwright JS evaluation returning visible elements with bbox, text, role,
  aria-label, font size, computed bg color, icon-only flag
- `perception/filters.py`: vocabulary, icon blindness, reading limit, salience (seeded RNG)
- `perception/render.py`: Indonesian observation text exactly like SPEC §4
- Color naming helper (rgb → "hijau", "merah", "biru", "abu-abu", ...)
- CLI debug command: `gaptek observe --persona P --url U` prints raw vs filtered side by side

**Done when:** unit tests cover each filter without a browser (fixture element lists);
`gaptek observe` on demo app shows "Verifikasi OTP" as `???` and the icon submit with no label.

## Phase 2 — Agent loop (2 days)
- `agent/tester.py` with structured output + persona system prompt
- `agent/executor.py` with misclick/typo noise, back button
- `agent/patience.py` state machine
- `runner.py` loop, stop conditions, runner-side success check, `trace.jsonl` + screenshots
- `gaptek run` command, `--headed`, `--seed`

**Done when:** on demo app, Bu Sri persona usually fails or struggles at the OTP screen;
a "tech-savvy" control persona (`personas/kontrol-melek-teknologi.yaml`, no filters) succeeds.
Same seed → same noise decisions.

## Phase 3 — Analysis & report (1–2 days)
- `analyst.py`: strong model reads trace, outputs `findings.json` (schema in SPEC §9), each issue must cite steps
- `report.py`: HTML report (timeline, screenshots, emotion strip, ranked issues)
- `gaptek batch`: multiple personas × N runs, aggregate issue frequency ("4/6 runs stuck at /payment")

**Done when:** report on demo app lists the OTP jargon and icon-only button as high severity with evidence.

## Phase 4 — MCP + Claude Code skill (1 day)
- `mcp_server.py` with FastMCP (tools in SPEC §11), background runs
- `skills/gaptek-test/SKILL.md` for Claude Code
- README with setup for Claude Code (`claude mcp add ...`)

**Done when:** from Claude Code, "test the checkout flow as Bu Sri" runs end to end and returns findings.

## Phase 5 — Validation & polish (ongoing)
- Run on one real app (MakanMap) and compare to 3–5 real non-technical people → `docs/VALIDATION.md`
- Tune filters/persona defaults based on mismatches
- More personas: bapak pensiunan, remaja HP murah + sinyal lemah, pedagang UMKM
- Later: network throttling persona, React Native via Maestro, CI GitHub Action

---

## Risks to watch
- **Model too smart despite filters** → tighten filters, use smaller tester model, lower `max_words_read`.
- **Flaky element resolution** → stable element refs per observation, re-extract after every action.
- **Cost** → tester on cheap model, cap `max_steps`, cache nothing secret.
- **Fake confidence in results** → report always states it is a simulation; Phase 5 validation is mandatory before sharing claims publicly.
