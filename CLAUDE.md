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
- `Browser` (base): launches Chrome with the user's real profile (`--user-data-dir`) for saved passwords/cookies, kills existing Chrome processes first, persists state to `Chrome/status.binaryfile` (pickle of a pandas DataFrame). `safe_click(element_or_locator)` clicks normally and falls back to a JS-dispatched `element.click()` on `ElementNotInteractableException`/`ElementClickInterceptedException` — use this instead of a plain Selenium `.click()` for any element that's present in the DOM but not necessarily visible/on-screen (e.g. CSS-hidden radio/checkbox inputs); a native synthetic click requires the element to be displayed, a JS `.click()` does not. `patient_get(url, description, wait_for=None)` / `wait_for_manual_step()` tolerate OS-native modal dialogs (Windows Hello PIN, etc.) blocking navigation — see "Windows Hello / manual-auth waits" below.
- `Cyboze(Browser)`: exports schedule CSV, inputs/deletes events via Cybozu web UI
- `GoogleCalender(Browser)`: triggers calendar export ZIP download from Google Calendar web UI; also fetches calendars individually via `get_extra_calendars()` (see "Extra Google calendars" below)
- `Sakura(Browser)`: composes and addresses messages in Sakura notification system

**`Calender/`** — Data model classes, independent of browser:
- `Event` / `AllDay` / `MultiDay`: a single calendar event; `input_cyboze()` and `delete_cyboze()` take a `Browser` instance and drive the UI. `Event`/`AllDay` accept optional `participants`/`facilities` lists (`[(cybozu_id, display_name), ...]`) that get injected into the Cybozu entry form (see "Cybozu ScheduleEntry form internals" below). Both `Event.input_cyboze()` and `AllDay.input_cyboze()` retry `driver.get()` in a loop until the `Detail` field is actually present before filling the form — the ScheduleEntry page doesn't always finish loading within Selenium's implicit wait, and hitting `find_element` too early raises `NoSuchElementException`. (`AllDay` was missing this retry loop until it was added to match `Event`.)
- `Calender`: collection of Events with `union()`, `substract()` (set difference), `filtering_by_date()`
- `CybozeCalender(Calender)`: reads from Cybozu's exported CSV (CP932 or UTF-8)
- `GoogleCalender(Calender)`: parses `.ics` files manually from `./data/GoogleCalender/`; expands recurring events into individual instances. Accepts `extra_participants`/`extra_facilities` which get stamped onto every `Event` parsed from that one `.ics` file

### Sync flow (`ScheduleSync.py`)

1. Download Google Calendar → extract `.ics` files → `chrome.get_extra_calendars()` fetches any registered extra calendars individually → parse all `.ics` files in `./data/GoogleCalender/` into `Calender` objects (unioned together)
2. Download Cybozu schedule CSV → parse into `CybozeCalender`
3. Filter both to a date window (yesterday → +1 year)
4. `ccal - gcal` → events to delete from Cybozu
5. `gcal - ccal` → events to input into Cybozu

The whole flow runs inside a `while True` / `except Exception` retry loop that prompts the user to retry or Ctrl+C on failure. The handler calls `traceback.print_exc()` before printing `Error occurred: {e}` — check the printed traceback (not just the one-line message) to find the actual failing file/line, since Selenium exceptions' `str(e)` is just the opaque chromedriver-side stack.

### Event identity

Events are matched (`Event.match()`) by comparing only `title`, `start_time`, `end_time`. `id` is still generated as `str([name, start_time, end_time, uid])` — a string representation of the list, stored in Cybozu's memo field during input and read back during CSV export (only events with `datetime.datetime(` in the memo field are treated as auto-synced events) — but as of the fix below it is **not** used for identity/matching, only for display/debugging and as the search text `delete_cyboze()` uses to locate the record to delete. `participants`/`facilities` are also NOT part of identity — changing them for a source calendar only affects newly-input events, not ones already synced.

