# QuBot

A modular Discord bot for managing academic and lab-related tasks. Currently, it supports:

- Quantum Journal Club (QJC) announcements  
- General reminders (i.e. Monday Meetings)
- Reminders for refilling Elsa's cold trap dewar  

It is designed to be easily extensible by adding new modules (cogs).

---

## 🧠 Features

- ⏰ Scheduled reminders (e.g., for QJC meetings)
- 📝 Easy integration with Google Sheets and Docs
- 🧩 Modular cog-based architecture

---

## 📁 Project Structure

```text
qubot/
├── main.py                # Entry point of the bot
├── utils.py               # Utility functions
├── messages.json          # Templates for messages to send
├── service_account.json   # Google Cloud service account credentials
├── .env                   # Environment variables (tokens, channel IDs, URLs, etc.)
├── cogs/
│   ├── announcements.py   # Base class for announcement-related cogs
│   ├── elsa.py            # Cog for Elsa's channel reminders
│   ├── general.py         # Cog for the general channel reminders
│   └── journal_club.py    # Cog for Quantum Journal Club announcements
```

## ⚙️ Setup

1. **Install dependencies**:

   ```bash
   poetry install
   ```

2. **Add a ```.env``` file in the root directory with the following variables**:

   ```env
   DISCORD_TOKEN="your_token"
   GENERAL_CHANNEL="123456789123456789"
   ELSA_CHANNEL="123456789123456789"
   JOURNAL_CLUB_CHANNEL="123456789123456789"
   JOURNAL_CLUB_SPREADSHEET_URL="https://docs.google.com/spreadsheets/d/abcdfghijklmnopqrstuvwxyz"
   MONDAY_MEETING_ZOOM_URL="https://zoom.us/j/123456789"
   MONDAY_MEETING_MINUTES_URL="https://docs.google.com/document/d/abcdfghijklmnopqrstuvwxyz"
   SERVICE_ACCOUNT_JSON="service_account.json"
   MESSAGES_JSON="messages.json"
   ```

3. **Add your ```service_account.json``` file**:<br>
   This file is downloaded from Google Cloud and is required to access Google Sheets and Docs.

4. **Run the bot**:
   ```bash
   python qubot.py
   ```

## ➕ Extending QuBot
To add new functionality:

    Create a new cog (e.g., ```my_cog.py```) in the ```cogs/``` directory.

    Load it by modifying the QuBot class to include:

   ```python
    await self.load_extension("cogs.my_cog")
   ```

Minimal changes are needed in ```main.py```, thanks to the modular architecture.