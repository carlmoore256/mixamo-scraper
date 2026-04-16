# mixamo-scraper

Bulk-download Mixamo animations with per-item metadata using a persistent browser profile (Playwright). The first run opens a browser so you can sign in to Adobe; later runs reuse the saved session.

## Requirements

- Python 3.10+
- Network access to [Mixamo](https://www.mixamo.com)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Usage

No config file needed — everything has sensible defaults and can be set via CLI flags.

```bash
# download up to 25 "walk" animations
python -m mixamo_scraper -q walk

# download ALL walk animations without root motion
python -m mixamo_scraper -q walk --max 0 --in-place

# download 10 "idle" animations at 60 fps into a custom folder
python -m mixamo_scraper -q idle --max 10 --fps 60 -o ./my-anims

# set arbitrary animation parameters
python -m mixamo_scraper -q walk --param "Overdrive=50" --param "Arm Space=80"

# run headless (no visible browser window — requires an existing login session)
python -m mixamo_scraper -q run --headless

# use a YAML config for complex/repeated setups (CLI flags still override it)
python -m mixamo_scraper --config config.yaml -q jump
```

Run `python -m mixamo_scraper --help` for the full list of options.

### CLI flags

| Flag | Description | Default |
|------|-------------|---------|
| `-q, --query` | Animation search query | *(all)* |
| `--max` | Max animations to download (0 = all) | 25 |
| `--start` | Start index in results | 0 |
| `--fps` | FPS for exported animation | 30 |
| `--format` | Export format | FBX Binary |
| `--skin / --no-skin` | Include skin in download | off |
| `--keyframe-reduction` | Keyframe reduction mode | None |
| `--in-place / --no-in-place` | Download without root motion | off |
| `--param KEY=VALUE` | Set animation parameter (repeatable) | |
| `--character` | Character search query | *(current)* |
| `--character-exact` | Exact character name | |
| `-o, --output-dir` | Output directory | output |
| `--no-skip-existing` | Re-download existing files | *(skip)* |
| `--headless / --no-headless` | Headless browser mode | off |
| `--profile-dir` | Browser profile directory | .mixamo-profile |
| `--config` | Optional YAML config file | |

### YAML config (optional)

For advanced or repeated setups, see `config.example.yaml`. CLI flags always take priority over values in the config file.
