"""Thin async wrapper around the qtics Proteox client.

Exposes one method per concern (status, sensors), bundles results in a
typed snapshot, and isolates the rest of the bot from qtics internals.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from qtics.instruments.network.proteox.proteox import Proteox  # type: ignore[import-not-found]

from qubot.core.fridge_config import FridgeProfile, SensorSpec
from qubot.core.logging_setup import get_logger
from qubot.core.settings import FridgeConnection
from qubot.core.units import format_value


@dataclass
class SensorReading:
    spec: SensorSpec
    value: float | None  # None if the read failed

    def formatted(self) -> str:
        # For heaters, show "OFF" instead of "Out of range" when value is 0
        if self.value == 0 and self.spec.quantity == "power":
            return "OFF"
        return format_value(
            self.value,
            quantity=self.spec.quantity,
            precision=self.spec.precision,
            from_base_scale=self.spec.from_base_scale,
        )


@dataclass
class Snapshot:
    """Result of reading one fridge once."""

    fridge_name: str
    states: list[str]
    temperatures: list[SensorReading] = field(default_factory=list)
    pressures: list[SensorReading] = field(default_factory=list)
    heaters: list[SensorReading] = field(default_factory=list)
    flow: list[SensorReading] = field(default_factory=list)

    @property
    def status(self) -> str:
        """Best-effort single status label (first recognized state or 'Unknown')."""
        return self.states[0] if self.states else "Unknown"

    @property
    def is_idle(self) -> bool:
        """True if any recognized state name starts with 'IDLE' or 'Idle' (case-insensitive)."""
        return any(s.upper().startswith("IDLE") for s in self.states)

    def temperature_value(self, uri_key: str) -> float | None:
        for r in self.temperatures:
            if r.spec.uri_key == uri_key:
                return r.value
        return None

    def mixing_chamber_value(self, mixing_chamber_key: str) -> float | None:
        return self.temperature_value(mixing_chamber_key)

    def sections(self) -> list[tuple[str, list[SensorReading]]]:
        """(label, readings) pairs in display order. Callers skip empty ones."""
        return [
            ("Temperatures", self.temperatures),
            ("Pressures",    self.pressures),
            ("Heaters",      self.heaters),
            ("Flow",         self.flow),
        ]


class ProteoxService:
    """One-shot async client for a single fridge.

    Use as `async with ProteoxService(conn, profile) as svc: snap = await svc.snapshot()`.
    Each context manager entry opens a fresh WAMP session and closes it on exit.
    """

    def __init__(self, conn: FridgeConnection, profile: FridgeProfile) -> None:
        self._conn = conn
        self._profile = profile
        self._client: Any | None = None
        self._log = get_logger(f"proteox.{profile.name}")

    # Hard timeout for the WAMP connection handshake. autobahn's internal
    # warning ("WebSocket opening handshake timeout") does not propagate as an
    # exception, so we wrap the connect() call to force a TimeoutError.
    _CONNECT_TIMEOUT_S = 10.0

    async def __aenter__(self) -> "ProteoxService":
        self._log.info(
            "connecting to %s (realm=%s)", self._conn.proteox_url, self._conn.proteox_realm
        )
        self._client = Proteox(url=self._conn.proteox_url, realm=self._conn.proteox_realm)
        try:
            await asyncio.wait_for(self._client.connect(), timeout=self._CONNECT_TIMEOUT_S)
        except asyncio.TimeoutError:
            self._log.error("connection timeout to %s", self._conn.proteox_url)
            raise RuntimeError(
                "is not responding. Please check the network."
            ) from None
        except Exception as exc:  # noqa: BLE001
            exc_str = str(exc).lower()
            if any(kw in exc_str for kw in ["timeout", "handshake", "refused", "unreachable"]):
                self._log.error("connection error to %s: %s", self._conn.proteox_url, exc)
                raise RuntimeError(
                    "is not responding. Please check the network."
                ) from None
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:  # noqa: BLE001 — best-effort cleanup
                self._log.warning("error during close", exc_info=True)
            self._client = None

    async def _read(self, spec: SensorSpec) -> SensorReading:
        assert self._client is not None
        getter_name = f"get_{spec.uri_key}"
        try:
            getter = getattr(self._client, getter_name)
            value = await getter()
            return SensorReading(spec=spec, value=float(value))
        except Exception:  # noqa: BLE001
            self._log.warning("failed to read sensor %s", spec.uri_key, exc_info=True)
            return SensorReading(spec=spec, value=None)

    async def _read_many(self, specs: list[SensorSpec]) -> list[SensorReading]:
        return [await self._read(s) for s in specs]

    async def _is_local(self) -> bool:
        state = await self._client.get_state()
        return state is None or "None" in str(state)

    async def recognized_status(self) -> tuple[bool, list[str]] | None:
        """Return (is_in_recognized_state, matched_state_names), or None if LOCAL."""
        assert self._client is not None
        if await self._is_local():
            return None
        is_rec = await self._client.is_in_recognized_state()
        names = await self._client.get_recognized_states()
        return is_rec, list(names)

    async def transition_plan(self, target_state: str | None) -> dict | None:
        """Return the structured transition plan, or None if LOCAL."""
        assert self._client is not None
        if await self._is_local():
            return None
        return await self._client.recognized_states.get_transition_plan(target_state)

    async def snapshot(self) -> Snapshot:
        """Fetch status + all configured sensors for the fridge."""
        assert self._client is not None
        try:
            state = await self._client.get_state()
            states = [str(state)] if state is not None else []
        except Exception:  # noqa: BLE001
            self._log.warning("failed to read state", exc_info=True)
            states = []

        snap = Snapshot(fridge_name=self._profile.name, states=states)

        # When the instrument is in LOCAL mode the server closes the WAMP
        # session immediately after returning state; skip sensor reads to
        # avoid a flood of "closed protocol" warnings.
        if snap.status == "Unknown" or "None" in snap.status:
            self._log.info("system is in LOCAL mode — skipping sensor reads")
            return snap

        snap.temperatures = await self._read_many(self._profile.temperatures)
        snap.pressures = await self._read_many(self._profile.pressures)
        snap.heaters = await self._read_many(self._profile.heaters)
        snap.flow = await self._read_many(self._profile.flow)

        self._log.info(
            "snapshot ok: status=%s temps=%d pressures=%d heaters=%d flow=%d",
            snap.status,
            len(snap.temperatures),
            len(snap.pressures),
            len(snap.heaters),
            len(snap.flow),
        )
        return snap
