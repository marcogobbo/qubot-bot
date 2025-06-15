import asyncio
import queue
import threading
from sys import version_info

from autobahn.asyncio.wamp import ApplicationRunner
from decs_visa_components.simple_socket_server import simple_server
from decs_visa_components.wamp_component import Component
from decs_visa_tools.base_logger import logger
from decs_visa_tools.decs_visa_settings import (
    PYTHON_MIN_MAJOR,
    PYTHON_MIN_MINOR,
    SHUTDOWN,
)
from mysecrets import (
    BIND_SERVER_TO_INTERFACE,
    SERVER_PORT,
    WAMP_REALM,
    WAMP_ROUTER_URL,
    WAMP_USER,
    WAMP_USER_SECRET,
)


class DecsVisaController:
    def __init__(self):
        if version_info < (PYTHON_MIN_MAJOR, PYTHON_MIN_MINOR):
            raise RuntimeError(
                f"Incompatible Python version: {version_info.major}.{version_info.minor}, "
                f"required ≥ {PYTHON_MIN_MAJOR}.{PYTHON_MIN_MINOR}"
            )

        self.user = WAMP_USER
        self.user_secret = WAMP_USER_SECRET
        self.url = WAMP_ROUTER_URL
        self.realm = WAMP_REALM
        self.interface = BIND_SERVER_TO_INTERFACE
        self.port = SERVER_PORT

        self.queries = queue.Queue(maxsize=1)
        self.responses = queue.Queue(maxsize=1)

        self.server_thread = None
        self.runner = None

    def start(self):
        """Start socket server and WAMP component."""
        logger.info("Starting DECS<->VISA server...")

        # Start socket server in background thread
        self.server_thread = threading.Thread(
            target=simple_server,
            args=(self.interface, self.port, self.queries, self.responses),
            daemon=True,
        )
        self.server_thread.start()

        # Start WAMP runner in the main thread (blocking call)
        self.runner = ApplicationRunner(
            self.url,
            self.realm,
            extra={
                "input_queue": self.queries,
                "output_queue": self.responses,
                "user_name": self.user,
                "user_secret": self.user_secret,
            },
        )

        try:
            self.runner.run(Component, log_level="critical")  # runs in main thread
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                logger.info("Keyboard Interrupt - shutdown")
            else:
                logger.info("WAMP component error: %s", e)
            try:
                _ = self.responses.get_nowait()
            except queue.Empty:
                pass
            self.shutdown()

        # Clean exit for socket server
        self.server_thread.join()

    def shutdown(self):
        """Gracefully stop the server and WAMP."""
        logger.info("Shutting down DECS<->VISA server...")

        try:
            _ = self.responses.get_nowait()
        except queue.Empty:
            pass

        self.responses.put(SHUTDOWN)

        if self.server_thread:
            self.server_thread.join()

        logger.info("DECS<->VISA server shut down.")


controller = DecsVisaController()
controller.start()
