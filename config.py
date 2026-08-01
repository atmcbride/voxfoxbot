"""
Per-chat settings.

Backed by DynamoDB when VOXFOX_DDB_TABLE is set (Lambda), otherwise by a local
settings.json next to the code (development / polling mode).

Overrides are stored as one JSON string per chat: the blobs are tiny, and JSON
text round-trips floats cleanly where DynamoDB's native number type (Decimal)
does not.
"""

import json
import os
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

_TABLE_NAME = os.environ.get("VOXFOX_DDB_TABLE")
_table = None


def _ddb_table():
    global _table
    if _table is None:
        import boto3

        _table = boto3.resource("dynamodb").Table(_TABLE_NAME)
    return _table


def _chat_key(chat_id: int) -> dict:
    return {"pk": f"chat#{chat_id}"}


def _load() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    with open(SETTINGS_FILE) as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _get_overrides(chat_id: int) -> dict:
    if _TABLE_NAME:
        item = _ddb_table().get_item(Key=_chat_key(chat_id)).get("Item")
        return json.loads(item["settings"]) if item else {}
    return _load().get("chats", {}).get(str(chat_id), {})


def get(chat_id: int) -> dict:
    return {**DEFAULTS, **_get_overrides(chat_id)}


def update(chat_id: int, **kwargs) -> None:
    if _TABLE_NAME:
        overrides = {**_get_overrides(chat_id), **kwargs}
        _ddb_table().put_item(
            Item={**_chat_key(chat_id), "settings": json.dumps(overrides)}
        )
        return
    data = _load()
    chats = data.setdefault("chats", {})
    chats.setdefault(str(chat_id), {}).update(kwargs)
    _save(data)


def reset(chat_id: int) -> None:
    if _TABLE_NAME:
        _ddb_table().delete_item(Key=_chat_key(chat_id))
        return
    data = _load()
    data.get("chats", {}).pop(str(chat_id), None)
    _save(data)
