# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Browser automation toolkit (Python/Selenium) for syncing Google Calendar → Cybozu groupware, and automating other institutional web services (Sakura messaging, accounting entry).

## Environment Setup

This project uses [pixi](https://prefix.dev/docs/pixi/) (conda-based) for dependency management, targeting Windows only (`win-64`).

```powershell
pixi install          # install dependencies
pixi shell            # activate environment
python ScheduleSync.py  # run schedule sync
```

## Running Scripts

- **Schedule sync** (main use case): `python ScheduleSync.py`
- **Sakura messaging**: `python makemail_sakura.py`
- Individual modules can be run directly (each has `if __name__ == "__main__"` blocks with hardcoded user paths)

Scripts require Chrome to be installed and not running — `Browser.__init__` kills all Chrome processes before launching.

## Architecture

### Two-layer design

**`Chrome/`** — Selenium browser automation classes, all inheriting from `Browser`:
- `Browser` (base): launches Chrome with the user's real profile (`--user-data-dir`) for saved passwords/cookies, kills existing Chrome processes first, persists state to `Chrome/status.binaryfile` (pickle of a pandas DataFrame)
- `Cyboze(Browser)`: exports schedule CSV, inputs/deletes events via Cybozu web UI
- `GoogleCalender(Browser)`: triggers calendar export ZIP download from Google Calendar web UI
- `Sakura(Browser)`: composes and addresses messages in Sakura notification system

**`Calender/`** — Data model classes, independent of browser:
- `Event` / `AllDay` / `MultiDay`: a single calendar event; `input_cyboze()` and `delete_cyboze()` take a `Browser` instance and drive the UI
- `Calender`: collection of Events with `union()`, `substract()` (set difference), `filtering_by_date()`
- `CybozeCalender(Calender)`: reads from Cybozu's exported CSV (CP932 or UTF-8)
- `GoogleCalender(Calender)`: parses `.ics` files manually from `./data/GoogleCalender/`; expands recurring events into individual instances

### Sync flow (`ScheduleSync.py`)

1. Download Google Calendar → extract `.ics` files → parse into `Calender` objects
2. Download Cybozu schedule CSV → parse into `CybozeCalender`
3. Filter both to a date window (yesterday → +1 year)
4. `ccal - gcal` → events to delete from Cybozu
5. `gcal - ccal` → events to input into Cybozu

### Event identity

Events are matched by comparing all four fields: `title`, `start_time`, `end_time`, `id`. The `id` field is `str([name, start_time, end_time, uid])` — a string representation of the list. This string is stored in Cybozu's memo field during input and read back during CSV export for identification; only events with `datetime.datetime(` in the memo field are treated as auto-synced events.

### File locations

- `./data/` — downloaded files (Cybozu CSV, Google Calendar ICS/ZIP); files are deleted after parsing
- `./data/GoogleCalender/` — extracted ICS files
- `Chrome/status.binaryfile` — persisted status (user IDs, names, Google account ID)

### Legacy code

`Edge/` contains an older version using `msedge-selenium-tools` (Edge WebDriver), superseded by the `Chrome/` implementations. `Other/` has standalone utility scripts.

## Known Limitations

- Moving a recurring event in Google Calendar does not delete the original from Cybozu
- `MultiDay.input_cyboze()` is a no-op (multi-day spans are not synced)
- Hardcoded user paths (`C:/Users/Yusaku/...`) appear throughout scripts
