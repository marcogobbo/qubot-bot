# QuBot

Discord bot for monitoring dilution refrigerators (Elsa, Anna, Olaf) at INFN Milano Bicocca via the qtics/Proteox WAMP API.

## Architecture

```
src/qubot/
  main.py                  # QuBot(commands.Bot) — loads cogs, syncs slash commands
  cogs/
    reports.py             # /report slash command — on-demand fridge snapshot
    scheduler.py           # Daily report at 09:30 (skips fridges that are LOCAL, or Idle with MC=0)
    monday.py              # Monday Meeting reminder at 09:15 every Monday
    uta.py                 # /uta slash command — HVAC plant report (scrapes legacy CGI)
  services/
    proteox.py             # ProteoxService — async WAMP client; Snapshot dataclass
    report.py              # build_report_embed() — renders Snapshot as Discord Embed
    destinations.py        # resolve() / send_embed() — channel or thread routing
    uta.py                 # UTA snapshot service — scrapes legacy CGI HTML
    uta_report.py          # build_uta_embed() — renders UtaSnapshot as Discord Embed
  core/
    settings.py            # Pydantic Settings loaded from .env; FridgeConnection per fridge
    fridge_config.py       # FridgeProfile + SensorSpec loaded from config/<name>.yaml
    units.py               # format_value() — SI unit formatting with scale factors
    logging_setup.py       # structlog setup
config/
  elsa.yaml / anna.yaml / olaf.yaml   # per-fridge sensor lists, labels, resources
```

## Configuration

Copy `.env.example` to `.env`. Per-fridge variables are prefixed: `ELSA_PROTEOX_URL`, `ELSA_DESTINATION_ID`, etc. Fridges with incomplete config are skipped at startup with a warning (bot still runs with the remaining ones).

## Key behaviours

**LOCAL mode detection** — when a fridge is in LOCAL (not REMOTE) mode, `get_state()` returns an object that stringifies to `"Unknown (None)"`. `ProteoxService.snapshot()` checks for this immediately after reading state and returns early, skipping all sensor reads. Callers (`reports.py`, `scheduler.py`) then show a LOCAL mode warning instead of a report.

**Connection timeout** — `ProteoxService.__aenter__` wraps `connect()` with `asyncio.wait_for(..., timeout=10.0)`. On timeout or connection refusal a `RuntimeError` is raised with the message `"is not responding. Please check the network."` — formatted by callers as `:warning: **FridgeName** is not responding. Please check the network.`

**Scheduler skip conditions** — the daily report is skipped for a fridge if status is LOCAL, or if the fridge is Idle **and** the mixing-chamber temperature reads 0 / unavailable. A fridge that is actively running but has a transient MC=0 reading, or one that is Idle with a valid MC reading, is still reported.

**Command routing** — `/report` is silently ignored (ephemeral defer) if invoked from a channel not bound to any fridge. The `channel→fridge` map is built at cog load from `<FRIDGE>_DESTINATION_ID` values.

**UTA reports** — `/uta` is available in **every** channel/thread (no destination gating). Each invocation HTTP-GETs the legacy `utareport_html` CGI (URL in `UTA_CGI_URL`) and parses the returned HTML with regex anchored on stable label strings. The CGI already runs inside the lab and has direct access to the UTA controller, so this avoids the FTP-firewall problem QuBot would hit going direct. Network failures surface as `:warning: **UTA** controller is not responding. Please check the network.` Parser lives in `services/uta.py::parse_uta_html`.

## Running

```bash
poetry install
poetry run qubot        # or: python -m qubot.main
```

## Docker deployment

The repo ships a `Dockerfile` (multi-stage, Python 3.11-slim + tini) and `docker-compose.yml`. The `.env` is gitignored and supplied via `env_file:`; `config/` is bind-mounted read-only at `/app/config`.

```bash
cp .env.example .env       # then fill in tokens, IDs, UTA_CGI_URL, etc.
docker compose up -d --build
docker logs -f qubot       # expect: "loaded cog …reports/…scheduler/…monday/…uta" then "global command tree synced"
```

Update after a code change: `git pull && docker compose up -d --build`. Edits to YAML under `config/` only need `docker compose restart qubot`; `.env` changes need `docker compose up -d` (recreate).

**`PYTHONPATH=/app/src`** is set in the runtime stage of the Dockerfile. Poetry's root-install step is unreliable in slim builds without a `poetry.lock` (root package never lands in site-packages), so `python -m qubot.main` would fail with `ModuleNotFoundError: No module named 'qubot'`. Putting `src/` on the path makes the src-layout package importable directly from the bind-copied source — no install step required. **Do not remove this env var** without first verifying `docker compose run --rm qubot python -c "import qubot"` still resolves.

**Outbound reachability needed from the container:** Discord gateway + REST, `ws://<fridge>.mib.infn.it:8080/ws` for each enabled fridge, `http://artico.mib.infn.it/cgi-bin/utareport_html` for `/uta`. To set log timestamps to local time, add `environment: { TZ: Europe/Rome }` under the `qubot:` service — `zoneinfo` already handles the scheduler tz independently.
