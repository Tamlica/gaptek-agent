# gaptek-agent — Technical Spec

## 1. Goal
Given a **persona** and a **task** ("pesan makanan dan bayar pakai QRIS"), drive a real browser as that
persona would, and produce a **findings report**: where they got stuck, what confused them, whether they
gave up, with evidence (screenshots, step trace).

Non-goals (v1): native mobile apps, visual regression, load testing, replacing real user research.

## 2. Architecture

```
            ┌──────────────┐
 task.yaml ─┤              │
 persona ───┤  Runner      │──► run dir (trace.jsonl, screenshots/, report.html, findings.json)
            │  (loop)      │
            └──┬───────┬───┘
               │       │
     ┌─────────▼─┐   ┌─▼──────────────┐
     │ Browser   │   │ Tester Agent    │  weak/cheap model, persona prompt,
     │ (Playwright)  │ (LLM)           │  sees ONLY filtered observation
     └─────┬─────┘   └─▲──────┬───────┘
           │ raw page  │      │ intent ("tekan tombol hijau besar")
     ┌─────▼───────────┴┐   ┌─▼──────────────┐
     │ Perception Filter │   │ Action Executor │  resolves intent → element,
     │ (persona-limited) │   │ (+ behavior     │  applies misclick / hesitation
     └───────────────────┘   │   noise)        │
                             └────────────────┘
 After run:  Analyst (strong model) reads trace → findings.json + report.html
```

Two models, deliberately separated:
- **Tester**: plays the user. Constrained, ideally a smaller model (configurable).
  Tester and analyst may use different providers (see §8, Models).
- **Analyst**: reads the trace afterwards and writes developer-facing findings. Never acts.

## 3. Modules (`src/gaptek/`)

| Module | Responsibility |
|---|---|
| `config.py` | Pydantic models: `Persona`, `Task`, `RunConfig` |
| `browser.py` | Playwright session, device emulation (default: mid-range Android viewport), screenshots |
| `perception/extract.py` | Pull visible interactive + text elements from the page (bbox, text, role, color, size) |
| `perception/filters.py` | Pure functions applying persona limits to extracted elements |
| `perception/render.py` | Render filtered elements into the text observation the tester sees |
| `agent/tester.py` | Prompt build + LLM call → structured `Intent` |
| `agent/executor.py` | Map `Intent` to a real element; apply behavior noise; perform action |
| `agent/patience.py` | Patience/frustration budget state machine |
| `runner.py` | Main loop, stop conditions, trace writing |
| `analyst.py` | Post-run analysis → `findings.json` |
| `report.py` | Jinja2 HTML report |
| `llm.py` | One structured-output call over providers (Anthropic SDK; OpenAI SDK for OpenAI-compatible APIs) |
| `cli.py` | Typer CLI |
| `mcp_server.py` | FastMCP wrapper |

## 4. Perception filter (the core)

Input: list of `Element(id, role, text, aria_label, bbox, font_size, bg_color, is_icon_only, is_visible)`.
Output: list of `PerceivedElement(ref, description)` where `ref` is an opaque short id (e.g. `E7`).

Filters, each toggled/tuned from persona YAML:

1. **Vocabulary filter** — tokens not in persona vocabulary (base Indonesian list + persona `knows_words`)
   and in `unknown_terms` (e.g. login, OTP, sync, toggle, checkout, dashboard) become `???`.
   Matching is case-insensitive. Unknown English words are `???` unless whitelisted.
2. **Icon blindness** — icon-only elements lose aria-label/tooltip. Described only by shape/color/position
   ("ikon kecil abu-abu di pojok kanan atas"), unless icon is in persona `recognized_icons`
   (e.g. back arrow, WhatsApp, home).
3. **Reading limit** — text blocks truncated to `max_words_read` words, then "...".
4. **Salience** — small elements (font < `min_noticed_font_px` or area tiny) are dropped with probability
   `small_element_miss_rate`. Large, colored buttons are always kept and described as "tombol besar warna X".
5. **Scroll awareness** — only elements in the current viewport are shown; whether the persona thinks to scroll
   is controlled by `scrolls_spontaneously` (bool) + prompt.

Observation format given to tester (Indonesian, plain text):
```
Layar sekarang:
[E1] tulisan besar di atas: "Selamat datang di ???"
[E2] tombol besar hijau: "???"
[E3] ikon kecil abu-abu di pojok kanan atas
[E4] kotak isian kosong dengan tulisan samar: "Nomor ???"
Kamu sudah mencoba 2 kali di layar ini. Kesabaran: 3/5.
```

