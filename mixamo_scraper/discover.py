from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Iterable

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from mixamo_scraper.selectors import CHARACTER_PICKER_OPENERS, SEARCH_INPUT_LABELS

IGNORED_CARD_TEXT = (
    "log in",
    "sign up",
    "characters",
    "animations",
    "upload character",
    "find animations",
    "download",
    "copyright",
    "privacy",
    "terms",
    "per page",
    "default character",
    "loading",
)


@dataclass
class AnimationItem:
    title: str
    description: str
    href: str
    slug: str


def _slugify(value: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    text = "-".join(part for part in text.split("-") if part)
    return text or "item"


def _first_visible_by_text(page: Page, labels: Iterable[str]):
    for label in labels:
        locator = page.get_by_text(label, exact=False)
        if locator.count() > 0:
            try:
                target = locator.first
                if target.is_visible():
                    return target
            except Exception:
                continue
    return None


def open_character_picker(page: Page) -> bool:
    for opener in CHARACTER_PICKER_OPENERS:
        button = page.get_by_role("button", name=opener, exact=False)
        if button.count() > 0:
            try:
                button.first.click()
                return True
            except Exception:
                pass
    fallback = _first_visible_by_text(page, CHARACTER_PICKER_OPENERS)
    if fallback:
        fallback.click()
        return True
    return False


def select_character(page: Page, query: str, exact_name: str) -> str:
    if not query and not exact_name:
        return ""
    open_character_picker(page)
    time.sleep(1)
    search = page.get_by_role("textbox", name="Search", exact=False)
    if search.count() > 0:
        search.first.fill(exact_name or query)
    else:
        for label in SEARCH_INPUT_LABELS:
            field = page.get_by_placeholder(label)
            if field.count() > 0:
                field.first.fill(exact_name or query)
                break
    time.sleep(1)
    target = exact_name or query

    candidates = [target]
    lowered = target.lower().strip()
    normalized = lowered.replace(" ", "").replace("-", "")
    if normalized == "ybot":
        candidates.extend(["Ybot", "Y Bot", "Y-Bot"])
    elif normalized == "xbot":
        candidates.extend(["Xbot", "X Bot", "X-Bot"])

    for candidate in candidates:
        card = page.get_by_text(candidate, exact=False)
        if card.count() > 0:
            card.first.click()
            time.sleep(1)
            return card.first.inner_text().strip() or candidate

    cards = page.locator("a,button,div").filter(has_text=re.compile(r".+"))
    for idx in range(min(cards.count(), 30)):
        try:
            text = (cards.nth(idx).inner_text() or "").strip()
            if not text:
                continue
            compact = text.lower().replace(" ", "").replace("-", "")
            if normalized and normalized in compact:
                cards.nth(idx).click()
                time.sleep(1)
                return text
        except Exception:
            continue

    raise RuntimeError(f"Could not find character '{target}'")


def apply_animation_search(page: Page, query: str) -> None:
    if not query:
        return

    def locate_search_input():
        search_input = page.get_by_role("searchbox", name="Search")
        if search_input.count() > 0:
            return search_input.first
        search_input = page.locator("form input[type='search']")
        if search_input.count() > 0:
            return search_input.first
        search_input = page.get_by_role("textbox", name="Search", exact=False)
        if search_input.count() > 0:
            return search_input.first
        for label in SEARCH_INPUT_LABELS:
            field = page.get_by_placeholder(label)
            if field.count() > 0:
                return field.first
        return None

    cancel = page.get_by_role("button", name="Cancel")
    if cancel.count() > 0:
        try:
            cancel.first.click(timeout=500)
            time.sleep(0.2)
        except Exception:
            pass

    target = locate_search_input()
    if target is None:
        try:
            page.goto("https://www.mixamo.com/#/?page=1&type=Motion%2CMotionPack", wait_until="domcontentloaded")
            time.sleep(1.0)
        except Exception:
            pass
        target = locate_search_input()

    if target is not None:
        target.click()
        target.fill("")
        target.type(query)
        target.press("Enter")
        try:
            page.wait_for_function(
                "([q]) => window.location.hash.toLowerCase().includes(('query=' + encodeURIComponent(q)).toLowerCase())",
                arg=[query],
                timeout=8000,
            )
        except PlaywrightTimeoutError:
            pass
        return

    raise RuntimeError("Could not locate animation search input")


def _card_locator(page: Page):
    specific = page.locator(".product.product-animation")
    if specific.count() > 0:
        return specific
    return page.locator("div").filter(has=page.locator("img[alt='3D Animation']"))


def activate_animation_card(page: Page, title: str, description: str = "") -> None:
    clicked = page.evaluate(
        """({ title, description }) => {
            const normalize = (v) => String(v || "").replace(/\\s+/g, " ").trim().toLowerCase();
            const titleNorm = normalize(title);
            const descNorm = normalize(description);
            const cards = Array.from(document.querySelectorAll(".product.product-animation"));
            const byText = cards.find((card) => {
                const t = normalize(card.querySelector("p")?.textContent || "");
                const dRaw = normalize(card.querySelector("li")?.textContent || "");
                const d = dRaw.startsWith("description:") ? dRaw.slice("description:".length).trim() : dRaw;
                if (t !== titleNorm) return false;
                if (!descNorm) return true;
                return d === descNorm;
            });
            const target = byText || cards.find((card) => normalize(card.querySelector("p")?.textContent || "") === titleNorm);
            if (!target) return false;
            target.scrollIntoView({ block: "center", inline: "nearest" });
            target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
            return true;
        }""",
        {"title": title, "description": description},
    )
    if clicked:
        time.sleep(0.7)
        return

    if description:
        combined = re.compile(rf"{re.escape(title)}.*{re.escape(description)}", re.IGNORECASE | re.DOTALL)
        card = _card_locator(page).filter(has_text=combined)
    else:
        card = _card_locator(page).filter(has_text=re.compile(rf"^{re.escape(title)}(\n|$)"))
    if card.count() > 0:
        card.first.scroll_into_view_if_needed()
        card.first.click(force=True)
        time.sleep(0.7)
        return
    text_hit = page.get_by_text(title, exact=True)
    if text_hit.count() > 0:
        text_hit.first.click()
        time.sleep(0.7)
        return
    raise RuntimeError(f"Could not activate animation card '{title}'")


def collect_animation_items(page: Page, max_items: int, start_index: int) -> list[AnimationItem]:
    seen: set[str] = set()
    items: list[AnimationItem] = []
    needed = max_items + start_index

    def _clean_title(value: str) -> str:
        return " ".join(value.split()).strip()

    def _is_valid_title(value: str) -> bool:
        if not value:
            return False
        if len(value) > 80:
            return False
        lower = value.lower()
        if any(token in lower for token in IGNORED_CARD_TEXT):
            return False
        if re.fullmatch(r"[0-9]+", value):
            return False
        return True

    while len(items) < needed:
        before = len(items)
        raw_cards = page.evaluate(
            """() => {
                const visible = (el) => !!el && !!el.isConnected && el.offsetParent !== null;
                const rows = [];
                const cards = Array.from(document.querySelectorAll(".product.product-animation"));
                for (const card of cards) {
                    if (!visible(card)) continue;
                    const titleEl = card.querySelector("p");
                    const descEl = card.querySelector("li");
                    const title = (titleEl?.textContent || "").replace(/\\s+/g, " ").trim();
                    const descRaw = (descEl?.textContent || "").replace(/\\s+/g, " ").trim();
                    if (!title) continue;
                    rows.push({ title, description: descRaw });
                }
                if (rows.length > 0) return rows;

                const imgs = Array.from(document.querySelectorAll("img[alt='3D Animation']"));
                for (const img of imgs) {
                    const card = img.closest("div");
                    if (!visible(card)) continue;
                    const titleEl = card.querySelector("p");
                    const descEl = card.querySelector("li");
                    const title = (titleEl?.textContent || "").replace(/\\s+/g, " ").trim();
                    const descRaw = (descEl?.textContent || "").replace(/\\s+/g, " ").trim();
                    if (!title) continue;
                    rows.push({ title, description: descRaw });
                }
                return rows;
            }"""
        )
        if not isinstance(raw_cards, list):
            raw_cards = []

        for row in raw_cards:
            if not isinstance(row, dict):
                continue
            text = _clean_title(str(row.get("title", "")))
            if not _is_valid_title(text):
                continue
            desc = _clean_title(str(row.get("description", "")))
            if desc.lower().startswith("description:"):
                desc = _clean_title(desc.split(":", 1)[1])
            key = f"{text.lower()}|{desc.lower()}"
            if key in seen:
                continue
            seen.add(key)
            items.append(AnimationItem(title=text, description=desc, href="", slug=_slugify(text)))
            if len(items) >= needed:
                break

        if len(items) >= needed:
            break

        next_button = page.locator("a:has-text('')")
        if next_button.count() == 0:
            break
        try:
            next_button.first.click()
            time.sleep(1.2)
        except Exception:
            break

        if len(items) == before:
            break

    if start_index > 0:
        items = items[start_index:]
    return items[:max_items]
