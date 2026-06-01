"""UTA (Unità Trattamento Aria — HVAC) snapshot service.

Scrapes the legacy CGI at `<UTA_CGI_URL>` (originally
`uta/utareport_html.c`), strips HTML tags, and pulls values + alarm phrases
out via regex. The C program itself FTP-pulls SQLite DBs from the controller,
but those FTP data ports aren't reachable from outside the lab LAN — going
through the CGI reuses an already-deployed bridge that has direct access.
"""

from __future__ import annotations

import asyncio
import html as html_lib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import aiohttp

from qubot.core.logging_setup import get_logger

if TYPE_CHECKING:
    from qubot.core.settings import Settings


log = get_logger("services.uta")

_NUM = r"(-?\d+(?:\.\d+)?)"


@dataclass
class UtaSnapshot:
    """Latest UTA reading parsed from the CGI HTML.

    Analog fields are floats (None if absent / unparseable). Digital fields
    are 0/1 ints derived from the presence of specific alarm/state phrases.
    """

    timestamp: datetime
    # Analog
    t_lab: float | None = None
    t_pumps_room: float | None = None
    t_external: float | None = None
    t_water_cold: float | None = None
    t_water_hot: float | None = None
    t_water_chiller: float | None = None
    t_preheat: float | None = None
    sp_preheat: float | None = None
    valve_preheat: float | None = None
    t_cool: float | None = None
    valve_cool: float | None = None
    t_supply: float | None = None
    sp_supply: float | None = None
    valve_supply: float | None = None
    sp_summer: float | None = None
    sp_winter: float | None = None
    flow_supply: float | None = None
    flow_return: float | None = None
    dp_pocket: float | None = None
    dp_absolute: float | None = None
    humidity: float | None = None
    co2: float | None = None
    # Digital state — inferred from textual phrases in the CGI HTML
    stagione: int = 0
    marcia: int = 0
    iauto: int = 0
    ausiliari: int = 0
    inverterin: int = 0
    inverterout: int = 0
    fancoil: int = 0
    termalarm: int = 0
    notifier: int = 0
    incendio: int = 0
    alinverterin: int = 0
    alinverterout: int = 0
    generalarm: int = 0
    frigoon: int = 0
    frigoalarm: int = 0
    frigotermico: int = 0
    valvemergout: int = 0
    valvemerginacquedotto: int = 0
    pompaalarm: int = 0

    @property
    def any_alarm(self) -> bool:
        return bool(
            self.termalarm or self.notifier or self.incendio
            or self.alinverterin or self.alinverterout or self.generalarm
        )

    @property
    def any_alarm_chiller(self) -> bool:
        return bool(
            self.frigoalarm or self.frigotermico
            or self.valvemerginacquedotto or self.valvemergout
            or self.pompaalarm
        )

    @property
    def is_running(self) -> bool:
        return bool(
            self.marcia and self.inverterin and self.inverterout
            and not self.any_alarm
        )

    @property
    def chiller_running(self) -> bool:
        return bool(
            self.frigoon and not self.valvemerginacquedotto
            and not self.valvemergout and not self.any_alarm_chiller
        )


def _strip_html(html_text: str) -> str:
    """Drop tags and decode entities so simple regexes can match labels."""
    text = re.sub(r"<[^>]+>", " ", html_text)
    return html_lib.unescape(text)


