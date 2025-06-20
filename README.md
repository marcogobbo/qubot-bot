# Qu-bot

A modular Discord bot for managing academic and lab-related tasks. It currently supports the **Quantum Journal Club (QJC)** and is designed for easy extension by adding new modules.

## 🧠 Features

- ⏰ Scheduled reminders (e.g. for QJC meetings)
- 🔗 Slash commands for quick info access

## 📁 Project Structure

```
qu_bot/
├── __main__.py           # Entry point
├── journal_club.py       # QJC-specific logic (commands, reminders)
├── utils.py              # Shared helpers (e.g. time calculations)
└── mysecrets.py            # API keys and config (excluded from git)
```

## ⚙️ Setup

1. **Install dependencies**:

   ```bash
   poetry install
   ```

2. **Add `mysecrets.py`**:

   ```python
   DISCORD_TOKEN = "your_token"
   JC_CHANNEL_ID = 123456789012345678
   JC_SPREADSHEET_URL = "https://docs.google.com/spreadsheets/..."
   SERVICE_ACCOUNT_FILE = "path/to/service_account.json"
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
