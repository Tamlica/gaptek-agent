"""MCP server (SPEC §11). Runs happen in the background; poll get_findings.

mcp 2.x renamed FastMCP to MCPServer; same decorator API.
"""

import asyncio
import os
from pathlib import Path
from typing import Any

import yaml
from mcp.server.mcpserver import MCPServer

from gaptek.config import ConfigError, Persona, RunConfig, Task, load_persona, load_task
from gaptek.runner import new_run_dir, run_and_report

HOME = Path(os.environ.get("GAPTEK_HOME", ".")).resolve()
PERSONAS = HOME / "personas"

mcp = MCPServer(
    "gaptek",
    instructions=(
        "Usability tests that simulate non-technical Indonesian users in a real browser. "
        "Call list_personas, then run_test (returns a run_id immediately), then poll "
        "get_findings(run_id) until status is 'done'. Never put app source code in the task."
    ),
)

_runs: dict[str, dict[str, Any]] = {}
_tasks: set[asyncio.Task[None]] = set()  # strong refs so background runs aren't GC'd


def _resolve_persona(persona: str) -> Persona:
    path = Path(persona)
    if not path.suffix:
        path = PERSONAS / f"{persona}.yaml"
    elif not path.is_absolute():
        path = HOME / path
    return load_persona(path)


def _resolve_task(task: str) -> Task:
    """`task` is a path to a task YAML, or the YAML text itself."""
    path = Path(task) if "\n" not in task else None
    if path is not None and not path.is_absolute():
        path = HOME / path
    if path is not None and path.is_file():
        return load_task(path)
    data = yaml.safe_load(task)
    if not isinstance(data, dict):
        raise ConfigError(f"task is neither an existing file nor inline YAML: {task[:80]!r}")
    return Task.model_validate(data)


@mcp.tool()
def list_personas() -> list[dict[str, str]]:
    """List available personas (id, name, background). Broken files are listed with an error."""
    out = []
    for f in sorted(PERSONAS.glob("*.yaml")):
        try:
            p = load_persona(f)
        except ConfigError as e:
            out.append({"id": f.stem, "error": str(e)})
            continue
        out.append({"id": p.id, "name": p.name, "background": p.background.strip()})
    return out


@mcp.tool()
async def run_test(persona: str, task: str, seed: int = 0, analyze: bool = True) -> dict[str, str]:
    """Start a usability run in the background and return its run_id.

    persona: persona id (e.g. "bu-sri") or path to a persona YAML.
    task: path to a task YAML, or inline task YAML with keys id, url, goal_for_persona
          (in Indonesian, as the persona would say it), success (url_contains and/or
          text_visible), optional progress_hints and max_steps.
    """
    try:
        p, t = _resolve_persona(persona), _resolve_task(task)
    except (ConfigError, ValueError, yaml.YAMLError) as e:
        raise ValueError(str(e)) from e
    cfg = RunConfig(seed=seed, runs_dir=HOME / "runs")
    run_dir = new_run_dir(cfg, t, p)
    run_id = run_dir.name
    _runs[run_id] = {"status": "running", "run_dir": str(run_dir)}

    async def go() -> None:
        try:
            o = await run_and_report(p, t, cfg, analyze=analyze, run_dir=run_dir)
            _runs[run_id] |= {
                "status": "done",
                "result": o.run.result,
                "steps": o.run.steps,
                "report": str(o.report),
                "analysis_error": o.analysis_error,
            }
        except Exception as e:
            _runs[run_id] |= {"status": "error", "error": f"{type(e).__name__}: {e}"}

    bg = asyncio.create_task(go())
    _tasks.add(bg)
    bg.add_done_callback(_tasks.discard)
    return {"run_id": run_id, "status": "running"}


@mcp.tool()
def get_findings(run_id: str) -> dict[str, Any]:
    """Status of a run; when done, includes result, findings and the report path."""
    info = _runs.get(run_id)
    if info is None:
        rd = HOME / "runs" / run_id  # also serve runs from earlier server sessions
        if (rd / "run.json").exists():
            info = {"status": "done", "run_dir": str(rd), "report": str(rd / "report.html")}
        elif (rd / "trace.jsonl").exists():
            info = {
                "status": "incomplete",
                "run_dir": str(rd),
                "error": "run did not finish (server stopped?); partial trace.jsonl only",
            }
        else:
            raise ValueError(f"unknown run_id {run_id!r}")
    out = dict(info)
    f = Path(info["run_dir"]) / "findings.json"
    if info["status"] == "done" and f.exists():
        import json

        out["findings"] = json.loads(f.read_text(encoding="utf-8"))
    return out


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
