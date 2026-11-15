# Changelog

## Phase 0 — Scaffold (2026-11-15)
- uv project (Python 3.12), package `src/gaptek/`, ruff / mypy (strict) / pytest config.
- `config.py`: `Persona`, `Task`, `RunConfig` models with `extra="forbid"`; `load_persona` / `load_task`
  raise `ConfigError` naming the file and each bad field (typo'd keys, out-of-range rates, missing fields, bad YAML).
- Moved `PLAN.md`/`SPEC.md` into `docs/`, `bu-sri.yaml` into `personas/`; added `tasks/example.yaml`.
- `demo_app/index.html`: hash-routed menu → form → success. Traps: "Checkout" button, "Verifikasi OTP" jargon,
  icon-only header "Settings" and "Resend OTP" buttons, icon-only floating submit, tiny 11px hint text,
  English `alert("Field required")`. Run: `cd demo_app && python -m http.server 8000`.
- Deps kept to pydantic + pyyaml; Playwright / Anthropic / Typer get added in the phase that needs them.

## Phase 1 — Perception (2026-11-15)
- `perception/extract.py`: one `page.evaluate` returns visible interactive + text elements (bbox, text,
  aria-label/title, placeholder, value, font size, bg/fg color, roundness, icon-only flag, icon hint,
  in-viewport) and tags each with `data-gaptek-id` for the executor.
- `perception/filters.py` (pure, seeded): viewport -> salience -> icon blindness -> reading limit ->
  vocabulary. Vocabulary precedence: `knows_words` > `unknown_terms` > base Indonesian list >
  curated English UI list (`perception/data/*.txt`). Consecutive `???` collapse into one.
- `perception/render.py`: SPEC §4 observation text, top-to-bottom order; `refs` (E1 -> element id)
  never shown to the tester. `perception/colors.py`: rgb -> Indonesian color name.
- New persona knob `perception.icon_blindness` (default true) so the control persona can turn it off.
- `gaptek observe`: raw vs filtered side by side. On the demo form: "Verifikasi OTP" -> `???`,
  submit -> "tombol bulat biru di pojok kanan bawah" with no label, 11px hint often unnoticed.

## Phase 2 — Agent loop (2026-11-15)
- `agent/tester.py`: Indonesian persona system prompt (no web-dev terms, tested), structured
  `Intent` via `messages.parse`. The runner depends only on a `Decide` callable, so tests drive the
  real browser loop with scripted testers.
- `agent/executor.py`: misclick = nearest other tappable element by bbox center; per-char QWERTY-
  neighbor typos; seeded draws per tap/char so same seed + same actions -> same noise. Perception and
  noise use separate seeded RNG streams.
- `agent/patience.py`: SPEC §7 rules, reasons logged per step.
- `runner.py`: runner-side success check (url and/or text), `false_done` when the tester claims
  success wrongly, alert() texts captured and shown as "Muncul pesan", `trace.jsonl` + screenshots +
  `run.json`. API/network failures end the run as `error` with the partial trace kept.
- Control persona `personas/kontrol-melek-teknologi.yaml` (no filters, no noise).
- Not verified with a live LLM yet (no API key in the build environment): "Bu Sri usually
  struggles / control succeeds" is shown with scripted testers only.

## Phase 3 — Analysis & report (2026-11-15)
- `analyst.py`: analyst model gets raw + perceived screen per step and the persona's thoughts;
  structured `findings.json` (SPEC §9 + `summary`, `simulated: true`). Issues citing non-existent
  steps are dropped; evidence limited to screenshots that exist.
- `report.py` + `templates/report.html.j2`: simulation banner, emotion strip, ranked issues with
  evidence thumbnails, timeline with what the persona saw vs what was really there.
- `gaptek report <run_dir>` (analyzes if needed), `gaptek batch` (+ `batch.py` aggregate:
  results per persona, "N/M runs ended without success at <screen>", issues by screen).

## Phase 4 — MCP + skill (2026-11-15)
- `mcp_server.py` on `mcp` 2.x `MCPServer` (FastMCP's new name): `list_personas`,
  `run_test` (background asyncio task, task as YAML path or inline YAML), `get_findings`
  (also serves runs from earlier sessions). Verified over a real stdio client handshake.
- `skills/gaptek-test/SKILL.md`, README with `claude mcp add` setup.

## Phase 5 — Validation & polish (started 2026-11-15)
- Personas: `pak-harjo-pensiunan`, `rina-remaja-hp-murah`, `bu-yati-pedagang-umkm`.
- `docs/VALIDATION.md`: protocol + empty results table. Real-user validation and filter tuning
  need real people and a real app; not done.
- Not started (PLAN "later"): network throttling, React Native via Maestro, CI GitHub Action.

## Independent review fixes (2026-11-15)
A separate reviewer agent audited phases 0–4 against SPEC/PLAN/CLAUDE.md. Confirmed clean: only
filtered text reaches the tester; per-step logging; seeded, separate RNG streams. Fixed:
- Perception leaks: screen-reader-only text inside icon buttons, elements under `opacity:0`
  ancestors, inside collapsed `overflow:hidden` containers, or covered by an overlay
  (`elementFromPoint`); icon-font ligatures ("arrow_back") now count as icons; app-prefilled input
  values go through the vocabulary filter; controls inside clickable cards are no longer dropped.
- Reading order groups vertically overlapping elements into rows (labels stay next to their buttons).
- `kembali` on the first screen / external links: the app is reopened (`left_app` in trace, counts
  as an error for patience) instead of stranding the persona on about:blank.
- Misclicks only land within 48px of the target, else the tap hits nothing.
- `ketik` replaces the field's content so a typo can be corrected by retyping.
- After every action the runner waits for load (`networkidle`, 5s cap); signature reads retry
  after a mid-navigation failure.
- Run dirs get a random suffix (no collisions between concurrent MCP runs); `steps` = tester turns.
- `prefers` is a `Literal`; `observe` reports unreachable URLs cleanly; `list_personas` lists broken
  files instead of failing; `get_findings` reports interrupted runs as `incomplete`.
- Known gaps left open: choosing `<select>` options, deciding on `confirm()` dialogs (always
  accepted), images are not perceived at all, analyst doesn't validate `screen`.
