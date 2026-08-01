"""Local-backend semantics of config.py (DynamoDB path is exercised in prod)."""

import config


def _use_tmp_file(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_TABLE_NAME", None)
    monkeypatch.setattr(config, "SETTINGS_FILE", tmp_path / "settings.json")


def test_get_returns_defaults_for_unknown_chat(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    assert config.get(123) == config.DEFAULTS


def test_update_overrides_only_given_keys(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    config.update(123, fmin=100, fmax=8000)
    cfg = config.get(123)
    assert cfg["fmin"] == 100
    assert cfg["fmax"] == 8000
    assert cfg["colormap"] == config.DEFAULTS["colormap"]
    # other chats untouched
    assert config.get(456) == config.DEFAULTS


def test_updates_accumulate(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    config.update(123, fmin=100)
    config.update(123, colormap="viridis")
    cfg = config.get(123)
    assert cfg["fmin"] == 100
    assert cfg["colormap"] == "viridis"


def test_reset_restores_defaults(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    config.update(123, fmin=100)
    config.reset(123)
    assert config.get(123) == config.DEFAULTS


def test_defaults_never_written_to_storage(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    config.update(123, fmin=100)
    stored = config._load()["chats"]["123"]
    assert stored == {"fmin": 100}
