"""Terminal logging configured once at startup.

Logs every event (commands, scheduled runs, sensor reads, errors) to stdout
in a format suitable for `docker logs`.
"""

from __future__ import annotations

import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure the root logger to write to stdout. Returns the qubot logger."""
    root = logging.getLogger()
    root.setLevel(level.upper())

    # Drop any pre-existing handlers (matters when modules import logging early).
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root.addHandler(handler)

    # discord.py is chatty at DEBUG; cap it at INFO unless the user really wants it.
    logging.getLogger("discord").setLevel(max(root.level, logging.INFO))

    return logging.getLogger("qubot")


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the `qubot` namespace."""
    return logging.getLogger(f"qubot.{name}")
