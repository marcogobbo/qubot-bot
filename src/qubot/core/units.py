"""Auto-scaled SI-prefix formatting for sensor values.

Each `quantity` (temperature, pressure, power, magnetic_field, flow) has a
table of (factor, label) prefixes sorted descending by factor. The formatter
picks the largest prefix whose factor is <= |value|, so the displayed
mantissa stays >= 1 (e.g. 0.9 K renders as 900 mK).

If the raw value comes in a unit other than the quantity's base unit, pass
`from_base_scale` to convert (e.g. flow returned as mol/s but displayed as
μmol/s → from_base_scale=1e6).
"""

from __future__ import annotations

Quantity = str  # "temperature" | "pressure" | "power" | "magnetic_field" | "flow"

# Each list is sorted descending by factor. The final entry is the smallest
# prefix and is used as a fallback for sub-prefix values and for "0 …".
QUANTITIES: dict[Quantity, list[tuple[float, str]]] = {
    "temperature":    [(1.0,  "K"),   (1e-3, "mK")],
    "pressure":       [(1e3,  "kPa"), (1.0,  "Pa")],
    "power":          [(1.0,  "W"),   (1e-3, "mW"),  (1e-6, "μW"),
                       (1e-9, "nW"),  (1e-12, "pW")],
    "magnetic_field": [(1.0,  "T"),   (1e-3, "mT")],
    "flow":           [(1.0,  "μmol/s")],
}


def format_value(
    raw: float | None,
    quantity: Quantity,
    precision: int = 3,
    from_base_scale: float = 1.0,
) -> str:
    """Format `raw` using the quantity's SI-prefix table.

    Args:
        raw: value as returned by the qtics getter (None means read failed).
        quantity: which prefix table to use.
        precision: decimal places shown.
        from_base_scale: multiplier applied before prefix selection. Use this
            when the raw value's unit differs from the quantity's base unit
            (e.g. mol/s → μmol/s: from_base_scale=1e6).

    Returns:
        Formatted string, or "N/A" if raw is None, or "Out of range" if raw == 0.
    """
    if raw is None:
        return "N/A"

    if raw == 0:
        return "Out of range"

    if quantity not in QUANTITIES:
        raise ValueError(f"unknown quantity: {quantity!r}")
    prefixes = QUANTITIES[quantity]

    v = raw * from_base_scale
    av = abs(v)
    for factor, label in prefixes:
        if av >= factor:
            return f"{v / factor:.{precision}f} {label}"

    # Below the smallest prefix — still use it (numbers will be < 1).
    factor, label = prefixes[-1]
    return f"{v / factor:.{precision}f} {label}"
