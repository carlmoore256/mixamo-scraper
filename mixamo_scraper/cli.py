from __future__ import annotations

import argparse
import time
from pathlib import Path

from mixamo_scraper.animation_params import apply_animation_parameters, capture_animation_parameters
from mixamo_scraper.config import AppConfig, default_config, load_config
from mixamo_scraper.discover import activate_animation_card, apply_animation_search, collect_animation_items, select_character
from mixamo_scraper.download import download_current_animation, sanitize_filename
from mixamo_scraper.metadata import (
    MetadataEntry,
    build_manifest_from_meta_files,
    has_matching_item,
    make_animation_identity,
    make_item_hash,
    make_options_signature,
    save_manifest,
    utc_now_iso,
    write_per_item_metadata,
)
from mixamo_scraper.selectors import MIXAMO_URL
from mixamo_scraper.session import create_persistent_context, is_signed_in, wait_for_login


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mixamo-scrape",
        description=(
            "Bulk download Mixamo animations with metadata. "
            "First run uses interactive login in a persistent browser profile."
        ),
        epilog=(
            "All options have sensible defaults. A config file is only needed "
            "for advanced/repeated setups. CLI flags override config file values."
        ),
    )
    parser.add_argument("--config", type=Path, default=None, help="Optional YAML config file (CLI flags override it)")

    search = parser.add_argument_group("search")
    search.add_argument("-q", "--query", dest="query", default=None, help="Animation search query (default: all)")
    search.add_argument("--max", dest="max_items", type=int, default=None, help="Max animations to download (default: 25)")
    search.add_argument("--start", dest="start_index", type=int, default=None, help="Start index in results (default: 0)")

    dl = parser.add_argument_group("download")
    dl.add_argument("--fps", default=None, help="FPS for exported animation (default: 30)")
    dl.add_argument("--format", dest="dl_format", default=None, help="Export format (default: FBX Binary)")
    dl.add_argument("--skin", action="store_true", default=None, help="Include skin in download")
    dl.add_argument("--no-skin", dest="skin", action="store_false")
    dl.add_argument("--keyframe-reduction", default=None, help="Keyframe reduction mode (default: None)")

    char = parser.add_argument_group("character")
    char.add_argument("--character", dest="character_query", default=None, help="Character search query")
    char.add_argument("--character-exact", dest="character_exact_name", default=None, help="Exact character name")

    out = parser.add_argument_group("output")
    out.add_argument("-o", "--output-dir", dest="output_dir", type=Path, default=None, help="Output directory (default: output)")
    out.add_argument("--no-skip-existing", dest="skip_existing", action="store_false", default=None, help="Re-download existing files")

    browser = parser.add_argument_group("browser")
    browser.add_argument("--headless", action="store_true", default=None, help="Run browser in headless mode")
    browser.add_argument("--no-headless", dest="headless", action="store_false")
    browser.add_argument("--profile-dir", dest="profile_dir", type=Path, default=None, help="Browser profile directory")

    return parser


