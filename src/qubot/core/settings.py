"""Application settings loaded from environment variables (.env)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

FRIDGE_NAMES: tuple[str, ...] = ("elsa", "anna", "olaf")

DestinationType = Literal["thread", "channel"]


class FridgeConnection(BaseSettings):
    """Connection + destination for a single fridge.

    Populated from environment variables prefixed with the fridge name
    (e.g. ELSA_PROTEOX_URL, ELSA_DESTINATION_ID, ELSA_DESTINATION_TYPE).
    """

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    proteox_url: str
    proteox_realm: str = "ucss"
    destination_id: int
    destination_type: DestinationType


class Settings(BaseSettings):
    """Top-level bot settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    discord_token: str

    log_level: str = "INFO"

    daily_report_hour: int = 9
    daily_report_minute: int = 30
    daily_report_tz: str = "Europe/Rome"

    # Monday Meeting reminder
    monday_meeting_zoom_url: str = ""
    monday_meeting_minutes_url: str = ""
    monday_meeting_destination_id: int = 0
    monday_meeting_destination_type: DestinationType = "channel"
    monday_meeting_hour: int = 9
    monday_meeting_minute: int = 15

    # Global WAMP credentials — qtics reads these from os.environ at import.
    # Mirrored here so we can validate they're set before connecting.
    wamp_user: str
    wamp_user_secret: str
    wamp_realm: str = "ucss"
    wamp_router_url: str = ""

    # UTA (HVAC) CGI source — /uta scrapes the legacy report HTML on each
    # invocation. Empty URL disables the command with a clear runtime error.
    uta_cgi_url: str = ""
    uta_cgi_timeout: float = 10.0

    # UTA hourly monitor (`/uta monitor on`) thresholds. A warning is posted to
    # Elsa's daily-report destination when the chiller water temperature is at or
    # above the max, or the absolute filter ΔP is at or below the min.
    uta_monitor_chiller_temp_max: float = 16.0  # °C — warn if at/above
    uta_monitor_abs_filter_min: float = 60.0  # Pa — warn if at/below

    fridges: dict[str, FridgeConnection] = Field(default_factory=dict)

    @classmethod
    def load(cls) -> "Settings":
        """Load settings and fill per-fridge connections from prefixed env vars.

        Fridges with incomplete or missing env vars are skipped with a warning
        so the bot can start with only a subset configured.
        """
        import logging
        base = cls()
        for name in FRIDGE_NAMES:
            try:
                base.fridges[name] = FridgeConnection(_env_prefix=f"{name.upper()}_")  # type: ignore[call-arg]
            except Exception as exc:
                logging.getLogger("qubot.settings").warning(
                    "skipping fridge %s — incomplete config: %s", name, exc
                )
        if not base.fridges:
            raise RuntimeError("No fridges configured — set at least one <FRIDGE>_PROTEOX_URL and <FRIDGE>_DESTINATION_ID in .env")
        return base