`id` (and thus `uid`) used to be part of the match too, but this was found to cause a real, recurring bug: some Google-side calendars (observed on `music_room.ics`, e.g. repeating `個人練習(他の部員も参加可)` slots) get their events deleted and recreated with a fresh `UID` while `title`/`start_time`/`end_time` stay identical — confirmed by diffing a raw ICS export against the raw Cybozu CSV export for the same slot side by side (same title/date/time, different `UID` embedded in the stored memo). Matching on the full `id` treated these as brand-new events forever: the sync kept trying to re-input an already-synced slot, which either silently created a duplicate row (non-facility events — confirmed live: 13 duplicate title+start+end row-pairs already existed in a real CSV export) or, for facility-reserved slots (e.g. 音楽練習室), got rejected as a double-booking (error 14312) and crashed/retried indefinitely. Matching on `title`+`start_time`+`end_time` alone fixes both: a UID-churned event is now recognized as already-synced, and the stale duplicate lingering in Cybozu (which used to fall outside `ScheduleSync.py`'s 1-year delete window once old enough, so it could never be cleaned up) is naturally treated as the same event instead of orphaned.

`Cyboze.input_schedule()`/`delete_schedule()` also wrap each event's `input_cyboze()`/`delete_cyboze()` call in try/except: one event failing (e.g. a genuine facility conflict, or any other per-event error) is logged and skipped — via `Cyboze._dismiss_lingering_alert()`, which accepts any native `alert()` left open — instead of propagating out and taking down the whole sync run (which used to feed `ScheduleSync.py`'s outer `while True`/retry loop, re-downloading and re-diffing everything from scratch on every single failure).

### Extra Google calendars (calendars missing from the bulk export)

Google's `/exporticalzip` bulk-export endpoint silently omits some calendars you can view/edit but don't own (observed for a calendar shared with "make changes and manage sharing" permission from another account) — even though other non-owned-but-subscribed calendars *are* included. There's no reliable rule for which non-owned calendars get excluded, so don't assume a shared calendar is covered by the bulk export; verify by diffing the zip contents against the calendar list.

Workaround: `GoogleCalender.add_extra_calendar(key, secret_ics_url, display_name)` registers a calendar's private "Secret address in iCal format" URL (Calendar Settings → that calendar → Integrate calendar) into `Chrome/status.binaryfile` under `extra_calendar_<key>_url`/`_name`. `GoogleCalender.get_extra_calendars()` then downloads each registered URL directly and saves it as `./data/GoogleCalender/<key>.ics`, so it's picked up by the normal directory scan in `ScheduleSync.py`. Currently registered: `music_room` (音楽練習室, `kagawakosenkeionbu@gmail.com`).

`music_room` events also get `MUSIC_ROOM_EXTRA_FACILITIES` (施設: 音楽練習室) stamped onto them in `ScheduleSync.py`, and Cybozu's `ScheduleEntry` form rejects a facility reservation with no time (`施設を予約する場合は、時刻を入力してください。` native alert, which surfaces as `UnexpectedAlertPresentException` on the next `wait_element` call) — `AllDay.input_cyboze()` never sets a time. So `ScheduleSync.py` passes `skip_allday=True` to `Calender.GoogleCalender(...)` for `music_room.ics` specifically, and `Calender.GoogleCalender.__init__`'s 終日予定 branch skips appending `Event.AllDay` instances entirely when set — all-day events on this calendar are never synced to Cybozu at all (not deleted either, since they never enter `gcal`).

`music_room.ics` also contains per-person placeholder entries (titled e.g. `北村`/`前田`, both all-day and timed) that aren't real practice sessions but still inherit the 音楽練習室 facility stamp — when their time range overlaps an actual practice-session event, Cybozu rejects the input with error 14312 (`「音楽練習室」の他の予約と時間帯が重なっています。`, a facility double-booking conflict). `ScheduleSync.py` passes `skip_titles=MUSIC_ROOM_SKIP_TITLES` (`['北村', '前田']`) for `music_room.ics`; `Calender.GoogleCalender.__init__` checks the title immediately after extracting `SUMMARY:` and `continue`s past the whole `BEGIN:VEVENT` block if it matches, before any all-day/timed/recurring branching — so these are skipped regardless of shape, same as all-day events (never synced, never deleted, since they never enter `gcal`).

