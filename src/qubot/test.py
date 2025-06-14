from logbook import ParamMonitor
from serverapi import DecsVisaController
import threading
import time
import os
from google.oauth2.service_account import Credentials
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from string import ascii_uppercase

from secrets import LOGBOOK_SPREADSHEET_ID, SERVICE_ACCOUNT_FILE

# Set your sheet details
SHEET_NAME = "Sheet1"  # Adjust if using a named sheet


def write_results_to_sheet(initials: dict, averages: dict, mins: dict):
    """
    Push results to the first row after header in Google Sheets.
    `data` should be a dict: { "param_name": value, ... }
    """

    sheet_name = "Foglio1"
    min_cols = {
        "get_DR1_T"  : "J" ,
        "get_DR2_T"  : "K" ,
        "get_PT1_T"  : "L" ,
        "get_PT2_T"  : "M" ,
        "get_STILL_T": "N" ,
        "get_MC_T"   : "O"
    }
    mean_cols = {
        "get_DR1_T"  : "P" ,
        "get_DR2_T"  : "Q" ,
        "get_PT1_T"  : "R" ,
        "get_PT2_T"  : "S" ,
        "get_STILL_T": "T" ,
        "get_MC_T"   : "U"
    }
    init_cols = {
        "get_DR1_T"   : "V",
        "get_DR2_T"   : "W",
        "get_PT1_T1"  : "X",
        "get_PT2_T1"  : "Y",
        "get_STILL_T" : "Z",
        "get_OVC_P"   : "AA",
        "get_P1_P"    : "AB",
        "get_P2_P"    : "AC",
        "get_P3_P"    : "AD",
        "get_P4_P"    : "AE",
        "get_P5_P"    : "AF",
        "get_P6_P"    : "AG",
        "get_CP_T"    : "AH",
        "get_SRB_T"   : "AI",
        "get_3He_F"   : "AJ",

    }

    # Authorize client
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    # scope = [
    #     "https://spreadsheets.google.com/feeds",
    #     "https://www.googleapis.com/auth/drive",
    # ]
    # creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)

    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()


    col_a = sheet.values().get(
        spreadsheetId=LOGBOOK_SPREADSHEET_ID,
        range=f"{sheet_name}!A:A"
    ).execute()

    rows = col_a.get("values", [])
    first_empty_row = len(rows)

    # Prepare batch update for individual cells
    updates = []

    iterate = [(min_cols, mins),
               (mean_cols, averages),
               (init_cols, initials)]
    for section in iterate:
        cols, results = section
        for param in cols:
            value = results.get(param, 0)
            col_letter = cols[param]
            cell_ref = f"{sheet_name}!{col_letter}{first_empty_row}"
            updates.append({
                "range": cell_ref,
                "values": [[value]]
            })

    if updates:
        body = {
            "valueInputOption": "USER_ENTERED",
            "data": updates
        }
        sheet.values().batchUpdate(
            spreadsheetId=LOGBOOK_SPREADSHEET_ID,
            body=body
        ).execute()
        print(f"Logged {len(updates)} entries to row {first_empty_row}")
    else:
        print("No matching parameters to write.")



if __name__ == "__main__":
    controller = DecsVisaController()

    # Start the monitoring thread instead
    def monitor_task():
        time.sleep(30)
        monitor = ParamMonitor()
        monitor.start()
        time.sleep(3 * 60)
        initials, averages, mins = monitor.stop()
        print("Monitoring Results:")
        for param, data in initials.items():
            print(f"{param}: {data}")
        controller.shutdown()
        time.sleep(10)
        write_results_to_sheet(initials, averages, mins)

    monitor_thread = threading.Thread(target=monitor_task)
    monitor_thread.start()

    # Now this runs in the main thread
    controller.start()
    monitor_thread.join()

