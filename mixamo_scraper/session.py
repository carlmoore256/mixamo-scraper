from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import BrowserContext, Error as PlaywrightError, Page, Playwright, TimeoutError as PlaywrightTimeoutError, sync_playwright

from mixamo_scraper.selectors import AUTHENTICATED_MARKERS, MIXAMO_URL, SIGNED_OUT_MARKERS


@dataclass
class SessionHandle:
    playwright: Playwright
    context: BrowserContext
    page: Page

    def close(self) -> None:
        self.context.close()
        self.playwright.stop()


def _launch_context(
    playwright: Playwright,
    profile_dir: Path,
    headless: bool,
    channel: str,
    chromium_sandbox: bool,
) -> BrowserContext:
    kwargs = {
        "user_data_dir": str(profile_dir),
        "headless": headless,
        "accept_downloads": True,
        "viewport": {"width": 1600, "height": 1000},
        "chromium_sandbox": chromium_sandbox,
    }
    if channel:
        kwargs["channel"] = channel
    return playwright.chromium.launch_persistent_context(**kwargs)


def create_persistent_context(
    profile_dir: Path,
    headless: bool,
    channel: str,
    chromium_sandbox: bool,
) -> SessionHandle:
    profile_dir.mkdir(parents=True, exist_ok=True)
    playwright = sync_playwright().start()
    last_error: Exception | None = None
    for candidate_channel in [channel, ""]:
        if candidate_channel == channel and channel == "":
            continue
        try:
            context = _launch_context(
                playwright=playwright,
                profile_dir=profile_dir,
                headless=headless,
                channel=candidate_channel,
                chromium_sandbox=chromium_sandbox,
            )
            break
        except PlaywrightError as exc:
            last_error = exc
            if candidate_channel == "":
                playwright.stop()
                raise
    else:
        playwright.stop()
        raise RuntimeError("Could not launch browser") from last_error

    context.set_default_timeout(15000)
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(MIXAMO_URL, wait_until="domcontentloaded")
    return SessionHandle(playwright=playwright, context=context, page=page)


def is_signed_in(page: Page) -> bool:
    for label in SIGNED_OUT_MARKERS:
        if page.get_by_text(label, exact=False).count() > 0:
            return False
    for label in AUTHENTICATED_MARKERS:
        if page.get_by_text(label, exact=False).count() > 0:
            return True
    if "adobe.com" in page.url.lower():
        return False
    return page.locator("text=Download").count() > 0 or page.locator("text=Animations").count() > 0


def wait_for_login(page: Page, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if is_signed_in(page):
            return
        try:
            page.wait_for_timeout(1500)
        except PlaywrightTimeoutError:
            time.sleep(1.5)
        time.sleep(2)
    raise TimeoutError("Timed out waiting for Mixamo login completion")
