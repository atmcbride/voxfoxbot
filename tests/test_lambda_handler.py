"""Webhook-path behavior of lambda_handler.py (no Telegram/AWS calls)."""

import json
import os

os.environ.setdefault("TG_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("AWS_LAMBDA_FUNCTION_NAME", "voxfoxbot")

import lambda_handler


class FakeLambdaClient:
    def __init__(self):
        self.invocations = []

    def invoke(self, **kwargs):
        self.invocations.append(kwargs)
        return {"StatusCode": 202}


def _event(body, secret="test-secret", method="POST"):
    return {
        "headers": {"x-telegram-bot-api-secret-token": secret},
        "requestContext": {"http": {"method": method}},
        "body": json.dumps(body) if isinstance(body, dict) else body,
    }


def _fake_client(monkeypatch):
    fake = FakeLambdaClient()
    monkeypatch.setattr(lambda_handler, "_lambda_client", fake)
    return fake


def test_wrong_secret_rejected(monkeypatch):
    fake = _fake_client(monkeypatch)
    resp = lambda_handler.handler(_event({"message": {}}, secret="wrong"), None)
    assert resp["statusCode"] == 401
    assert fake.invocations == []


def test_missing_secret_rejected(monkeypatch):
    fake = _fake_client(monkeypatch)
    event = _event({"message": {}})
    del event["headers"]
    resp = lambda_handler.handler(event, None)
    assert resp["statusCode"] == 401
    assert fake.invocations == []


def test_non_post_rejected(monkeypatch):
    fake = _fake_client(monkeypatch)
    resp = lambda_handler.handler(_event({"message": {}}, method="GET"), None)
    assert resp["statusCode"] == 405
    assert fake.invocations == []


def test_bad_json_rejected(monkeypatch):
    fake = _fake_client(monkeypatch)
    resp = lambda_handler.handler(_event("{not json"), None)
    assert resp["statusCode"] == 400
    assert fake.invocations == []


def test_message_update_acked_and_dispatched(monkeypatch):
    fake = _fake_client(monkeypatch)
    update = {"update_id": 1, "message": {"text": "hi"}}
    resp = lambda_handler.handler(_event(update), None)
    assert resp["statusCode"] == 200
    assert len(fake.invocations) == 1
    inv = fake.invocations[0]
    assert inv["FunctionName"] == "voxfoxbot"
    assert inv["InvocationType"] == "Event"
    assert json.loads(inv["Payload"]) == {"voxfox_update": update}


def test_channel_post_dispatched(monkeypatch):
    fake = _fake_client(monkeypatch)
    resp = lambda_handler.handler(
        _event({"update_id": 2, "channel_post": {"text": "hi"}}), None
    )
    assert resp["statusCode"] == 200
    assert len(fake.invocations) == 1


def test_irrelevant_update_acked_without_dispatch(monkeypatch):
    fake = _fake_client(monkeypatch)
    resp = lambda_handler.handler(
        _event({"update_id": 3, "my_chat_member": {}}), None
    )
    assert resp["statusCode"] == 200
    assert fake.invocations == []
