from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Download, Error as PlaywrightError, Page

from mixamo_scraper.config import DownloadConfig

MAX_DOWNLOAD_RETRIES = 3


@dataclass
class DownloadResult:
    file_path: Path
    title: str
    source_url: str


def sanitize_filename(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    clean = clean.strip("._")
    return clean or "item"


def _set_modal_options(page: Page, settings: DownloadConfig) -> None:
    skin_value = "Without Skin" if not settings.include_skin else "With Skin"
    page.evaluate(
        """({ format, skin, fps, keyframe }) => {
            const normalize = (v) => String(v || "").toLowerCase().replace(/\\s+/g, " ").trim();
            const dialog = document.querySelector("dialog") || document.querySelector("[role='dialog']") || document;
            const selects = Array.from(dialog.querySelectorAll("select"));

            function setSelect(labelText, desired) {
                if (!desired) return;
                const desiredNorm = normalize(desired);
                for (const sel of selects) {
                    const row = sel.closest("div");
                    if (!row) continue;
                    const rowText = normalize(row.textContent || "");
                    if (!rowText.includes(normalize(labelText))) continue;
                    const options = Array.from(sel.options);
                    const match = options.find(o => normalize(o.textContent).includes(desiredNorm));
                    if (!match) continue;
                    sel.value = match.value;
                    sel.dispatchEvent(new Event("change", { bubbles: true }));
                    return;
                }
            }

            setSelect("Format", format);
            setSelect("Skin", skin);
            setSelect("Frames per Second", fps);
            setSelect("Keyframe Reduction", keyframe);
        }""",
        {
            "format": settings.format,
            "skin": skin_value,
            "fps": settings.fps,
            "keyframe": settings.keyframe_reduction,
        },
    )


def download_current_animation(
    page: Page,
    output_dir: Path,
    output_stem: str,
    settings: DownloadConfig,
    title: str,
) -> DownloadResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    dl_button = page.get_by_role("button", name="Download")
    if dl_button.count() > 0:
        dl_button.first.click()
    else:
        page.locator("button:has-text('Download')").first.click()

    modal = page.locator(".asset-download-modal")
    modal.wait_for(state="visible", timeout=5000)
    time.sleep(0.3)

    _set_modal_options(page, settings)

    filename = sanitize_filename(f"{output_stem}.fbx")
    target_path = output_dir / filename

    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            with page.expect_download(timeout=settings.timeout_seconds * 1000) as download_info:
                modal_dl = modal.locator("button:has-text('Download')")
                if modal_dl.count() > 0:
                    modal_dl.first.click()
                else:
                    page.get_by_role("button", name="Download").last.click()
            download = download_info.value
            download.save_as(str(target_path))
            break
        except PlaywrightError as exc:
            if attempt < MAX_DOWNLOAD_RETRIES:
                print(f"  Download failed (attempt {attempt}/{MAX_DOWNLOAD_RETRIES}): {exc}")
                time.sleep(2)
                modal = page.locator(".asset-download-modal")
                if modal.count() == 0:
                    dl_button = page.get_by_role("button", name="Download")
                    if dl_button.count() > 0:
                        dl_button.first.click()
                    modal.wait_for(state="visible", timeout=5000)
                    time.sleep(0.3)
                    _set_modal_options(page, settings)
            else:
                raise

    if settings.delay_ms > 0:
        time.sleep(settings.delay_ms / 1000.0)

    return DownloadResult(
        file_path=target_path,
        title=title,
        source_url=page.url,
    )
