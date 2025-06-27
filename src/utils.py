"""Utility functions"""

from datetime import datetime
from json import load
from typing import Any

from gspread import Client, Spreadsheet, Worksheet, service_account
from pandas import DataFrame, to_datetime


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
