import asyncio
from collections.abc import Sequence
from pathlib import Path

import pytest

from gaptek import mcp_server
from gaptek.agent.tester import Intent


def test_list_personas() -> None:
    ids = {p["id"] for p in mcp_server.list_personas()}
    assert {"bu-sri", "kontrol-melek-teknologi"} <= ids


async def test_tools_are_registered() -> None:
    names = {t.name for t in await mcp_server.mcp.list_tools()}
    assert names == {"list_personas", "run_test", "get_findings"}


async def test_run_test_background_inline_task(
    demo_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def gives_up(obs: str, history: Sequence[str]) -> Intent:
        return Intent(pikiran="tidak paham", perasaan="menyerah", aksi="menyerah")

    real = mcp_server.run_and_report

    async def fake_run_and_report(*a, **kw):  # type: ignore[no-untyped-def]
        return await real(*a, **(kw | {"decide": gives_up}))

    monkeypatch.setattr(mcp_server, "run_and_report", fake_run_and_report)
    monkeypatch.setattr(mcp_server, "HOME", tmp_path)

    inline = f"""
id: inline
url: {demo_url}
goal_for_persona: Pesan nasi goreng.
success: {{url_contains: "#/success"}}
"""
    started = await mcp_server.run_test("bu-sri", inline, analyze=False)
    rid = started["run_id"]
    for _ in range(100):
        info = mcp_server.get_findings(rid)
        if info["status"] != "running":
            break
        await asyncio.sleep(0.2)
    assert info["status"] == "done", info
    assert info["result"] == "gave_up"
    assert Path(info["report"]).exists()


async def test_bad_task_is_a_clear_error() -> None:
    with pytest.raises(ValueError, match="success"):
        await mcp_server.run_test("bu-sri", "id: x\nurl: http://x\ngoal_for_persona: g\n")
