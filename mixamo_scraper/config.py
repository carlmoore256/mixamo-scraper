from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class BrowserConfig:
    profile_dir: Path = field(default_factory=lambda: Path(".mixamo-profile").resolve())
    headless: bool = False
    login_timeout_seconds: int = 300
    channel: str = "chrome"
    chromium_sandbox: bool = True


@dataclass
class TargetConfig:
    character_query: str = ""
    character_exact_name: str = ""
    force_character_select: bool = False


@dataclass
class SearchConfig:
    animation_search_query: str = ""
    max_items: int = 25
    start_index: int = 0


@dataclass
class DownloadConfig:
    format: str = "FBX Binary"
    fps: str = "30"
    include_skin: bool = False
    include_skinned_mesh: bool = False
    keyframe_reduction: str = "None"
    delay_ms: int = 800
    timeout_seconds: int = 120
    animation_parameters: dict[str, Any] = field(default_factory=dict)
    capture_animation_parameters: bool = True


@dataclass
class OutputConfig:
    output_dir: Path = field(default_factory=lambda: Path("output").resolve())
    manifest_filename: str = "manifest.json"
    skip_existing: bool = True


@dataclass
class AppConfig:
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    target: TargetConfig = field(default_factory=TargetConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    download: DownloadConfig = field(default_factory=DownloadConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


def default_config() -> AppConfig:
    return AppConfig()


def _as_dict(data: Any, key: str) -> dict[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"Expected '{key}' to be a mapping")
    return value


def load_config(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Config root must be a mapping")

    browser = _as_dict(raw, "browser")
    target = _as_dict(raw, "target")
    search = _as_dict(raw, "search")
    download = _as_dict(raw, "download")
    output = _as_dict(raw, "output")

    base_dir = path.parent.resolve()

    profile_dir = Path(browser.get("profile_dir", ".mixamo-profile"))
    output_dir = Path(output.get("output_dir", "output"))

    return AppConfig(
        browser=BrowserConfig(
            profile_dir=(base_dir / profile_dir).resolve(),
            headless=bool(browser.get("headless", False)),
            login_timeout_seconds=int(browser.get("login_timeout_seconds", 300)),
            channel=str(browser.get("channel", "chrome")).strip(),
            chromium_sandbox=bool(browser.get("chromium_sandbox", True)),
        ),
        target=TargetConfig(
            character_query=str(target.get("character_query", "")).strip(),
            character_exact_name=str(target.get("character_exact_name", "")).strip(),
            force_character_select=bool(target.get("force_character_select", False)),
        ),
        search=SearchConfig(
            animation_search_query=str(search.get("animation_search_query", "")).strip(),
            max_items=int(search.get("max_items", 25)),
            start_index=int(search.get("start_index", 0)),
        ),
        download=DownloadConfig(
            format=str(download.get("format", "FBX Binary")).strip(),
            fps=str(download.get("fps", "30")).strip(),
            include_skin=bool(download.get("include_skin", False)),
            include_skinned_mesh=bool(download.get("include_skinned_mesh", False)),
            keyframe_reduction=str(download.get("keyframe_reduction", "None")).strip(),
            delay_ms=int(download.get("delay_ms", 800)),
            timeout_seconds=int(download.get("timeout_seconds", 120)),
            animation_parameters=dict(download.get("animation_parameters", {}) or {}),
            capture_animation_parameters=bool(download.get("capture_animation_parameters", True)),
        ),
        output=OutputConfig(
            output_dir=(base_dir / output_dir).resolve(),
            manifest_filename=str(output.get("manifest_filename", "manifest.json")).strip(),
            skip_existing=bool(output.get("skip_existing", True)),
        ),
    )
