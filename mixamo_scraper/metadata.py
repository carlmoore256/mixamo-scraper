from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class MetadataEntry:
    animation_title: str
    animation_description: str
    animation_slug: str
    animation_identity: str
    character_name: str
    character_slug: str
    query: str
    source_url: str
    local_path: str
    downloaded_at: str
    options: dict[str, Any]
    options_signature: str
    requested_animation_parameters: dict[str, Any]
    applied_animation_parameters: dict[str, Any]
    observed_animation_parameters: dict[str, Any]


def write_per_item_metadata(output_dir: Path, entry: MetadataEntry) -> Path:
    filename = f"{Path(entry.local_path).stem}.meta.json"
    target = output_dir / filename
    target.write_text(json.dumps(asdict(entry), indent=2), encoding="utf-8")
    return target


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"updated_at": utc_now_iso(), "items": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"updated_at": utc_now_iso(), "items": []}
    if "items" not in data or not isinstance(data["items"], list):
        data["items"] = []
    return data


def has_matching_item(manifest: dict[str, Any], entry: MetadataEntry) -> bool:
    local_path = entry.local_path
    for item in manifest.get("items", []):
        if not isinstance(item, dict):
            continue
        if (
            item.get("animation_identity") == entry.animation_identity
            and item.get("options_signature") == entry.options_signature
            and item.get("character_slug") == entry.character_slug
        ):
            return True
        if item.get("local_path") == local_path:
            return True
    return False


def append_manifest_item(path: Path, entry: MetadataEntry) -> None:
    manifest = load_manifest(path)
    manifest["items"].append(asdict(entry))
    manifest["updated_at"] = utc_now_iso()
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = utc_now_iso()
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def build_manifest_from_meta_files(output_dir: Path) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for meta_path in sorted(output_dir.glob("*.meta.json")):
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return {"updated_at": utc_now_iso(), "items": items}


def make_options_signature(options: dict[str, Any]) -> str:
    payload = json.dumps(options, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def make_animation_identity(character_slug: str, title: str, description: str) -> str:
    raw = f"{character_slug}|{title.strip().lower()}|{description.strip().lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def make_item_hash(animation_identity: str, options_signature: str, length: int = 10) -> str:
    raw = f"{animation_identity}|{options_signature}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:max(4, length)]
