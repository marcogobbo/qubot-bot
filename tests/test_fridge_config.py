"""Tests for ``qubot.core.fridge_config`` — YAML profile loading + validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from qubot.core.fridge_config import FridgeProfile, load_profile

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@pytest.mark.parametrize("name", ["elsa", "anna", "olaf"])
def test_load_real_profiles(name):
    profile = load_profile(name, CONFIG_DIR)
    assert profile.name == name
    assert profile.display_name  # non-empty
    # The scheduler's warm-fridge gate keys off PT2.
    assert profile.pt2_key == "PT2_T1"
    # mixing_chamber_key was removed; it must not resurface as a field.
    assert not hasattr(profile, "mixing_chamber_key")
    # Every fridge defines at least one temperature sensor.
    assert profile.temperatures


def test_pt2_key_defaults_when_omitted():
    profile = FridgeProfile(name="x", display_name="X")
    assert profile.pt2_key == "PT2_T1"


def test_unknown_quantity_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "display_name: Bad\n"
        "temperatures:\n"
        "  - { uri_key: T1, label: T1, quantity: not_a_quantity }\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not_a_quantity"):
        load_profile("bad", tmp_path)


def test_load_fills_name_from_filename(tmp_path):
    p = tmp_path / "fridgey.yaml"
    p.write_text("display_name: Fridgey\n", encoding="utf-8")
    profile = load_profile("fridgey", tmp_path)
    assert profile.name == "fridgey"
    assert profile.display_name == "Fridgey"