def _grab(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except (TypeError, ValueError):
        return None


def parse_uta_html(html_text: str, tz: ZoneInfo) -> UtaSnapshot:
    """Parse the CGI HTML into a UtaSnapshot. Tolerant of missing fields."""
    text = _strip_html(html_text)

    # Timestamp like "Thu 2026-05-14 12:31:15 CEST" — parse just the date+time.
    m = re.search(r"\b(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\b", text)
    if m:
        ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
    else:
        ts = datetime.now(tz=tz)

    season = 1 if "SP inverno" in text else 0

    # Plant state — inferred from alarm phrases printed by utareport_html.c.
    marcia = 0 if "Impianto fermo" in text else (1 if "Impianto in marcia" in text else 0)
    inverterin = 0 if "Inverter ripresa fermo" in text else 1
    inverterout = 0 if "Inverter mandata fermo" in text else 1
    termalarm = 1 if "Cumulativo allarme termiche" in text else 0
    notifier = 1 if "Allarme centrale NOTIFIER" in text else 0
    incendio = 1 if "Allarme antincendio ripresa" in text else 0

    m = re.search(r"Allarme inverter \(ripresa:\s*(\d+)\s*::\s*mandata:\s*(\d+)\)", text)
    if m:
        alinverterin, alinverterout = int(m.group(1)), int(m.group(2))
    else:
        alinverterin = alinverterout = 0

    fancoil = 1 if re.search(r"Fancoil:\s*ON", text) else 0

    m = re.search(r"Sel AUTO\s*=\s*(\d+)\s*::\s*ausiliari\s*=\s*(\d+)", text)
    iauto = int(m.group(1)) if m else 0
    ausiliari = int(m.group(2)) if m else 0

    # Chiller. "Allarme gruppo frigo" and "Allarme termico gruppo frigo" are
    # distinct phrases — the latter doesn't contain the former as a substring,
    # so simple `in` checks discriminate correctly.
    frigotermico = 1 if "Allarme termico gruppo frigo" in text else 0
    frigoalarm = 1 if "Allarme gruppo frigo" in text else 0
    pompaalarm = 1 if "Allarme pompa circolazione" in text else 0
    valvemerginacquedotto = 1 if "By-pass carico acqua acquedotto" in text else 0
    valvemergout = 1 if "By-pass scarico acqua acquedotto" in text else 0
    if "Impianto H2O raffreddamento in funzione" in text:
        frigoon = 1
    elif "Impianto H2O raffreddamento fermo" in text:
        frigoon = 0
    else:
        frigoon = 1  # CGI only prints stop-phrase when chiller is off

    # Sensors
    t_lab = _grab(r"T laboratorio.*?:\s*" + _NUM, text)
    m = re.search(r"\(SP\s+(?:inverno|estate)\s+" + _NUM + r"\)", text)
    setpoint = float(m.group(1)) if m else None
    sp_winter = setpoint if season == 1 else None
    sp_summer = setpoint if season == 0 else None

    t_pumps_room = _grab(r"T locale pompe.*?:\s*" + _NUM, text)
    t_external = _grab(r"T esterna.*?:\s*" + _NUM, text)
    t_water_cold = _grab(r"T acqua fredda.*?:\s*" + _NUM, text)
    t_water_hot = _grab(r"T acqua calda.*?:\s*" + _NUM, text)

    m = re.search(
        r"Preriscaldamento.*?:\s*" + _NUM + r"\s*\(\s*" + _NUM + r"\s*\)\s*" + _NUM,
        text,
    )
    t_preheat = float(m.group(1)) if m else None
    sp_preheat = float(m.group(2)) if m else None
    valve_preheat = float(m.group(3)) if m else None

    m = re.search(
        r"Raffreddamento.*?:\s*" + _NUM + r"\s*\([^)]*\)\s*" + _NUM,
        text,
    )
    t_cool = float(m.group(1)) if m else None
    valve_cool = float(m.group(2)) if m else None

    m = re.search(
        r"Canale Mandata.*?:\s*" + _NUM + r"\s*\(\s*" + _NUM + r"\s*\)\s*" + _NUM,
        text,
    )
    t_supply = float(m.group(1)) if m else None
    sp_supply = float(m.group(2)) if m else None
    valve_supply = float(m.group(3)) if m else None

    # The C code's printf has a typo: ":: rirpresa %6.1f". Allow any short
    # run of i/r between the leading 'r' and "presa" so we tolerate the typo
    # if it ever gets fixed upstream.
    m = re.search(
        r"portata.*?mandata\s+" + _NUM + r"\s*::\s*r[ir]+presa\s+" + _NUM,
        text,
    )
    flow_supply = float(m.group(1)) if m else None
    flow_return = float(m.group(2)) if m else None

    dp_pocket = _grab(r"DP filtri a tasca.*?:\s*" + _NUM, text)
    dp_absolute = _grab(r"DP filtri assoluti.*?:\s*" + _NUM, text)
    humidity = _grab(r"Umidit[àa].*?:\s*" + _NUM, text)
    co2 = _grab(r"CO2 mand.*?:\s*" + _NUM, text)
    t_water_chiller = _grab(r"Temperatura H2[0O].*?:\s*" + _NUM, text)

    return UtaSnapshot(
        timestamp=ts,
        t_lab=t_lab, t_pumps_room=t_pumps_room, t_external=t_external,
        t_water_cold=t_water_cold, t_water_hot=t_water_hot,
        t_water_chiller=t_water_chiller,
        t_preheat=t_preheat, sp_preheat=sp_preheat, valve_preheat=valve_preheat,
        t_cool=t_cool, valve_cool=valve_cool,
        t_supply=t_supply, sp_supply=sp_supply, valve_supply=valve_supply,
        sp_summer=sp_summer, sp_winter=sp_winter,
        flow_supply=flow_supply, flow_return=flow_return,
        dp_pocket=dp_pocket, dp_absolute=dp_absolute,
        humidity=humidity, co2=co2,
        stagione=season,
        marcia=marcia, iauto=iauto, ausiliari=ausiliari,
        inverterin=inverterin, inverterout=inverterout, fancoil=fancoil,
        termalarm=termalarm, notifier=notifier, incendio=incendio,
        alinverterin=alinverterin, alinverterout=alinverterout,
        frigoon=frigoon, frigoalarm=frigoalarm, frigotermico=frigotermico,
        valvemergout=valvemergout, valvemerginacquedotto=valvemerginacquedotto,
        pompaalarm=pompaalarm,
    )


async def fetch_uta_snapshot(settings: "Settings") -> UtaSnapshot:
    """Fetch the latest UTA snapshot via HTTP GET to the legacy CGI.

    Raises RuntimeError on network failure or HTTP error.
    """
    url = settings.uta_cgi_url
    if not url:
        raise RuntimeError("CGI URL is not configured (set UTA_CGI_URL).")
    log.info("fetching UTA report from %s", url)
    timeout = aiohttp.ClientTimeout(total=settings.uta_cgi_timeout)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                html_text = await resp.text(errors="replace")
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        raise RuntimeError("controller is not responding. Please check the network.") from exc

    snap = parse_uta_html(html_text, ZoneInfo(settings.daily_report_tz))
    log.info(
        "snapshot ok: marcia=%s any_alarm=%s frigoon=%s any_alarm_chiller=%s",
        snap.marcia, snap.any_alarm, snap.frigoon, snap.any_alarm_chiller,
    )
    return snap
