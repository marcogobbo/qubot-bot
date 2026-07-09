"""Per-fridge personalization: sensors, labels, quantities, display options.

Loaded from `config/<fridge_name>.yaml`. Each fridge can show a different
subset of sensors with custom labels and quantities. Display units are picked
automatically from the quantity's SI-prefix table (see `core.units`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from qubot.core.units import QUANTITIES

Quantity = Literal["temperature", "pressure", "power", "magnetic_field", "flow"]


class Resource(BaseModel):
    """A resource link entry."""

    label: str
    url: str


class SensorSpec(BaseModel):
    """A single sensor entry on the report.

    `uri_key` is the attribute name on the Proteox client (e.g. `mixing_chamber`,
    `still`, `ovc`). The bot calls `client.get_<uri_key>()`.

    `quantity` selects which SI-prefix table is used for display. The bot
    auto-scales to the largest prefix where the mantissa stays >= 1.

    `from_base_scale` is a multiplier applied to the raw value before prefix
    selection — needed when qtics returns a unit different from the quantity's
    base (e.g. flow as mol/s but displayed in μmol/s → 1e6).
    """

    uri_key: str
    label: str
    quantity: Quantity
    precision: int = 3
    from_base_scale: float = 1.0


class FridgeProfile(BaseModel):
    """Personalized display profile for one fridge."""

    name: str  # canonical lowercase key (elsa/anna/olaf)
    display_name: str
    color: int = 0x3498DB
    # Which configured temperature uri_key represents the Pulse-tube 2 stage.
    # Used by the scheduler's warm-fridge skip (IDLE + PT2 > 273 K).
    pt2_key: str = "PT2_T1"
    temperatures: list[SensorSpec] = Field(default_factory=list)
    pressures: list[SensorSpec] = Field(default_factory=list)
    heaters: list[SensorSpec] = Field(default_factory=list)
    flow: list[SensorSpec] = Field(default_factory=list)
    resources: list[Resource] = Field(default_factory=list)
    footer: str = ""

    def all_sections(self) -> list[tuple[str, list[SensorSpec]]]:
        """(field_label, specs) pairs in display order. Empty sections still appear
        so callers can decide whether to render them."""
        return [
            ("Temperatures", self.temperatures),
            ("Pressures", self.pressures),
            ("Heaters", self.heaters),
            ("Flow", self.flow),
        ]

    def has_resources(self) -> bool:
        return len(self.resources) > 0


def load_profile(name: str, config_dir: Path) -> FridgeProfile:
    """Load `<config_dir>/<name>.yaml` into a FridgeProfile."""
    path = config_dir / f"{name}.yaml"
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    data.setdefault("name", name)
    profile = FridgeProfile(**data)
    _validate_quantities(profile)
    return profile


def load_all_profiles(names: list[str], config_dir: Path) -> dict[str, FridgeProfile]:
    return {name: load_profile(name, config_dir) for name in names}


def _validate_quantities(profile: FridgeProfile) -> None:
    """Sanity-check that every SensorSpec.quantity has a prefix table."""
    for _, specs in profile.all_sections():
        for spec in specs:
            if spec.quantity not in QUANTITIES:
                raise ValueError(
                    f"{profile.name}/{spec.uri_key}: unknown quantity {spec.quantity!r}"
                )
