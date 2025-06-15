import asyncio
import subprocess
import threading
import time
from typing import Dict, List

import numpy as np
import pyvisa as visa
from decs_visa_tools.decs_visa_settings import (
    HOST,
    PORT,
    READ_DELIM,
    SHUTDOWN,
    WRITE_DELIM,
)
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from mysecrets import LOGBOOK_SPREADSHEET_ID, SERVICE_ACCOUNT_FILE
from oauth2client.service_account import ServiceAccountCredentials
from serverapi import DecsVisaController

controller = None
monitor = None
monitor_thread = None
monitor_result = None

# Probe interval (in seconds)
PROBE_INTERVAL = 60 * 5

# Parameters to probe
PROBED_PARAMS = [
    "get_SAMPLE_T",
    "get_MC_T",
    "get_MC_T_SP",
    "get_MC_H",
    "get_STILL_T",
    "get_STILL_H",
    "get_CP_T",
    "get_SRB_T",
    "get_DR2_T",
    "get_PT2_T1",
    "get_DR1_T",
    "get_PT1_T1",
    "get_3He_F",
    "get_OVC_P",
    "get_P1_P",
    "get_P2_P",
    "get_P3_P",
    "get_P4_P",
    "get_P5_P",
    "get_P6_P",
]
TRACKED_PARAMS = [
    "get_MC_T",
    "get_STILL_T",
    "get_DR2_T",
    "get_PT2_T1",
    "get_DR1_T",
    "get_PT1_T1",
]


class ParamMonitor:
    def __init__(self, host=HOST, port=PORT, interval=PROBE_INTERVAL):
        self.host = host
        self.port = port
        self.interval = interval
        self.initial_values: Dict[str, float] = {}
        self.measurements: Dict[str, List[float]] = {
            param: [] for param in TRACKED_PARAMS
        }
        self._stop_event = threading.Event()
        self._thread = None
        self._visa = None

    def _connect(self):
        rm = visa.ResourceManager("@py")
        connection_str = f"TCPIP0::{self.host}::{self.port}::SOCKET"
        self._visa = rm.open_resource(connection_str)
        self._visa.read_termination = WRITE_DELIM
        self._visa.write_termination = READ_DELIM
        self._visa.chunk_size = 204800
        self._visa.timeout = 10000

    def _probe_once(self):
        for param in PROBED_PARAMS:
            try:
                val = float(self._visa.query(param))
                if param not in self.initial_values:
                    self.initial_values[param] = val
                if param in TRACKED_PARAMS:
                    self.measurements[param].append(val)
                print(f"Probed {param}: {val}")
            except Exception as e:
                print(f"Failed to probe {param}: {e}")

    def _acquisition_loop(self):
        while not self._stop_event.wait(self.interval):
            self._probe_once()

    def start(self):
        self._connect()
        self._probe_once()  # capture initial values
        self._thread = threading.Thread(target=self._acquisition_loop)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()

        initial = {param: self.initial_values[param] for param in PROBED_PARAMS}
        averages = {param: min(self.measurements[param]) for param in TRACKED_PARAMS}
        mins = {param: np.mean(self.measurements[param]) for param in TRACKED_PARAMS}
        try:
            self._visa.write(SHUTDOWN)
        except Exception:
            pass  # ignore if shutdown fails
        self._visa.close()
        return initial, averages, mins


def write_results_to_sheet(initials: dict, averages: dict, mins: dict):
    """
    Push results to the first row after header in Google Sheets.
    `data` should be a dict: { "param_name": value, ... }
    """

    sheet_name = "Foglio1"
    min_cols = {
        "get_DR1_T": "J",
        "get_DR2_T": "K",
        "get_PT1_T": "L",
        "get_PT2_T": "M",
        "get_STILL_T": "N",
        "get_MC_T": "O",
    }
    mean_cols = {
        "get_DR1_T": "P",
        "get_DR2_T": "Q",
        "get_PT1_T": "R",
        "get_PT2_T": "S",
        "get_STILL_T": "T",
        "get_MC_T": "U",
    }
    init_cols = {
        "get_DR1_T": "V",
        "get_DR2_T": "W",
        "get_PT1_T1": "X",
        "get_PT2_T1": "Y",
        "get_STILL_T": "Z",
        "get_OVC_P": "AA",
        "get_P1_P": "AB",
        "get_P2_P": "AC",
        "get_P3_P": "AD",
        "get_P4_P": "AE",
        "get_P5_P": "AF",
        "get_P6_P": "AG",
        "get_CP_T": "AH",
        "get_SRB_T": "AI",
        "get_3He_F": "AJ",
    }

    # Authorize client
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    # scope = [
    #     "https://spreadsheets.google.com/feeds",
    #     "https://www.googleapis.com/auth/drive",
    # ]
    # creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)

    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    col_a = (
        sheet.values()
        .get(spreadsheetId=LOGBOOK_SPREADSHEET_ID, range=f"{sheet_name}!A:A")
        .execute()
    )

    rows = col_a.get("values", [])
    first_empty_row = len(rows)

    # Prepare batch update for individual cells
    updates = []

    iterate = [(min_cols, mins), (mean_cols, averages), (init_cols, initials)]
    for section in iterate:
        cols, results = section
        for param in cols:
            value = results.get(param, 0)
            col_letter = cols[param]
            cell_ref = f"{sheet_name}!{col_letter}{first_empty_row}"
            updates.append({"range": cell_ref, "values": [[value]]})

    if updates:
        body = {"valueInputOption": "USER_ENTERED", "data": updates}
        sheet.values().batchUpdate(
            spreadsheetId=LOGBOOK_SPREADSHEET_ID, body=body
        ).execute()
        print(f"Logged {len(updates)} entries to row {first_empty_row}")
    else:
        print("No matching parameters to write.")


def logbook_setup(bot):

    @bot.command(name="cooldown_started")
    async def cooldown_started(ctx):
        global controller, monitor, monitor_thread, monitor_result

        if monitor_thread and monitor_thread.is_alive():
            await ctx.send("Monitor is already running.")
            return

        def monitor_task():
            global monitor_result, monitor
            subprocess.Popen(
                [
                    "python",
                    "/home/rodolfo/Venv/poutpurri/main/qubot-bot/src/qubot/serverapi.py",
                ]
            )
            time.sleep(30)
            monitor = ParamMonitor()
            monitor.start()

        monitor_thread = threading.Thread(target=monitor_task)
        monitor_thread.start()

        await ctx.send("Cooldown monitoring started.")

    @bot.command(name="cooldown_ended")
    async def cooldown_ended(ctx):
        global controller, monitor_result, monitor
        initials, averages, mins = monitor.stop()
        monitor_result = (initials, averages, mins)
        print("Monitoring done.")

        if controller:
            controller.shutdown()
            controller = None

        if monitor_thread:
            monitor_thread.join()

        if monitor_result:
            initials, averages, mins = monitor_result
            write_results_to_sheet(initials, averages, mins)
            await ctx.send("Monitoring stopped and results logged.")
        else:
            await ctx.send("No results to log.")