`music_room` is also exempted from the normal sync window (`now - 1 day` .. `now + 365 days`, applied in `ScheduleSync.py`): `gcal_other` (all non-music_room calendars) and `gcal_music_room` are tracked separately through the parse loop. For the input diff, `gcal_music_room` gets its own wider window instead — `2025-04-01` .. `now + 100 years` (effectively unlimited going forward) — via a dedicated `filtering_by_date(music_room_start, music_room_end)` call, and the result is diffed against the *unfiltered* `ccal` (`gcal_music_room_filter.substract(ccal, ...)`) instead of `ccal_filter`, so a music_room event back to 2025-04-01 or arbitrarily far in the future is still recognized as "already synced" and not endlessly re-input. The delete side is intentionally left unchanged (still computed from the normal windowed `gcal_filter`/`ccal_filter`, which includes music_room's in-window subset via the `gcal = gcal_other.union(gcal_music_room)` used there) — `ccal` has no per-event source-calendar tag, so widening the delete comparison to all time would risk flagging unrelated old Cybozu entries (from any calendar) that merely fall outside the window as deletable. For the unfiltered `ccal` comparison to actually see far-past auto-synced entries, `Cyboze.get_calender()` also selects a start year/month on the `PersonalScheduleExport` form before exporting. The start-date fields are named `SetDate.Year`/`SetDate.Month`/`SetDate.Day` — **not** `StartDate.*` despite the end-date fields being `EndDate.Year`/`EndDate.Month` (confirmed live: the initial `StartDate.*` guess silently no-op'd via a swallowed `NoSuchElementException`, leaving the export's start date at the form default and causing already-synced music_room events older than that default to be re-diffed as "missing" and re-input, which Cybozu then rejected as a facility double-booking). The select-name lookup on failure (dumping every `<select>` `name` on the page) is what surfaced the real field name — keep that fallback if this ever breaks again after a Cybozu form change.

Don't jump the year select to the earliest available option (`select_by_index(0)`, which resolved to 1997) — confirmed live that a ~36-year export range makes the subsequent `Export` button click hang until ChromeDriver's own command-response HTTP client times out (`urllib3.exceptions.ReadTimeoutError`, `read timeout=120`, not `page_load_timeout`/`patient_get` — this is Selenium's remote-connection client timing out waiting for the click command to return, because the browser itself is stuck generating/processing a huge CSV). Instead, `get_calender()` searches `SetDate.Year`'s options for the one containing `'2025'` (matching `music_room_start` in `ScheduleSync.py`) and falls back to index 0 only if no such option exists — this keeps the exported range wide enough for music_room's 2025-04-01 floor without ballooning it to decades. The `SetDate.Day` field is left at its default (already `1`) rather than explicitly set — the guessed visible-text format `'1日'` for that select didn't match live (`month` at `'1月'` did match, so day's format is apparently different/unconfirmed) and isn't needed since day-level precision doesn't matter for a synced-or-not check.

### Windows Hello / manual-auth waits

Cybozu login (and possibly other navigations) can trigger an OS-native Windows Hello PIN prompt that blocks Selenium's `driver.get()` — it either raises `TimeoutException` (after `page_load_timeout=120s`) or, worse, silently leaves the browser on the *previous* page while Selenium script execution continues unblocked.

`Browser.patient_get(url, description, wait_for=None)` handles this: it calls `driver.get(url)` (swallowing `TimeoutException`), then polls via `wait_for_manual_step()` until the page is actually ready. `wait_for_manual_step()` has no timeout by default (`timeout_hours=None` → waits indefinitely), printing a "waiting" status line every 60s — this is intentional, since the wait is for a human to physically complete the PIN prompt and there's no way to know how long that takes.

The base readiness check (`document.readyState == 'complete'` and the target domain appears in `driver.current_url`) is a **false positive** while a PIN dialog is still blocking navigation: if the previous page happened to be on the same domain, both conditions can already be true even though `driver.get(url)` hasn't actually taken effect yet, and the code proceeds to interact with a page that hasn't loaded (surfaced as `NoSuchElementException` on whatever field it looks for next — e.g. `EndDate.Year` in `Cyboze.get_calender()`, reproduced with the PIN deliberately left unentered). To guard against this, `patient_get` accepts an optional `wait_for=(By, value)` locator naming an element that only exists on the *actual target page*; if given, readiness additionally requires `find_element(*wait_for)` to succeed, retrying `driver.get(url)` on each failed poll. `Cyboze.get_calender()` passes `wait_for=(By.NAME, 'EndDate.Year')` for this reason. `Cyboze.login()`'s `patient_get` call does not use `wait_for` (no single element reliably marks "logged in" across both the first-time and already-logged-in flows there); it currently relies on the weaker domain/readyState check followed by its own try/except around the post-login element lookups.

### Cybozu ScheduleEntry form internals (participants & facilities)

The 予定入力 (`page=ScheduleEntry`) form has two structurally-identical widget groups, each three `<select>`s wired by inline JS — not a popup:

- 参加者: `sUID` (multiple, the actual submitted participant list, pre-loaded with the logged-in user) / `CGID` (group filter dropdown) / `CID` (candidate members of the selected group). The real "← 追加" button moves a `CID` option into `sUID`.
- 施設: `sFID` (multiple, actual submitted facility reservations) / `FGID` (facility-group filter) / `FCID` (candidate facilities).

On submit, `PreSubmitCGID`/`PreSubmitFGID` force-`selected = true` every `<option>` in `sUID`/`sFID` except the trailing blank placeholder — so a plain `<option value="id">name</option>` appended via `execute_script` (what `Event._add_participants`/`_add_facilities` do) is submitted exactly like one added through the UI, without needing to drive the group-dropdown/search/add-button flow (which is also fragile: some entities — e.g. a facility like 音楽練習室 — don't appear in the flat "(全員)"/user-search results, only inside the org-tree; and the two "← 追加" buttons share the same class/label, so a naive selector clicks the participants one even when you meant facilities).

A Cybozu-internal ID (e.g. a facility's `FGID`/`FID`) is **not** valid in the other namespace — a facility ID silently gets dropped if inserted into `sUID`, it does not error. If you need a new entity's ID, confirm which select it actually belongs to by testing, not by assuming from the org-tree grouping.

Deleting an event with more than one participant/facility has two gotchas `delete_cyboze()` handles: the search-results link text gets a trailing `+` (use `PARTIAL_LINK_TEXT`, not exact match), and the confirmation page (`page=ScheduleDelete`) adds a required `name="Member"` radio (`all` vs `single`) that must be selected before clicking 削除する/Yes, otherwise a native `alert()` ("条件を選択してください。") silently blocks the deletion. That `Member` radio has been observed to throw `ElementNotInteractableException` on a plain `.click()` (it's present in the DOM but not click-interactable in the WebDriver sense) — `delete_cyboze()` clicks it, the title link, and the 削除する/Yes links via `browser.safe_click()` for this reason.

### File locations

- `./data/` — downloaded files (Cybozu CSV, Google Calendar ICS/ZIP); files are deleted after parsing
- `./data/GoogleCalender/` — extracted/individually-fetched ICS files
- `Chrome/status.binaryfile` — persisted status (user IDs, names, Google account ID, `extra_calendar_*` registrations)

### Legacy code

`Edge/` contains an older version using `msedge-selenium-tools` (Edge WebDriver), superseded by the `Chrome/` implementations. `Other/` has standalone utility scripts.

## Known Limitations

- Moving a recurring event in Google Calendar does not delete the original from Cybozu
- `MultiDay.input_cyboze()` is a no-op (multi-day spans are not synced)
- Hardcoded user paths (`C:/Users/Yusaku/...`) appear throughout scripts
- The `.ics` parser (`Calender.GoogleCalender`) is manual regex-ish string extraction, not a real iCalendar parser — it only understands the field combinations Google happens to emit. A single-moment VEVENT with `DTSTART` but no `DTEND` (seen on old manually-created events) used to crash the whole sync with `UnboundLocalError: edaytime`; it's now treated as a zero-duration event (`edaytime = sdaytime`). If a new "Error occurred" shows an `UnboundLocalError` for `sdaytime`/`edaytime` again, it's almost certainly another DTSTART/DTEND field-name variant this parser doesn't recognize — inspect the raw `.ics` (left on disk in `./data/GoogleCalender/` when parsing throws, since the delete-after-parse only runs on success) for the offending `BEGIN:VEVENT` block.