def _apply_cli_overrides(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    if args.query is not None:
        config.search.animation_search_query = args.query
    if args.max_items is not None:
        config.search.max_items = args.max_items
    if args.start_index is not None:
        config.search.start_index = args.start_index
    if args.fps is not None:
        config.download.fps = args.fps
    if args.dl_format is not None:
        config.download.format = args.dl_format
    if args.skin is not None:
        config.download.include_skin = args.skin
    if args.keyframe_reduction is not None:
        config.download.keyframe_reduction = args.keyframe_reduction
    if args.character_query is not None:
        config.target.character_query = args.character_query
        config.target.force_character_select = True
    if args.character_exact_name is not None:
        config.target.character_exact_name = args.character_exact_name
        config.target.force_character_select = True
    if args.output_dir is not None:
        config.output.output_dir = args.output_dir.resolve()
    if args.skip_existing is not None:
        config.output.skip_existing = args.skip_existing
    if args.headless is not None:
        config.browser.headless = args.headless
    if args.profile_dir is not None:
        config.browser.profile_dir = args.profile_dir.resolve()
    return config


def _settings_dict(config: AppConfig) -> dict[str, object]:
    return {
        "download": {
            "format": config.download.format,
            "fps": config.download.fps,
            "include_skin": config.download.include_skin,
            "include_skinned_mesh": config.download.include_skinned_mesh,
            "keyframe_reduction": config.download.keyframe_reduction,
        },
        "animation_parameters": dict(config.download.animation_parameters),
    }


def run(config: AppConfig) -> int:
    query_folder = sanitize_filename(config.search.animation_search_query or "all")
    output_dir = config.output.output_dir / query_folder
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / config.output.manifest_filename
    manifest = build_manifest_from_meta_files(output_dir)

    session = create_persistent_context(
        profile_dir=config.browser.profile_dir,
        headless=config.browser.headless,
        channel=config.browser.channel,
        chromium_sandbox=config.browser.chromium_sandbox,
    )
    page = session.page

    try:
        page.goto(MIXAMO_URL, wait_until="domcontentloaded")
        if not is_signed_in(page):
            print("Please sign in to Adobe/Mixamo in the opened browser window.")
            print("The scraper will wait here until login is completed.")
            wait_for_login(page, config.browser.login_timeout_seconds)
            print("Login detected.")

        character_name = "current_character"
        if config.target.force_character_select and (
            config.target.character_query or config.target.character_exact_name
        ):
            try:
                character_name = select_character(
                    page,
                    config.target.character_query,
                    config.target.character_exact_name,
                )
            except RuntimeError as exc:
                print(f"{exc}. Continuing with current/default character.")
                character_name = "current_character"
            if character_name:
                print(f"Using character: {character_name}")
        else:
            print("Using currently selected character in Mixamo.")

        apply_animation_search(page, config.search.animation_search_query)
        time.sleep(1)
        items = collect_animation_items(page, config.search.max_items, config.search.start_index)
        if not items:
            print("No animations found for the query.")
            return 1

        character_slug = sanitize_filename(character_name or "default_character")
        print(f"Found {len(items)} animation candidates.")
        options = _settings_dict(config)
        options_signature = make_options_signature(options)

        for index, item in enumerate(items, start=1):
            animation_slug = sanitize_filename(item.slug or item.title)
            animation_identity = make_animation_identity(character_slug, item.title, item.description)
            item_hash = make_item_hash(animation_identity, options_signature)
            output_stem = sanitize_filename(f"{animation_slug}__{item_hash}")
            local_path = (output_dir / f"{output_stem}.fbx").resolve()
            source_url = page.url

            draft_entry = MetadataEntry(
                animation_title=item.title,
                animation_description=item.description,
                animation_slug=animation_slug,
                animation_identity=animation_identity,
                character_name=character_name,
                character_slug=character_slug,
                query=config.search.animation_search_query,
                source_url=source_url,
                local_path=str(local_path),
                downloaded_at=utc_now_iso(),
                options=options,
                options_signature=options_signature,
                requested_animation_parameters=dict(config.download.animation_parameters),
                applied_animation_parameters={},
                observed_animation_parameters={},
            )
            if config.output.skip_existing and has_matching_item(manifest, draft_entry):
                print(f"[{index}/{len(items)}] Skipping existing: {item.title}")
                continue

            print(f"[{index}/{len(items)}] Downloading: {item.title}")
            activate_animation_card(page, item.title, item.description)
            apply_result = apply_animation_parameters(page, config.download.animation_parameters)
            if apply_result.get("applied"):
                time.sleep(0.5)
            missing_params = list(apply_result.get("missing", []) or [])
            if missing_params:
                print(f"  Missing animation controls: {', '.join(missing_params)}")
            observed_parameters: dict[str, object] = {}
            if config.download.capture_animation_parameters:
                observed_parameters = capture_animation_parameters(page)
            result = download_current_animation(
                page=page,
                output_dir=output_dir,
                output_stem=output_stem,
                settings=config.download,
                title=item.title,
            )

            entry = MetadataEntry(
                animation_title=result.title,
                animation_description=item.description,
                animation_slug=animation_slug,
                animation_identity=animation_identity,
                character_name=character_name,
                character_slug=character_slug,
                query=config.search.animation_search_query,
                source_url=result.source_url,
                local_path=str(result.file_path.resolve()),
                downloaded_at=utc_now_iso(),
                options=options,
                options_signature=options_signature,
                requested_animation_parameters=dict(config.download.animation_parameters),
                applied_animation_parameters=dict(apply_result.get("applied", {}) or {}),
                observed_animation_parameters=observed_parameters,
            )
            write_per_item_metadata(output_dir, entry)
            manifest["items"].append(entry.__dict__)

        save_manifest(manifest_path, build_manifest_from_meta_files(output_dir))
        print(f"Done. Manifest: {manifest_path}")
        return 0
    finally:
        session.close()


def main() -> int:
    args = _build_parser().parse_args()
    if args.config is not None:
        config_path = args.config.resolve()
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        config = load_config(config_path)
    else:
        config = default_config()
    config = _apply_cli_overrides(config, args)
    return run(config)
