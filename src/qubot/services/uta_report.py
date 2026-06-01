"""Build a Discord Embed from a UTA Snapshot."""

from __future__ import annotations

import discord

from qubot.services.uta import UtaSnapshot

COLOR_OK = 0x2ECC71       # green — plant running, no alarms
COLOR_ALARM = 0xE74C3C    # red — any active alarm
COLOR_NEUTRAL = 0x95A5A6  # grey — stopped without alarms


def _f(value: float | None, precision: int = 2) -> str:
    return "N/A" if value is None else f"{value:.{precision}f}"


def _state_section(snap: UtaSnapshot) -> str:
    lines: list[str] = []
    if snap.is_running:
        lines.append(
            f":green_circle: **Plant running** (Auto = {snap.iauto}, Aux = {snap.ausiliari})"
        )
    else:
        faults: list[str] = []
        if not snap.marcia:
            faults.append(f"Plant stopped (Auto = {snap.iauto}, Aux = {snap.ausiliari})")
        if not snap.inverterin:
            faults.append("Return inverter stopped")
        if not snap.inverterout:
            faults.append("Supply inverter stopped")
        if snap.termalarm:
            faults.append("Cumulative thermal alarm")
        if snap.notifier:
            faults.append("NOTIFIER central alarm")
        if snap.incendio:
            faults.append("Return-air fire alarm")
        if snap.alinverterin or snap.alinverterout:
            faults.append(
                f"Inverter alarm (return = {snap.alinverterin}, supply = {snap.alinverterout})"
            )
        if not faults:
            faults.append("Plant stopped")
        lines.append(":red_circle: **Plant fault**")
        lines.extend(f"- {f}" for f in faults)
    lines.append(f"Fan coil: **{'ON' if snap.fancoil else 'OFF'}**")
    return "\n".join(lines)


def _temperatures_section(snap: UtaSnapshot) -> str:
    if snap.stagione:
        setpoint, season_label = snap.sp_winter, "winter"
    else:
        setpoint, season_label = snap.sp_summer, "summer"
    return "\n".join([
        f"- **Lab**: {_f(snap.t_lab)} °C (SP {season_label}: {_f(setpoint)} °C)",
        f"- **Pumps room**: {_f(snap.t_pumps_room)} °C",
        f"- **External**: {_f(snap.t_external)} °C",
        f"- **Cold water**: {_f(snap.t_water_cold)} °C",
        f"- **Hot water**: {_f(snap.t_water_hot)} °C",
        f"- **Pre-heat coil**: {_f(snap.t_preheat)} °C "
        f"(SP {_f(snap.sp_preheat)} °C, valve {_f(snap.valve_preheat, 1)} %)",
        f"- **Cooling coil**: {_f(snap.t_cool)} °C "
        f"(valve {_f(snap.valve_cool, 1)} %)",
        f"- **Supply duct**: {_f(snap.t_supply)} °C "
        f"(SP {_f(snap.sp_supply)} °C, valve {_f(snap.valve_supply, 1)} %)",
    ])


def _flow_section(snap: UtaSnapshot) -> str:
    return "\n".join([
        f"- **Supply flow**: {_f(snap.flow_supply, 1)} m³/h",
        f"- **Return flow**: {_f(snap.flow_return, 1)} m³/h",
        f"- **Pocket filter ΔP**: {_f(snap.dp_pocket)} Pa",
        f"- **Absolute filter ΔP**: {_f(snap.dp_absolute)} Pa",
    ])


def _air_quality_section(snap: UtaSnapshot) -> str:
    return "\n".join([
        f"- **Humidity**: {_f(snap.humidity, 1)} %",
        f"- **CO₂**: {_f(snap.co2, 1)} ppm",
    ])


def _chiller_section(snap: UtaSnapshot) -> str:
    lines: list[str] = []
    if snap.chiller_running:
        lines.append(":green_circle: **Cooling water plant running**")
    else:
        faults: list[str] = []
        if not snap.frigoon:
            faults.append("Cooling water plant stopped")
        if snap.valvemerginacquedotto:
            faults.append("Bypass: water intake from aqueduct")
        if snap.valvemergout:
            faults.append("Bypass: water drain to aqueduct")
        if snap.frigoalarm:
            faults.append("Chiller unit alarm")
        if snap.frigotermico:
            faults.append("Chiller thermal alarm")
        if snap.pompaalarm:
            faults.append("Circulation pump alarm")
        if not faults:
            faults.append("Cooling water plant stopped")
        lines.append(":red_circle: **Cooling water fault**")
        lines.extend(f"- {f}" for f in faults)
    lines.append(f"- **Chiller water temperature**: {_f(snap.t_water_chiller, 1)} °C")
    return "\n".join(lines)


def build_uta_embed(snap: UtaSnapshot, cgi_url: str | None = None) -> discord.Embed:
    """Render the UTA snapshot as a Discord embed."""
    if snap.any_alarm or snap.any_alarm_chiller:
        color = COLOR_ALARM
    elif snap.is_running:
        color = COLOR_OK
    else:
        color = COLOR_NEUTRAL

    embed = discord.Embed(
        title="🌬️ **Report - UTA Cryogenic Laboratory**",
        description=snap.timestamp.strftime("%a %Y-%m-%d %H:%M:%S %Z"),
        color=color,
    )
    embed.add_field(name="**STATE**", value=_state_section(snap), inline=False)
    embed.add_field(name="**TEMPERATURES**", value=_temperatures_section(snap), inline=False)
    embed.add_field(name="**FLOW & PRESSURE**", value=_flow_section(snap), inline=False)
    embed.add_field(name="**AIR QUALITY**", value=_air_quality_section(snap), inline=False)
    embed.add_field(name="**CHILLER**", value=_chiller_section(snap), inline=False)
    if cgi_url:
        embed.add_field(
            name="**RESOURCES**",
            value=f"- **[Full Report]({cgi_url})**",
            inline=False,
        )
    return embed
