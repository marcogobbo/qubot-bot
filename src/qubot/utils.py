from datetime import datetime, timedelta

import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build
from mysecrets import LOGBOOK_SPREADSHEET_ID, SERVICE_ACCOUNT_FILE


def seconds_until_target(day_of_week, hour, minute):
    now = datetime.now(pytz.timezone("Europe/Rome"))
    today = now.weekday()
    days_ahead = (day_of_week - today + 7) % 7
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if days_ahead == 0 and now > target:
        days_ahead = 7

    target += timedelta(days=days_ahead)
    return (target - now).total_seconds()


def is_cryo_active():
    """Check if cryostat is active"""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )

    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    result = (
        sheet.values()
        .get(spreadsheetId=LOGBOOK_SPREADSHEET_ID, range="Foglio1!A2:C")
        .execute()
    )
    values = result.get("values", [])

    for row in values:
        start = row[0].strip() if len(row) > 0 else ""
        stop = row[2].strip() if len(row) > 2 else ""
        if start and not stop:
            return True

    return False
