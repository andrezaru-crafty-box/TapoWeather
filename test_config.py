"""The credential handling is the part that would be embarrassing to get wrong."""

import json

import pytest

from tapo_weather.config import DEFAULT_PRESETS, Settings, load_env_file


def test_settings_default_to_preview_mode(monkeypatch):
    for key in ("TAPO_USERNAME", "TAPO_PASSWORD", "TAPO_IPS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("tapo_weather.config.load_env_file", lambda *a, **k: None)
    s = Settings.from_env()
    assert s.username == ""
    assert s.password == ""
    assert s.ips == []


def test_repr_never_leaks_the_password():
    s = Settings(username="someone@example.com", password="hunter2",
                 ips=["10.0.0.1", "10.0.0.2"])
    text = repr(s)
    assert "hunter2" not in text
    assert "password=<set>" in text
    # nor should the bulb addresses, which map your home network
    assert "10.0.0.1" not in text


def test_repr_of_an_empty_password_says_unset():
    assert "password=<unset>" in repr(Settings())


def test_env_file_is_parsed_but_never_overrides_the_real_environment(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# a comment\n"
        "\n"
        "TAPO_USERNAME=file@example.com\n"
        'TAPO_PASSWORD="quoted secret"\n'
        "export TAPO_IPS=192.168.1.5\n"
        "MALFORMED_LINE\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TAPO_USERNAME", "real@example.com")
    monkeypatch.delenv("TAPO_PASSWORD", raising=False)
    monkeypatch.delenv("TAPO_IPS", raising=False)

    load_env_file(env)

    import os
    assert os.environ["TAPO_USERNAME"] == "real@example.com"   # env wins
    assert os.environ["TAPO_PASSWORD"] == "quoted secret"      # quotes stripped
    assert os.environ["TAPO_IPS"] == "192.168.1.5"             # export handled


def test_missing_env_file_is_not_an_error(tmp_path):
    load_env_file(tmp_path / "nothing-here")


def test_ips_are_split_and_trimmed(monkeypatch):
    monkeypatch.setattr("tapo_weather.config.load_env_file", lambda *a, **k: None)
    monkeypatch.setenv("TAPO_IPS", " 10.0.0.1 , 10.0.0.2 ,, ")
    assert Settings.from_env().ips == ["10.0.0.1", "10.0.0.2"]


def test_bad_numbers_fall_back_instead_of_crashing(monkeypatch):
    monkeypatch.setattr("tapo_weather.config.load_env_file", lambda *a, **k: None)
    monkeypatch.setenv("LAMP_PORT", "not-a-port")
    assert Settings.from_env().port == 8765


def test_local_presets_take_priority(tmp_path, monkeypatch):
    local = tmp_path / "presets.local.json"
    local.write_text(json.dumps([{"label": "Mine", "lat": 1.0, "lon": 2.0}]), encoding="utf-8")
    monkeypatch.setattr("tapo_weather.config.LOCAL_PRESETS_FILE", local)
    monkeypatch.setattr("tapo_weather.config.PRESETS_FILE", tmp_path / "presets.json")
    from tapo_weather.config import load_presets
    assert load_presets()[0]["label"] == "Mine"


def test_broken_presets_file_falls_back_to_the_builtin(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "presets.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr("tapo_weather.config.LOCAL_PRESETS_FILE", tmp_path / "absent.json")
    monkeypatch.setattr("tapo_weather.config.PRESETS_FILE", bad)
    from tapo_weather.config import load_presets
    assert load_presets() == DEFAULT_PRESETS


def test_no_credentials_are_hardcoded_anywhere_in_the_package():
    """A regression guard: this project once had an email address in its source."""
    import re
    from pathlib import Path

    package = Path(__file__).resolve().parent.parent / "tapo_weather"
    email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    private_ip = re.compile(r"\b(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b")

    for path in package.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not email.search(text), f"an email address is sitting in {path.name}"
        assert not private_ip.search(text), f"a LAN address is sitting in {path.name}"
