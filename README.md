# QuBot

Discord bot that reports pressures and temperatures from BiQuTe's three Proteox
dilution refrigerators — **Elsa**, **Anna**, and **Olaf**.

- `/report` — on-demand report. The fridge is inferred from the channel or
  thread where the command is invoked, by reverse-lookup of the
  `<FRIDGE>_DESTINATION_ID` values in `.env`. Invoking `/report` outside any
  configured channel is silently ignored (logged for audit).
- **Daily 09:30** — automatic report per fridge, posted only when the fridge is
  active (status not `Idle`) and the mixing-chamber temperature is in scale
  (not exactly `0`).
- Units **auto-scale by magnitude**: 0.9 K → `900 mK`; 1.2 nW heater → `1.2 nW`;
  1500 Pa → `1.5 kPa`. Flow shown as μmol/s.
- Sends to a **thread** or **channel** (per fridge, configured in `.env`).
- All events logged to the terminal (`docker logs -f qubot`).

## Architecture

```
QuBot/
├── pyproject.toml             # Poetry project
├── Dockerfile                 # multi-stage build
├── docker-compose.yml
├── .env.example
├── config/                    # per-fridge personalization (editable YAML)
│   ├── elsa.yaml
│   ├── anna.yaml
│   └── olaf.yaml
└── src/qubot/
    ├── main.py                # entrypoint, loads cogs
    ├── core/
    │   ├── settings.py        # .env loader (pydantic-settings)
    │   ├── fridge_config.py   # YAML loader (FridgeProfile)
    │   └── logging_setup.py
    ├── services/
    │   ├── proteox.py         # async wrapper over qtics Proteox client
    │   ├── report.py          # Embed builder
    │   └── destinations.py    # thread/channel resolver
    └── cogs/
        ├── reports.py         # /report slash command
        └── scheduler.py       # daily 09:30 task
```

### Why cogs?

Cogs are discord.py's idiomatic way to group related commands and listeners.
With at least two distinct concerns (slash command + scheduled task), cogs
keep `reports.py` and `scheduler.py` focused and let `tasks.loop` live next
to the code that consumes it. Adding e.g. a `health` cog later is a one-file
change.

## Configuration

### `.env`

Copy `.env.example` to `.env` and fill in the values. Per-fridge variables are
prefixed with the fridge name (`ELSA_`, `ANNA_`, `OLAF_`):

| Variable | Meaning |
| --- | --- |
| `DISCORD_TOKEN` | Bot token from the Discord developer portal. |
| `DISCORD_GUILD_IDS` | Comma-separated guild IDs for fast slash sync. Empty = global. |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR`. |
| `DAILY_REPORT_HOUR` / `DAILY_REPORT_MINUTE` | When the daily task fires (default 09:30). |
| `DAILY_REPORT_TZ` | IANA timezone (default `Europe/Rome`). |
| `WAMP_USER` / `WAMP_USER_SECRET` | DECS WAMP credentials (shared across all fridges in one bot process). |
| `WAMP_REALM` | Default WAMP realm. Overridden per fridge by `<FRIDGE>_PROTEOX_REALM`. |
| `WAMP_ROUTER_URL` | Default WAMP router URL. Overridden per fridge by `<FRIDGE>_PROTEOX_URL`. |
| `<FRIDGE>_PROTEOX_URL` | WAMP URL of this fridge's Proteox controller. |
| `<FRIDGE>_PROTEOX_REALM` | WAMP realm for this fridge (usually `ucss`). |
| `<FRIDGE>_DESTINATION_ID` | Thread or channel Discord ID. |
| `<FRIDGE>_DESTINATION_TYPE` | `thread` or `channel`. |

### WAMP credentials note

`qtics` reads `WAMP_USER`, `WAMP_USER_SECRET`, `WAMP_REALM`, and
`WAMP_ROUTER_URL` directly from `os.environ` at module import time. QuBot
calls `dotenv.load_dotenv()` at startup so the values in `.env` reach
`os.environ` before qtics is imported.

**Shared credentials caveat:** because `WAMP_USER` / `WAMP_USER_SECRET` are
read once at module load, all three fridges in a single bot process share the
same WAMP user. If you need distinct credentials per fridge, run one bot
process per fridge.

`BIND_SERVER_TO_INTERFACE` and `SERVER_PORT` you may have seen in the
Oxford Instruments DECS docs belong to the *DECS server* on the cryostat
host — they are not consumed by QuBot.

The bot runs on as many guilds as you invite it to; destinations are resolved
by ID across all of them.

### `config/<fridge>.yaml`

Each fridge has its own YAML file describing which sensors appear on its
report, with custom labels and a `quantity` that drives auto-scaled display.
Example:

```yaml
display_name: "Elsa"
color: 0x5DADE2
mixing_chamber_key: MC_T   # used by the "skip if 0" gate

temperatures:
  - { uri_key: MC_T,  label: "Mix Chamber", quantity: temperature, precision: 3 }
  - { uri_key: STILL_T, label: "Still",     quantity: temperature, precision: 3 }

pressures:
  - { uri_key: OVC_P, label: "OVC", quantity: pressure, precision: 3 }
  - { uri_key: P1_P,  label: "P1",  quantity: pressure, precision: 3 }

heaters:
  - { uri_key: MC_H, label: "MC Heater", quantity: power, precision: 3 }

flow:
  # qtics returns mol/s; convert to μmol/s for display.
  - { uri_key: "3He_F", label: "³He Flow", quantity: flow, precision: 2, from_base_scale: 1.0e+6 }

resources:
  - { label: "Dashboard", url: "https://lab.example.com/elsa/dashboard" }
  - { label: "Manual", url: "https://docs.example.com/proteox" }
```

`uri_key` must match a key in the qtics `getters` dict (defined in
`qtics/instruments/network/proteox/uris.py`). The bot calls `get_<uri_key>()`
which is dynamically created by qtics's `__getattr__`. Valid keys include:
`MC_T`, `STILL_T`, `CP_T`, `PT1_T`, `PT2_T`, `MAG_T`, `SRB_T`, `OVC_P`, 
`P1_P`–`P6_P`, `MC_H`, `STILL_H`, `3He_F`, etc. Add/remove rows freely — the
report adjusts automatically.

### Quantities and units

| `quantity`       | Base unit | Auto-scaled prefixes              |
| ---------------- | --------- | --------------------------------- |
| `temperature`    | K         | K, mK, μK                         |
| `pressure`       | Pa        | MPa, kPa, Pa, mPa                 |
| `power`          | W         | W, mW, μW, nW, pW                 |
| `magnetic_field` | T         | T, mT                             |
| `flow`           | μmol/s    | (fixed; use `from_base_scale` if qtics returns a different unit) |

The bot picks the largest prefix where the mantissa stays ≥ 1
(0.9 K → `900 mK`; 1.2 K → `1.200 K`).

## Run locally (Poetry)

```bash
poetry install
cp .env.example .env   # edit it
poetry run qubot
```

## Run in Docker

```bash
cp .env.example .env   # edit it
docker compose up -d --build
docker compose logs -f qubot
```

The `config/` directory is mounted read-only — edit a YAML and restart the
container (`docker compose restart qubot`) to apply.

## Daily report gating

For each fridge at 09:30:

1. Open WAMP session, fetch `get_recognized_states()` + every configured sensor.
2. If any recognized state begins with `"Idle"` → **skip** (and log it).
3. If the configured `mixing_chamber_key` reads `0` (or fails) → **skip**.
4. Otherwise, build a personalized embed and post to the fridge's destination.

`/report` runs the same pipeline but never skips — it always returns something.
