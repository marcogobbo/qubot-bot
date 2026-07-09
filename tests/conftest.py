"""Shared fixtures and sample data for the QuBot test suite.

Heavy, optional-dependency imports (anything that pulls in ``qtics`` via
``qubot.services.proteox``) are kept *out* of this module so the pure-logic
tests still collect even when those packages are unavailable. Such imports live
inside the individual test modules that need them.
"""

from __future__ import annotations

import textwrap

import pytest

# --- Sample UTA CGI HTML -----------------------------------------------------
# Trimmed but structurally faithful renderings of what utareport_html.c emits.
# parse_uta_html() first strips tags, so the exact markup is irrelevant — only
# the label strings and numbers matter.

UTA_HTML_RUNNING = textwrap.dedent(
    """\
    <html><body>
    <p>Thu 2026-05-14 12:31:15 CEST</p>
    <p>Impianto in marcia</p>
    <p>Sel AUTO = 1 :: ausiliari = 0</p>
    <p>Fancoil: ON</p>
    <p>T laboratorio: 21.4</p>
    <p>(SP estate 24.0)</p>
    <p>T locale pompe: 19.2</p>
    <p>T esterna: 27.8</p>
    <p>T acqua fredda: 7.1</p>
    <p>T acqua calda: 41.0</p>
    <p>Preriscaldamento: 22.0 ( 23.0 ) 10.0</p>
    <p>Raffreddamento: 18.5 ( x ) 40.0</p>
    <p>Canale Mandata: 20.1 ( 21.0 ) 55.0</p>
    <p>portata mandata 1200.0 :: ripresa 1100.0</p>
    <p>DP filtri a tasca: 120.0</p>
    <p>DP filtri assoluti: 80.0</p>
    <p>Umidita: 45.0</p>
    <p>CO2 mand: 480.0</p>
    <p>Temperatura H2O: 6.5</p>
    <p>Impianto H2O raffreddamento in funzione</p>
    </body></html>
    """
)

# Winter season, plant stopped, multiple alarms, chiller off.
UTA_HTML_ALARM_WINTER = textwrap.dedent(
    """\
    <html><body>
    <p>Mon 2026-01-12 08:05:00 CET</p>
    <p>Impianto fermo</p>
    <p>SP inverno</p>
    <p>(SP inverno 20.0)</p>
    <p>Inverter ripresa fermo</p>
    <p>Inverter mandata fermo</p>
    <p>Cumulativo allarme termiche</p>
    <p>Allarme centrale NOTIFIER</p>
    <p>Allarme inverter (ripresa: 1 :: mandata: 0)</p>
    <p>Allarme termico gruppo frigo</p>
    <p>Impianto H2O raffreddamento fermo</p>
    <p>T laboratorio: 19.0</p>
    </body></html>
    """
)

# No recognizable timestamp and almost no fields — exercises fallbacks.
UTA_HTML_SPARSE = "<html><body><p>nothing useful here</p></body></html>"


@pytest.fixture
def uta_html_running() -> str:
    return UTA_HTML_RUNNING


@pytest.fixture
def uta_html_alarm_winter() -> str:
    return UTA_HTML_ALARM_WINTER


@pytest.fixture
def uta_html_sparse() -> str:
    return UTA_HTML_SPARSE
