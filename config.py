import json
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent / "settings.json"

DEFAULTS: dict = {
    "fmin": 70,
    "fmax": 4000,
    "colormap": "magma",
    "fps": 30,
    "auto_spectrogram": True,
    "linear_scale": False,
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


def get(chat_id: int) -> dict:
    stored = _load()
    chat_cfg = stored.get("chats", {}).get(str(chat_id), {})
    return {**DEFAULTS, **chat_cfg}


def update(chat_id: int, **kwargs) -> None:
    data = _load()
    chats = data.setdefault("chats", {})
    chats.setdefault(str(chat_id), {}).update(kwargs)
    _save(data)


def reset(chat_id: int) -> None:
    data = _load()
    data.get("chats", {}).pop(str(chat_id), None)
    _save(data)
