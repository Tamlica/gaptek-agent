# gaptek-agent

**Bahasa Indonesia** | [English](README.en.md)

Alat uji kegunaan (usability QA) yang mensimulasikan pengguna awam ("gaptek") Indonesia yang mencoba
menyelesaikan suatu tugas di aplikasi web kamu, dengan browser sungguhan. Alat ini menemukan hambatan
yang biasanya lolos dari tes otomatis biasa: istilah teknis, label berbahasa Inggris, tombol yang
cuma berupa ikon, tulisan terlalu kecil, dan langkah berikutnya yang tidak jelas.

Realisme datang dari **batasan di kode, bukan dari prompt**: model penguji hanya pernah melihat
deskripsi layar yang sudah difilter, dalam bahasa Indonesia sederhana. Kata di luar kosakata persona
berubah jadi `???`, tombol ikon kehilangan label tersembunyinya, tulisan kecil bisa tidak terlihat,
teks panjang dipotong, dan ketukan/ketikan diberi gangguan "jari gemuk" yang di-seed. Setelah sesi
selesai, model analis terpisah yang lebih kuat membaca jejak (trace) dan menulis temuan untuk
developer.

> Hasilnya adalah simulasi. Anggap sebagai hipotesis yang perlu dicek ke orang sungguhan (lihat
> `docs/VALIDATION.md`).

## Persiapan

```bash
uv sync && uv run playwright install chromium
cp .env.example .env                  # lalu isi model + API key
```

### Model dan provider

Model ditulis dengan format `provider:model` dan diatur di `.env` (atau environment variable, atau
`--tester-model` / `--analyst-model`):

```bash
GAPTEK_TESTER_MODEL=anthropic:claude-haiku-5-5   # sengaja model kecil
GAPTEK_ANALYST_MODEL=anthropic:claude-opus-5-5   # model kuat
```

| Provider | Contoh model | Key |
|---|---|---|
| `anthropic` | `anthropic:claude-haiku-5-5` (nama tanpa provider juga berarti anthropic) | `ANTHROPIC_API_KEY` |
| `openai` | `openai:gpt-5-mini` | `OPENAI_API_KEY` |
| `gemini` | `gemini:gemini-2.5-flash` | `GEMINI_API_KEY` |
| `openrouter` | `openrouter:meta-llama/llama-3.3-70b-instruct` | `OPENROUTER_API_KEY` |
| `groq` | `groq:llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| `deepseek` | `deepseek:deepseek-chat` | `DEEPSEEK_API_KEY` |
| `ollama` | `ollama:qwen3:8b` (lokal, tanpa key) | - |

Semua selain `anthropic` memakai chat API yang kompatibel dengan OpenAI dengan structured output,
jadi modelnya harus mendukung output JSON schema. `<PROVIDER>_BASE_URL` mengganti endpoint;
`OPENAI_BASE_URL` mengarahkan `openai:` ke server lain yang kompatibel dengan OpenAI (vLLM,
LM Studio, ...).

## Coba di aplikasi demo

```bash
cd demo_app && python -m http.server 8000      # di terminal lain
uv run gaptek observe --persona personas/bu-sri.yaml --url "http://localhost:8000/#/form"
uv run gaptek run --persona personas/bu-sri.yaml --task tasks/example.yaml --seed 1
uv run gaptek run --persona personas/kontrol-melek-teknologi.yaml --task tasks/example.yaml
```

`observe` tidak butuh API key: perintah ini menampilkan isi halaman yang sebenarnya berdampingan
dengan apa yang dilihat persona.

Setiap run menulis `runs/<timestamp>-<task>-<persona>-s<seed>/`:
`trace.jsonl`, `screenshots/step-NNN.png`, `run.json`, `findings.json`, `report.html`.

## Perintah

```
gaptek observe --persona P --url U [--seed N]
gaptek run     --persona P --task T [--seed N] [--headed] [--tester-model M] [--analyst-model M] [--no-analyze]
gaptek report  <run_dir> [--reanalyze]
gaptek batch   --personas personas/ --task T [--runs-per-persona 3] [--seed N]
```

Default: penguji `anthropic:claude-haiku-5-5`, analis `anthropic:claude-opus-5-5` (lihat di atas).
`--seed` yang sama menghasilkan keputusan salah-pencet / salah-ketik / elemen-terlewat yang sama.

## Persona dan tugas

Persona ada di `personas/*.yaml`; semua pengaturan perilaku (kosakata, ikon yang dikenali, batas
membaca, ambang ukuran huruf, peluang terlewat, peluang salah pencet/salah ketik, kesabaran) ada di
sana. `kontrol-melek-teknologi` tidak punya filter dan gangguan: kalau persona ini gagal, berarti
alur atau kriteria suksesnya yang rusak, bukan UX-nya.

Contoh tugas (`tasks/*.yaml`):

```yaml
id: order-food
url: http://localhost:5173
goal_for_persona: "Kamu mau pesan nasi goreng buat makan siang, terus bayar."
success:
  url_contains: "/order/success"   # dan/atau text_visible: "Pesanan berhasil"
progress_hints: ["/menu", "/cart", "/payment"]
max_steps: 40
```

Keberhasilan dinilai oleh runner dari halaman, bukan dari pengakuan model penguji.

## Pakai dari Claude Code (MCP)

```bash
claude mcp add gaptek --env GAPTEK_HOME=/path/to/gaptek-agent -- \
  uv --directory /path/to/gaptek-agent run gaptek-mcp
```

Server membaca model dan API key dari `$GAPTEK_HOME/.env`, jadi tidak perlu memasukkan key lewat
`--env`.

Tools: `list_personas`, `run_test(persona, task, seed?, analyze?)` (mengembalikan `run_id` dan
berjalan di latar belakang; `task` berupa path YAML atau YAML langsung), `get_findings(run_id)`.

Untuk alur kerja terpandu, salin skill ke project atau skill pengguna kamu:

```bash
cp -r skills/gaptek-test ~/.claude/skills/        # atau <aplikasi-kamu>/.claude/skills/
```

Lalu minta ke Claude Code: *"tes alur checkout sebagai Bu Sri"*.

## Pengembangan

```bash
uv run pytest            # unit test + tes browser ke demo_app (tanpa API key)
uv run ruff check . && uv run ruff format .
uv run mypy src
```

Desain: `docs/SPEC.md`. Protokol validasi: `docs/VALIDATION.md`.

## Lisensi

[MIT](LICENSE)
