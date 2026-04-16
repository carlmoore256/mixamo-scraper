from __future__ import annotations

from typing import Any

from playwright.sync_api import Page


def apply_animation_parameters(page: Page, requested: dict[str, Any]) -> dict[str, Any]:
    if not requested:
        return {"applied": {}, "missing": []}
    result = page.evaluate(
        """(params) => {
            const normalize = (v) => String(v || "").toLowerCase().replace(/\\s+/g, " ").trim();
            const visible = (el) => !!el && !!el.isConnected && el.offsetParent !== null;
            const isRightPanelControl = (el) => {
                if (!visible(el)) return false;
                const rect = el.getBoundingClientRect();
                if (!rect || rect.width <= 0 || rect.height <= 0) return false;
                return rect.left >= window.innerWidth * 0.35;
            };
            const applied = {};
            const missing = [];

            for (const [rawKey, rawValue] of Object.entries(params)) {
                const key = String(rawKey);
                const keyNorm = normalize(key);
                let done = false;

                const boxes = Array.from(document.querySelectorAll("input[type='checkbox']"))
                    .filter(isRightPanelControl);
                for (const box of boxes) {
                    const row = box.closest("div, label") || box.parentElement;
                    const labelText = normalize((row?.textContent || "") + " " + (box.getAttribute("aria-label") || ""));
                    if (!labelText.includes(keyNorm)) continue;
                    const value = !!rawValue;
                    if (box.checked !== value) {
                        box.click();
                        box.dispatchEvent(new Event("input", { bubbles: true }));
                        box.dispatchEvent(new Event("change", { bubbles: true }));
                    }
                    if (box.checked !== value) {
                        box.checked = value;
                        box.dispatchEvent(new Event("input", { bubbles: true }));
                        box.dispatchEvent(new Event("change", { bubbles: true }));
                    }
                    applied[key] = !!box.checked;
                    done = true;
                    break;
                }
                if (done) continue;

                const textInputs = Array.from(document.querySelectorAll("input"))
                    .filter((el) => isRightPanelControl(el) && (el.type === "text" || el.type === "number"));
                for (const input of textInputs) {
                    const row = input.closest("div") || input.parentElement;
                    const rowText = normalize((row?.textContent || ""));
                    if (!rowText.includes(keyNorm)) continue;
                    const value = String(rawValue);
                    input.focus();
                    input.value = "";
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.value = value;
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
                    input.dispatchEvent(new KeyboardEvent("keyup", { key: "Enter", bubbles: true }));
                    applied[key] = value;
                    done = true;
                    break;
                }

                if (!done) missing.push(key);
            }

            return { applied, missing };
        }""",
        requested,
    )
    if not isinstance(result, dict):
        return {"applied": {}, "missing": list(requested.keys())}
    return {
        "applied": dict(result.get("applied", {}) or {}),
        "missing": list(result.get("missing", []) or []),
    }


def capture_animation_parameters(page: Page) -> dict[str, Any]:
    snapshot = page.evaluate(
        """() => {
            const normalize = (v) => String(v || "").replace(/\\s+/g, " ").trim();
            const visible = (el) => !!el && !!el.isConnected && el.offsetParent !== null;
            const isRightPanelControl = (el) => {
                if (!visible(el)) return false;
                const rect = el.getBoundingClientRect();
                if (!rect || rect.width <= 0 || rect.height <= 0) return false;
                return rect.left >= window.innerWidth * 0.35;
            };
            const output = {};
            const inputs = Array.from(document.querySelectorAll("input"))
                .filter((el) => isRightPanelControl(el) && el.type !== "search");

            let index = 0;
            for (const input of inputs) {
                const row = input.closest("div, label") || input.parentElement;
                const rowText = normalize(row?.textContent || "");
                let label = "";
                const tokens = rowText.split(" ").filter(Boolean);
                if (tokens.length > 0) {
                    label = rowText;
                }
                if (!label) {
                    label = `field_${index}`;
                }

                if (input.type === "checkbox") {
                    output[label] = !!input.checked;
                } else if (input.type === "text" || input.type === "number") {
                    output[label] = normalize(input.value || "");
                }
                index += 1;
            }
            return output;
        }"""
    )
    if isinstance(snapshot, dict):
        return dict(snapshot)
    return {}