## 5. Tester agent

Structured output (Pydantic, via tool call or JSON):
```json
{
  "pikiran": "Saya tidak tahu ini apa, tapi tombol hijau kelihatan penting.",
  "perasaan": "bingung",          // tenang | bingung | ragu | kesal | takut | menyerah
  "aksi": "tekan",                // tekan | ketik | gulir | kembali | tunggu | menyerah | selesai
  "target": "E2",
  "teks": null
}
```
System prompt: persona background + task in their own words + rule that they only know what they see.
No mention of web development terms anywhere in the prompt.

## 6. Executor + behavior noise
- `misclick_rate`: with this probability, click the nearest neighbor element (by bbox distance) instead.
- `typo_rate`: per-character typo chance when typing.
- `hesitation`: logged only (no real delay needed) — counts toward time-on-screen metric.
- `kembali` uses browser back (gaptek users love the back button).

## 7. Patience model
- Start at `patience_max`. Decrease on: same screen after action (−1), error message seen (−1),
  `perasaan` in {kesal, takut} (−1). Increase +1 on visible progress (URL/screen change matching task hints).
- At 0 → forced `menyerah`. Also stop at `max_steps` or `selesai`.
- Success check: task YAML `success` criteria (URL pattern and/or visible text), evaluated by the runner,
  NOT by the tester's claim.

## 8. Config formats

Persona (`personas/*.yaml`) — see `personas/bu-sri.yaml`.

Task (`tasks/*.yaml`):
```yaml
id: order-food
url: http://localhost:5173
goal_for_persona: "Kamu mau pesan nasi goreng buat makan siang, terus bayar."
success:
  url_contains: "/order/success"
  # or text_visible: "Pesanan berhasil"
progress_hints: ["/menu", "/cart", "/payment"]
max_steps: 40
```

### Models and `.env`
Models are named `provider:model`; a bare name means `anthropic`. Providers: `anthropic` (native
SDK) and the OpenAI-compatible `openai`, `gemini`, `openrouter`, `groq`, `deepseek`, `ollama`
(table in `llm.py`; the model must support JSON-schema structured output).

| Variable | Purpose |
|---|---|
| `GAPTEK_TESTER_MODEL` | default tester model (`anthropic:claude-haiku-5-5`) |
| `GAPTEK_ANALYST_MODEL` | default analyst model (`anthropic:claude-opus-5-5`) |
| `<PROVIDER>_API_KEY` | key per provider, e.g. `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` (ollama needs none) |
| `<PROVIDER>_BASE_URL` | optional endpoint override; `OPENAI_BASE_URL` targets any OpenAI-compatible server |

The CLI loads `.env` from the current directory; the MCP server from `$GAPTEK_HOME/.env`.
Real environment variables win over `.env`; `--tester-model` / `--analyst-model` win over both.
See `.env.example`.

## 9. Outputs (`runs/<timestamp>-<task>-<persona>/`)
- `trace.jsonl` — one line per step: observation, tester output, executed action, noise applied, patience, screenshot path
- `screenshots/step-NNN.png`
- `findings.json`:
```json
{
  "result": "gave_up | success | max_steps",
  "steps": 23,
  "issues": [
    {"severity": "high", "step": 7, "screen": "/payment",
     "summary": "Term 'Verifikasi OTP' not understood; user retried 4x then pressed back",
     "evidence": ["step-007.png", "step-008.png"],
     "suggestion": "Use 'Masukkan kode dari SMS' and show where the SMS comes from"}
  ]
}
```
- `report.html` — timeline with screenshots, emotion strip, issues ranked by severity.

## 10. CLI
```
gaptek observe --persona P --url U [--seed N]
gaptek run --persona P --task T [--seed N] [--headed] [--tester-model M] [--analyst-model M] [--no-analyze]
gaptek batch --personas dir/ --task T --runs-per-persona 3
gaptek report <run_dir> [--reanalyze]
```

## 11. MCP
Tools: `list_personas`, `run_test(persona, task_yaml_or_inline)` (returns run_id, runs in background),
`get_findings(run_id)`. Plus a Claude Code skill `gaptek-test` that: writes a task YAML for the flow
the dev names, calls `run_test`, reads findings, proposes code fixes. The skill must not leak source code
into the tester.

## 12. Validation
A run is credible only if, on a reference flow, the tool finds ≥ the majority of issues found by
3–5 real non-technical people on the same flow. Track this in `docs/VALIDATION.md`.
