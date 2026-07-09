"""Tests for ``qubot.core.settings`` — env-driven loading and per-fridge skip.

Each test runs in a clean temp cwd (so the repo's real ``.env`` is never picked
up) and clears any fridge/credential env vars that might leak from the shell.
"""

from __future__ import annotations

import pytest

from qubot.core.settings import FRIDGE_NAMES, Settings

# Env var suffixes a fully-configured fridge needs.
_FRIDGE_SUFFIXES = ("PROTEOX_URL", "PROTEOX_REALM", "DESTINATION_ID", "DESTINATION_TYPE")
_BASE_VARS = ("DISCORD_TOKEN", "WAMP_USER", "WAMP_USER_SECRET", "WAMP_REALM")


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    """Isolate settings loading: empty cwd + no relevant env vars set."""
    monkeypatch.chdir(tmp_path)
    for var in _BASE_VARS:
        monkeypatch.delenv(var, raising=False)
    for name in FRIDGE_NAMES:
        for suffix in _FRIDGE_SUFFIXES:
            monkeypatch.delenv(f"{name.upper()}_{suffix}", raising=False)
    # Minimal top-level required fields.
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("WAMP_USER", "user")
    monkeypatch.setenv("WAMP_USER_SECRET", "secret")
    return monkeypatch


def _configure_fridge(monkeypatch, name: str, dest_id: int, dest_type: str = "channel"):
    up = name.upper()
    monkeypatch.setenv(f"{up}_PROTEOX_URL", f"ws://{name}.example/ws")
    monkeypatch.setenv(f"{up}_DESTINATION_ID", str(dest_id))
    monkeypatch.setenv(f"{up}_DESTINATION_TYPE", dest_type)


def test_full_fridge_is_loaded(clean_env):
    _configure_fridge(clean_env, "elsa", 12345, "thread")
    settings = Settings.load()

    assert set(settings.fridges) == {"elsa"}
    elsa = settings.fridges["elsa"]
    assert elsa.destination_id == 12345
    assert elsa.destination_type == "thread"
    assert elsa.proteox_url == "ws://elsa.example/ws"
    # Default realm applied.
    assert elsa.proteox_realm == "ucss"


def test_incomplete_fridge_is_skipped_not_fatal(clean_env):
    # anna fully configured; elsa missing its DESTINATION_ID.
    _configure_fridge(clean_env, "anna", 999)
    clean_env.setenv("ELSA_PROTEOX_URL", "ws://elsa.example/ws")
    clean_env.setenv("ELSA_DESTINATION_TYPE", "channel")

    settings = Settings.load()

    assert "anna" in settings.fridges
    assert "elsa" not in settings.fridges


def test_no_fridges_configured_raises(clean_env):
    with pytest.raises(RuntimeError, match="No fridges configured"):
        Settings.load()


def test_invalid_destination_type_skips_fridge(clean_env):
    _configure_fridge(clean_env, "olaf", 1)  # valid anchor so load() succeeds
    _configure_fridge(clean_env, "elsa", 2, dest_type="carrier-pigeon")

    settings = Settings.load()

    assert "olaf" in settings.fridges
    assert "elsa" not in settings.fridges
