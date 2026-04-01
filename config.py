import json
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent / "settings.json"

DEFAULTS: dict = {
    "fmin": 70,
    "fmax": 4000,
    "colormap": "magma",
    "fps": 30,
    "markers": [
        {"freq": 74.42, "label": "D2"},
        {"freq": 164.81, "label": "E3"},
        {"freq": 293.66, "label": "D4"},
    ],
}


def _load() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    with open(SETTINGS_FILE) as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get() -> dict:
    stored = _load()
    return {**DEFAULTS, **stored}


def update(**kwargs) -> None:
    current = _load()
    current.update(kwargs)
    _save(current)
