"""
AWS Lambda entry point for VoxFox Bot.

One function, two invocation modes:

1. Telegram webhook (Lambda Function URL, POST): verify the
   X-Telegram-Bot-Api-Secret-Token header, asynchronously re-invoke this same
   function with the update payload, and return 200 immediately. Telegram
   retries webhooks that respond slowly, and renders take tens of seconds —
   acking first prevents duplicate videos.

2. Worker ({"voxfox_update": {...}} from the async self-invocation): run the
   update through the python-telegram-bot Application — the same handlers as
   the polling bot.

Heavy imports (bot.py pulls in librosa/matplotlib) are deferred to the worker
path so webhook acks stay fast even on cold containers.
"""

import asyncio
import json
import logging
import os

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger(__name__)

_WEBHOOK_SECRET = os.environ["TG_WEBHOOK_SECRET"]

# One event loop and PTB application per container, reused across invocations
# so httpx connection pools and handler state survive between updates.
_loop = asyncio.new_event_loop()
_app = None
_lambda_client = None


def _get_lambda_client():
    global _lambda_client
    if _lambda_client is None:
        import boto3

        _lambda_client = boto3.client("lambda")
    return _lambda_client


def _get_app():
    global _app
    if _app is None:
        from bot import build_application, register_mention_handlers

        app = build_application(os.environ["TELEGRAM_BOT_TOKEN"])
        _loop.run_until_complete(app.initialize())
        _loop.run_until_complete(register_mention_handlers(app))
        _app = app
    return _app


def _wants_processing(update: dict) -> bool:
    """Only messages and channel posts have handlers; skip everything else."""
    return "message" in update or "channel_post" in update


def _handle_webhook(event: dict) -> dict:
    headers = event.get("headers") or {}
    if headers.get("x-telegram-bot-api-secret-token") != _WEBHOOK_SECRET:
        return {"statusCode": 401, "body": "unauthorized"}

    method = (event.get("requestContext") or {}).get("http", {}).get("method")
    if method != "POST":
        return {"statusCode": 405, "body": "method not allowed"}

    try:
        update = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": "bad request"}

    if _wants_processing(update):
        _get_lambda_client().invoke(
            FunctionName=os.environ["AWS_LAMBDA_FUNCTION_NAME"],
            InvocationType="Event",
            Payload=json.dumps({"voxfox_update": update}).encode(),
        )
    return {"statusCode": 200, "body": "ok"}


def _handle_worker(update_json: dict) -> dict:
    from telegram import Update

    app = _get_app()
    update = Update.de_json(update_json, app.bot)
    _loop.run_until_complete(app.process_update(update))
    return {"ok": True}


def handler(event: dict, context) -> dict:
    if "voxfox_update" in event:
        return _handle_worker(event["voxfox_update"])
    return _handle_webhook(event)
