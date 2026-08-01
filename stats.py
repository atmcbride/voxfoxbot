"""
VoxFox user tracking — records every unique user who has interacted with the bot.

DynamoDB-backed when VOXFOX_DDB_TABLE is set, local stats.json otherwise. A
conditional put on user#<id> plus an atomic counter keeps /stats a single read
with no scans.
"""

import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)

_STATS_FILE = Path(__file__).parent / "stats.json"
_COUNTER_KEY = {"pk": "stat#users"}

_TABLE_NAME = os.environ.get("VOXFOX_DDB_TABLE")
_table = None


def _ddb_table():
    global _table
    if _table is None:
        import boto3

        _table = boto3.resource("dynamodb").Table(_TABLE_NAME)
    return _table


def _record_user_ddb(user_id: int) -> None:
    from botocore.exceptions import ClientError

    try:
        _ddb_table().put_item(
            Item={"pk": f"user#{user_id}", "first_seen": int(time.time())},
            ConditionExpression="attribute_not_exists(pk)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return  # already counted
        raise
    _ddb_table().update_item(
        Key=_COUNTER_KEY,
        UpdateExpression="ADD n :one",
        ExpressionAttributeValues={":one": 1},
    )


def record_user(user_id: int | None) -> None:
    """Record a user interaction. Silently ignores None (e.g. channel posts)."""
    if user_id is None:
        return
    try:
        if _TABLE_NAME:
            _record_user_ddb(user_id)
        else:
            data = json.loads(_STATS_FILE.read_text()) if _STATS_FILE.exists() else {}
            data.setdefault("users", {}).setdefault(str(user_id), time.time())
            _STATS_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        log.exception("stats.record_user failed")


def user_count() -> int:
    if _TABLE_NAME:
        item = _ddb_table().get_item(Key=_COUNTER_KEY).get("Item")
        return int(item["n"]) if item else 0
    data = json.loads(_STATS_FILE.read_text()) if _STATS_FILE.exists() else {}
    return len(data.get("users", {}))
