"""Playwright session with device emulation and popup-dialog capture."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Dialog, Page, async_playwright

DEVICES: dict[str, dict[str, Any]] = {
    "android_midrange": {
        "viewport": {"width": 360, "height": 800},
        "device_scale_factor": 2,
        "is_mobile": True,
        "has_touch": True,
        "user_agent": (
            "Mozilla/5.0 (Linux; Android 12; SM-A135F) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
        ),
    },
    "desktop": {"viewport": {"width": 1280, "height": 800}},
}


@dataclass
class Session:
    page: Page
    messages: list[str] = field(default_factory=list)  # alert/confirm texts not yet shown

    def pop_messages(self) -> list[str]:
        out, self.messages = self.messages, []
        return out


@asynccontextmanager
async def open_session(
    device: str = "android_midrange", headed: bool = False
) -> AsyncIterator[Session]:
    if device not in DEVICES:
        raise ValueError(f"unknown device {device!r}; known: {', '.join(DEVICES)}")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed)
        try:
            ctx = await browser.new_context(**DEVICES[device])
            page = await ctx.new_page()
            session = Session(page)

            async def on_dialog(d: Dialog) -> None:
                session.messages.append(d.message)
                await d.accept()

            page.on("dialog", on_dialog)
            yield session
        finally:
            await browser.close()
