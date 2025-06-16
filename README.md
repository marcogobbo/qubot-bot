# Qu-bot

A modular Discord bot for managing academic and lab-related tasks. It currently supports the **Quantum Journal Club (QJC)** and is designed for easy extension by adding new modules.

## 🧠 Features

- ⏰ Scheduled reminders (e.g. for QJC meetings)
- 🔗 Slash commands for quick info access

## 📁 Project Structure

```
qubot/
├── __main__.py           # Entry point
├── utils.py              # Shared helpers (e.g. time calculations)
├── serverapi.py          # WAMP functions for probing cryostat
├── journal_club.py       # QJC-specific logic (commands, reminders)
├── logbook.py            # Logbook-specific logic (start and stop cooldown)
└── mysecrets.py          # API keys and config (excluded from git)
```

## ⚙️ Setup

1. **Install dependencies**:

   ```bash
   poetry install
   ```

2. **Add `mysecrets.py`**:

   ```python
   DISCORD_TOKEN = "your_token"
   CHANNEL_ID = 123456789012345678
   JC_SPREADSHEET_URL = "https://docs.google.com/spreadsheets/..."
   SERVICE_ACCOUNT_FILE = "path/to/service_account.json"

   WAMP_USER = "CrioUser"
   WAMP_USER_SECRET = "criopassword"
   WAMP_REALM = "ucss"
   WAMP_ROUTER_URL = "ws://XXXX.XXX.XXXX.XX:8080/ws"
   BIND_SERVER_TO_INTERFACE = "localhost"
   SERVER_PORT = "33576"
   ```

3. **Share the spreadsheet** with your service account email.

4. **Run the bot**:

   ```bash
   python -m qubot
   ```

## ➕ Extend Qu-bot

To add functionality:

- Create a new module (e.g. `my_task.py`)
- Register new `@bot.command()`s or scheduled tasks

Minimal changes needed in `__main__.py`.
