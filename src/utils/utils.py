"""Utility functions"""

from dataclasses import dataclass
from datetime import datetime
from json import load
from typing import Any, Optional
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from gspread import Client, Spreadsheet, Worksheet, service_account
from pandas import DataFrame, to_datetime

from utils.constants import ZONE_INFO


@dataclass
class ScheduledTime:
    day: Optional[int] = None
    hour: int = 0
    minute: int = 0
    timezone: ZoneInfo = ZONE_INFO

    def __post_init__(self):
        """Validation"""
        if self.day is not None and not 0 <= self.day <= 6:
            raise ValueError("day must be between 0-6 or None")
        if not 0 <= self.hour <= 23:
            raise ValueError("hour must be between 0-23")
        if not 0 <= self.minute <= 59:
            raise ValueError("minute must be between 0-59")

    def to_cron_trigger(self) -> CronTrigger:
        """Convert in to trigger APScheduler"""
        return CronTrigger(
            day_of_week=self.day,
            hour=self.hour,
            minute=self.minute,
            timezone=self.timezone,
        )


def load_json(filename: str) -> dict[str, Any]:
    """Load JSON data from a file."""
    with open(filename, "r", encoding="utf-8") as f:
        data: dict[str, Any] = load(f)
    return data


def load_data(
    service_account_path: str, spreadsheet_url: str, sheet: int | str = 0
) -> DataFrame:
    """Load data from a Google Sheet into a DataFrame."""
    gc: Client = service_account(filename=service_account_path)
    sh: Spreadsheet = gc.open_by_url(spreadsheet_url)
    if isinstance(sheet, int):
        worksheet: Worksheet = sh.get_worksheet(sheet)
    else:
        worksheet: Worksheet = sh.worksheet(sheet)
    data: list[dict[str, Any]] = worksheet.get_all_records()
    df: DataFrame = DataFrame(data)
    df["spreadsheet"] = spreadsheet_url
    return df


def parse_data(df: DataFrame) -> dict[str, Any]:
    """Parse the DataFrame and return the next upcoming entry as a dictionary."""
    df["datetime"] = to_datetime(df["date"] + " " + df["time"], dayfirst=True)
    df_next = df[df["datetime"] > datetime.now()]
    row = df_next.loc[df_next["datetime"].idxmin()].copy()
    row["link"] = df["link"][0]
    return dict(row)
