import time
import numpy as np
import threading
from typing import List, Dict
import pyvisa as visa

from decs_visa_tools.decs_visa_settings import (
    HOST,
    PORT,
    SHUTDOWN,
    READ_DELIM,
    WRITE_DELIM,
)

# Parameters to probe
PROBED_PARAMS = ["get_SAMPLE_T",
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
                 "get_P6_P"]
TRACKED_PARAMS = ["get_MC_T",
                 "get_STILL_T",
                 "get_DR2_T",
                 "get_PT2_T1",
                 "get_DR1_T",
                 "get_PT1_T1",
]

# Probe interval (in seconds)
PROBE_INTERVAL = 60

class ParamMonitor:
    def __init__(self, host=HOST, port=PORT, interval=PROBE_INTERVAL):
        self.host = host
        self.port = port
        self.interval = interval
        self.initial_values: Dict[str, float] = {}
        self.measurements: Dict[str, List[float]] = {param: [] for param in TRACKED_PARAMS}
        self._stop_event = threading.Event()
        self._thread = None
        self._visa = None

    def _connect(self):
        rm = visa.ResourceManager('@py')
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

