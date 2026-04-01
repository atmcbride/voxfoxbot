import json
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent / "settings.json"

DEFAULTS: dict = {
    "fmin": 80,
    "fmax": 8000,
    "colormap": "magma",
    "fps": 30,
    "markers": [],  # list of {"freq": float, "label": str}
}


def _load() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    with open(SETTINGS_FILE) as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get(chat_id: int) -> dict:
    data = _load()
    stored = data.get(str(chat_id), {})
    # Merge stored markers separately to avoid clobbering defaults
    result = {**DEFAULTS, **stored}
    return result


def update(chat_id: int, **kwargs) -> None:
    data = _load()
    key = str(chat_id)
    current = data.get(key, {})
    current.update(kwargs)
    data[key] = current
    _save(data)
