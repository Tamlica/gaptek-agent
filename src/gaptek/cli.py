"""gaptek CLI."""

import asyncio
import random
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from dotenv import find_dotenv, load_dotenv
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from gaptek.runner import Outcome

from gaptek.config import ConfigError, Persona, RunConfig, Task, load_persona, load_task

load_dotenv(find_dotenv(usecwd=True))  # real env vars win over .env

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.callback()
def main() -> None:
    """Simulate a non-technical Indonesian user testing a web app."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252


def _fail(e: Exception) -> None:
    console.print(f"[red]{e}[/red]")
    raise typer.Exit(1)


@app.command()
def observe(
    persona: Path = typer.Option(..., help="Persona YAML"),
    url: str = typer.Option(..., help="Page to observe"),
    seed: int = 0,
) -> None:
    """Print raw extracted elements next to what the persona perceives."""
    from gaptek.browser import open_session
    from gaptek.perception.extract import extract
    from gaptek.perception.filters import more_below, perceive, viewport
    from gaptek.perception.render import render

    try:
        p = load_persona(persona)
    except ConfigError as e:
        _fail(e)

    async def go() -> None:
        async with open_session(p.device) as s:
            await s.page.goto(url)
            snap = await extract(s.page)
        vw, vh = snap.viewport_w, snap.viewport_h
        raw = render(viewport(snap.elements), vw, vh).text
        seen = render(
            perceive(snap, p, random.Random(f"{seed}-perception")),
            vw,
            vh,
            hint_more_below=p.perception.scrolls_spontaneously and more_below(snap),
        ).text
        t = Table("RAW (unfiltered)", f"FILTERED ({p.name})", show_lines=False)
        t.add_row(raw, seen)
        console.print(t)

    from playwright.async_api import Error as PlaywrightError

    try:
        asyncio.run(go())
    except PlaywrightError as e:
        _fail(RuntimeError(f"cannot open {url}: {str(e).splitlines()[0]}"))


def _load(persona: Path, task: Path) -> tuple[Persona, Task]:
    try:
        return load_persona(persona), load_task(task)
    except ConfigError as e:
        _fail(e)
        raise  # unreachable; keeps mypy happy


def _print_outcome(o: "Outcome") -> None:
    console.print(f"[bold]{o.run.result}[/bold] after {o.run.steps} steps -> {o.run.run_dir}")
    if o.run.error:
        console.print(f"[red]run error: {o.run.error}[/red]")
    if o.analysis_error:
        console.print(f"[yellow]analysis skipped: {o.analysis_error}[/yellow]")
    console.print(f"report: {o.report}")


@app.command()
def run(
    persona: Path = typer.Option(..., help="Persona YAML"),
    task: Path = typer.Option(..., help="Task YAML"),
    seed: int = typer.Option(0, help="Seeds misclicks, typos and perception misses"),
    headed: bool = typer.Option(False, help="Show the browser window"),
    tester_model: str = typer.Option(RunConfig().tester_model),
    analyst_model: str = typer.Option(RunConfig().analyst_model),
    analyze: bool = typer.Option(True, help="Run the analyst after the session"),
) -> None:
    """Run one persona through one task, then analyze and write report.html."""
    from gaptek.runner import run_and_report

    p, t = _load(persona, task)
    cfg = RunConfig(
        seed=seed, headed=headed, tester_model=tester_model, analyst_model=analyst_model
    )
    _print_outcome(asyncio.run(run_and_report(p, t, cfg, analyze=analyze)))


@app.command()
def report(
    run_dir: Path,
    reanalyze: bool = typer.Option(False, help="Re-run the analyst even if findings exist"),
    analyst_model: str = typer.Option(RunConfig().analyst_model),
) -> None:
    """(Re)build report.html for a run, analyzing it first if needed."""
    from gaptek.analyst import analyze
    from gaptek.report import render_report

    if not (run_dir / "trace.jsonl").exists():
        _fail(FileNotFoundError(f"{run_dir}: no trace.jsonl, not a run directory"))
    if reanalyze or not (run_dir / "findings.json").exists():
        try:
            asyncio.run(analyze(run_dir, analyst_model))
        except Exception as e:
            console.print(f"[yellow]analysis skipped: {type(e).__name__}: {e}[/yellow]")
    console.print(f"report: {render_report(run_dir)}")


@app.command()
def batch(
    personas: Path = typer.Option(..., help="Directory of persona YAMLs"),
    task: Path = typer.Option(..., help="Task YAML"),
    runs_per_persona: int = typer.Option(3, min=1),
    seed: int = typer.Option(0, help="First seed; run i uses seed + i"),
    tester_model: str = typer.Option(RunConfig().tester_model),
    analyst_model: str = typer.Option(RunConfig().analyst_model),
    analyze: bool = typer.Option(True),
) -> None:
    """Run every persona N times and aggregate how often each screen causes trouble."""
    import json
    from datetime import datetime

    from gaptek.batch import aggregate
    from gaptek.runner import run_and_report

    files = sorted(personas.glob("*.yaml"))
    if not files:
        _fail(FileNotFoundError(f"no *.yaml in {personas}"))
    loaded = [_load(f, task) for f in files]
    out_dir = RunConfig().runs_dir / f"batch-{datetime.now():%Y%m%d-%H%M%S}"

    async def go() -> list[Path]:
        dirs = []
        # ponytail: sequential runs; parallelize with a semaphore if batches get slow
        for p, t in loaded:
            for i in range(runs_per_persona):
                cfg = RunConfig(
                    seed=seed + i,
                    tester_model=tester_model,
                    analyst_model=analyst_model,
                    runs_dir=out_dir,
                )
                o = await run_and_report(p, t, cfg, analyze=analyze)
                _print_outcome(o)
                dirs.append(o.run.run_dir)
        return dirs

    summary = aggregate(asyncio.run(go()))
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    table = Table("persona", "results")
    for persona_id, counts in summary["results_by_persona"].items():
        table.add_row(persona_id, ", ".join(f"{k}: {v}" for k, v in counts.items()))
    console.print(table)
    for line in summary["stuck_at"]:
        console.print(f"- {line}")
    for item in summary["issues_by_screen"]:
        console.print(f"- issues at {item['screen']} in {item['runs']} runs")
    console.print(f"summary: {out_dir / 'summary.json'}")


if __name__ == "__main__":
    app()
