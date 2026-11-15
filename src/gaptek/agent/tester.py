"""Tester LLM: plays the persona. Sees only the filtered observation text."""

from collections.abc import Awaitable, Callable, Sequence
from typing import Literal

import anthropic
from pydantic import BaseModel

from gaptek.config import Persona, Task

Feeling = Literal["tenang", "bingung", "ragu", "kesal", "takut", "menyerah"]
Action = Literal["tekan", "ketik", "gulir", "kembali", "tunggu", "menyerah", "selesai"]


class Intent(BaseModel):
    pikiran: str
    perasaan: Feeling
    aksi: Action
    target: str | None = None
    teks: str | None = None


# (observation text, history lines) -> intent. The runner only depends on this shape,
# so tests can plug in a scripted tester.
Decide = Callable[[str, Sequence[str]], Awaitable[Intent]]

_PREFERS = {
    "big_colorful_buttons": "Kamu lebih percaya tombol yang besar dan berwarna.",
}


def system_prompt(persona: Persona, task: Task) -> str:
    habits = []
    if persona.behavior.prefers in _PREFERS:
        habits.append(_PREFERS[persona.behavior.prefers])
    if persona.behavior.uses_back_button_when_confused:
        habits.append("Kalau bingung, kamu biasanya pencet tombol kembali.")
    if not persona.perception.scrolls_spontaneously:
        habits.append("Kamu jarang terpikir untuk menggeser layar ke bawah.")
    habit_text = "\n".join(f"- {h}" for h in habits)
    return f"""Kamu adalah {persona.name}. {persona.background.strip()}

{persona.tester_prompt_notes.strip()}

Kebiasaanmu:
{habit_text}

Yang mau kamu lakukan sekarang di HP: {task.goal_for_persona}

Cara kerjanya:
- Setiap kali, kamu diberi tahu apa yang kamu lihat di "Layar sekarang". Kamu hanya tahu itu saja.
- Tulisan "???" artinya kamu tidak bisa membaca atau tidak paham kata itu. Jangan menebak artinya
  seolah-olah kamu paham.
- Pilih satu aksi: tekan (pencet sesuatu), ketik (tulis di kotak isian),
  gulir (geser layar ke bawah), kembali (tombol kembali di HP), tunggu,
  menyerah (kalau sudah tidak sanggup), atau selesai
  (kalau kamu yakin yang kamu mau sudah berhasil).
- Untuk tekan dan ketik, isi "target" dengan kode dalam kurung siku, misalnya E2.
  Untuk ketik, isi "teks" dengan yang mau kamu tulis; isi kotak yang lama akan terganti.
- "pikiran" ditulis seperti bicara dalam hati, pendek, bahasa sehari-hari.
- "perasaan" salah satu dari: tenang, bingung, ragu, kesal, takut, menyerah."""


def user_prompt(observation: str, history: Sequence[str]) -> str:
    past = "\n".join(history[-6:]) or "(belum ada, baru mulai)"
    return (
        f"Yang sudah kamu lakukan tadi:\n{past}\n\n{observation}\n\nApa yang kamu lakukan sekarang?"
    )


class Tester:
    def __init__(self, persona: Persona, task: Task, model: str) -> None:
        self.system = system_prompt(persona, task)
        self.model = model
        self.client = anthropic.AsyncAnthropic()

    async def decide(self, observation: str, history: Sequence[str]) -> Intent:
        resp = await self.client.messages.parse(
            model=self.model,
            max_tokens=4000,
            system=self.system,
            messages=[{"role": "user", "content": user_prompt(observation, history)}],
            output_format=Intent,
        )
        if resp.parsed_output is None:  # refusal / truncated: treat as a confused pause
            return Intent(
                pikiran=f"(tidak ada jawaban: {resp.stop_reason})",
                perasaan="bingung",
                aksi="tunggu",
            )
        return resp.parsed_output
