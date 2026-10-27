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
- **SHR欠席者へのさくら連絡網**: `pixi run shr [MMDD]`（`python shr_absence_sakura.py [MMDD|YYYY-MM-DD]` と同じ）（送信確認画面で止まり、送信完了の alert を検知して終了）
- 両スクリプトとも `-x 3,15,22` でサイボウズに欠席連絡がある学生の出席番号を宛先から除外できる（`absence_notice.py`。Garoon からの自動取得＝`docs/backlog_garoon.md` の4 までの手動版。授業欠課では除外した学生を送信記録に `欠席連絡あり` として書き、やり直しても飛ばす。`--force` では `送らず` と同じく聞き直す）
- **授業欠課者へのさくら連絡網**: `pixi run absence [MMDD]`（`python class_absence_sakura.py`。`--inspect` で出力ファイルの構造確認）（学生ごとに送信確認画面で止まる）
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
- `GoogleCalender(Calender)`: parses `.ics` files from `./data/GoogleCalender/` using the `icalendar` library, and expands `RRULE` recurring events (`WEEKLY`/`DAILY`/`MONTHLY`/`YEARLY`, including all-day) into individual instances via `dateutil.rrule`. Accepts `extra_participants`/`extra_facilities` which get stamped onto every `Event` parsed from that one `.ics` file

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

Whether a calendar is included in the bulk export can change on Google's side: as of 2026-08-20 the `music_room` calendar (`kagawakosenkeionbu@gmail.com`, registered as an extra calendar precisely because it *used* to be omitted) started appearing in the `/exporticalzip` output as well, as `kagawakosenkeionbu@gmail.com.ics`. Because `ScheduleSync.py` identified the music_room calendar by the exact filename `music_room.ics`, the bulk-export copy was treated as just another unrelated calendar — no 音楽練習室 facility stamp, no `skip_allday`, no `skip_titles` — so its all-day entries and 北村/前田 placeholder entries got synced into Cybozu as ordinary personal events (the timed practice sessions themselves were mostly spared: they matched the already-synced facility-reserved rows in `ccal` and were subtracted out). Fix: `MUSIC_ROOM_CALENDAR_KEYWORDS = ['music_room', 'keionbu']` — any ics filename containing one of these keywords gets the music_room treatment, so the calendar is handled correctly regardless of which path delivered it. Don't reduce this back to a single filename match, and don't instead *exclude* the bulk-export copy: if `get_extra_calendars()` ever fails, an excluded-and-not-fetched music_room would make `gcal` empty for that calendar and the delete diff would wipe every synced practice session out of Cybozu.

The flip side of accepting both copies is that the same event now arrives twice, and `Calender.union()` doesn't dedupe — a duplicate would be input twice (the second insert of a facility-reserved slot then fails with 14312). So `ScheduleSync.py` calls the new `Calender.Calender.unique()` on `gcal_other` and `gcal_music_room` before diffing; it collapses events with identical title/start/end (same condition as `Event.match()`, title run through `_unescape_legacy_ical_text` likewise) via a dict-keyed pass rather than pairwise `match()` calls, since recurrence expansion over the 100-year horizon can make these lists large. Verified live on the real `basic.ics`: the two copies produce 3452 events, `unique()` → 1725. Dedupe is applied per group (music_room / other) rather than to the merged `gcal`, so it can't drop an event's facility/participant stamps by keeping whichever copy happened to come first.

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

Deleting an event with more than one participant/facility has two gotchas `delete_cyboze()` handles: the search-results link text gets a trailing `+` (so a plain exact-text match misses it — see the paragraph below for how `_find_schedule_link()` handles it), and the confirmation page (`page=ScheduleDelete`) adds a required `name="Member"` radio (`all` vs `single`) that must be selected before clicking 削除する/Yes, otherwise a native `alert()` ("条件を選択してください。") silently blocks the deletion. That `Member` radio has been observed to throw `ElementNotInteractableException` on a plain `.click()` (it's present in the DOM but not click-interactable in the WebDriver sense) — `delete_cyboze()` clicks it, the title link, and the 削除する/Yes links via `browser.safe_click()` for this reason.

Locating the search-result row must **not** be a bare `By.PARTIAL_LINK_TEXT` on the title: that matches any link on the page containing the title as a substring, including Cybozu's header links. Confirmed live: an event titled `前田` (a music_room per-person placeholder that got wrongly synced before `skip_titles` existed) matched the logged-in user's name link `前田祐作` in the top-right of every page, so `delete_cyboze()` clicked that instead of the search result, found no 削除する link on the page it landed on, and skipped the event with the "検索結果に見つからない" warning — forever, on every run. `Event._find_schedule_link()` now requires the link text to equal the title exactly, allowing only a trailing decoration from `Event._LINK_TEXT_SUFFIXES` (`+` for multi-participant/facility events, `…`/`...` in case Cybozu ever truncates). If partial matches exist but none matches exactly, it prints their texts and returns `None` so a future Cybozu format change is visible in the log instead of silently clicking the wrong link.

### サイボウズ Garoon 6 への移行（2026-11-09）

高専のサイボウズは **2026-11-09(月)** に Office 10 から **Garoon 6.17.2** へ移行する（Office 10 のライセンス終了は 2027-03-31、試験運用期間は 2026-09-15〜10-15）。Garoon には **REST API** があるので、Office 10 で必要だった Selenium の画面操作は全部捨てられる。`Garoon/Client.py` の `GaroonClient` と `Calender.GaroonCalender` が実装済みで、`ScheduleSync.py` の `BACKEND`（`'cybozu'` / `'garoon'`、既定は `'cybozu'`）で切り替える。移行当日はこの定数を `'garoon'` にするだけ。環境変数 `SCHEDULE_SYNC_BACKEND` でも上書きできる。残作業は `docs/backlog_garoon.md`。

- ベースURL `https://garoon.da.kagawa-nct.ac.jp/scripts/cbgrn/grn.exe/api/v1`。認証は **`X-Cybozu-Authorization: base64("ログイン名:パスワード")` ヘッダのみ**。`Authorization: Basic` も Windows 統合認証もブラウザのセッションクッキーも通らない（実機確認済み）。資格情報は Windows 資格情報マネージャー（`keyring`、service=`ChromeTools-Garoon`）に置き、`Other/set_garoon_password.py` で登録する。
- **Office → Garoon のコンバートでメモ欄・施設・参加者はそのまま保持される**（実機確認済み）。したがって「メモに `datetime.datetime(` を含む＝このツールが自動入力した予定」という同一性判定はそのまま通用し、移行直後に全件が再入力される事態は起きない。
- `GET /schedule/events` は `notes` をそのまま返し、予定の `id` も取れる。これにより **CSV エクスポート＋pandas パース（`Cyboze.get_calender()` / `CybozeCalender`）も、削除時にタイトルで検索結果のリンクを探す処理（`Event._find_schedule_link()`）も不要になる**。削除は ID 直指定。`Chrome` の全プロセス kill も Windows Hello の PIN 待ち（`patient_get`）も不要。
- エラーはネイティブ `alert()` ではなく HTTP 400 + `X-Cybozu-Error` で返るので、`_dismiss_lingering_alert()` 相当も不要。実測したコード: `GRN_SCHD_13208`＝施設の二重予約（Office 10 の 14312 相当）、`GRN_SCHD_13207`＝終日予定に施設は予約できない（**`skip_allday` は引き続き必要**）、`GRN_SCHD_13001`＝予定が存在しない、`GRN_REST_API_00003`＝認証情報なし。401 の本文は IIS のカスタム HTML エラーページに差し替えられているので、**本文ではなく `X-Cybozu-Error` ヘッダで判断すること**。
- **`GET /base/users` の絞り込みパラメータは `name` であって `code` ではない。** `?code=maeda-y` は黙って無視され全件の先頭（Administrator 等）が返る。エラーにならないので気づきにくい。`name` にログイン名を渡し、返ってきた中から `code` の完全一致を選ぶこと。これを誤ると参加者が空になり `POST /schedule/events` が 400 `GRN_REST_API_00216` で失敗する。
- **Garoon は終日予定を「その日の 00:00:00 〜 23:59:59」で返す。** `GoogleCalender` と `CybozeCalender` は終日予定の終了を「翌日 00:00」（終端排他）で持っているため、`GaroonCalender` で翌日 00:00 に正規化しないと `Event.match()` が永久に一致せず、**終日予定が毎回すべて再入力される**（実機の3か月分で終日が135件中89件あった）。
- 参加者・施設は数値IDではなく **`code`**（`maeda-y` / `band` / `kitamura-d` / `of_1_音楽練習室`）で引く。Garoon の数値IDは Office 10 とは全く別の連番で、本移行時に試験環境とも変わりうる。施設一覧 `GET /schedule/facilities` は `limit`/`offset` でページングすること（全127件あり、音楽練習室がちょうど127番目なので `limit=100` 一回だけでは取りこぼす）。
- **`rangeEnd` には 2037-12-31(JST) という絶対的な上限がある**（超えると 400 `GRN_REST_API_00220`）。期間の長さの制限ではなく絶対的な日付の天井で、`rangeStart` を後ろにずらしても同じ日付で切れる（いわゆる2038年問題）。`ScheduleSync.py` の music_room 用「実質無制限」ウィンドウ（`now + 100年`）は Garoon 使用時にここで頭打ちにしている。頭打ちにしないと、上限より先の予定が ccal 側に存在しえないため毎回「未入力」と判定されて登録を試み続ける。
- `ScheduleSync.py` には **`DRY_RUN`**（環境変数 `SCHEDULE_SYNC_DRY_RUN=1`）がある。差分を表示するだけで入力・削除を一切行わない。移行当日はまず dry-run で差分の妥当性を確認してから本実行すること。
- **読み戻した `Calender` をそのまま `delete_schedule()` に渡してはいけない。** 検証スクリプトでこれをやり、試験環境の実予定22件を実際に削除した（2026-09-16）。検証で作った予定を消すときは、自分が作成したIDのリストだけを対象にすること。

2026-09-16 に試験環境で `BACKEND=garoon` の通し実行を完走（警告・エラーゼロ）。削除22件・入力296件が全件成功し、マーカー付き予定は 1878 → 2152。施設つき996件・終日320件を含め、参加者/施設/終日の往復が正しいことを確認済み。

### Office Hour（変形労働カレンダー → Google Calendar）

`Other/WorkingCalenderToIcalender.py` が、半期ごとに配布される変形労働カレンダーのxlsx（`*変形労働カレンダー*.xlsx`、「教員修正用」シート）から勤務時間を抽出して `data/Office_Hour.ics` を生成し、Googleカレンダーの `Office hour` カレンダーへ取り込む。同じ目的のスクリプトが3本（旧`Other/WorkingCalenderToICAL.py`、旧`変形労働カレンダーical化.py`）あったのをこの1本に統合した。ScheduleSync.py の流れとは独立した別エントリポイント。

各VEVENTには日付固定のUID `officehour-YYYYMMDD@officehour.chrometools` を振ってある。これが効いていて、**同じicsを再インポートしても重複せず既存予定が更新される**（2026-09-02に実カレンダーで確認: 9:00–10:00で2件取り込んだ後、同UID・14:00–15:00のicsを再インポートすると件数は2件のまま時刻だけ置き換わった）。当初想定していた「カレンダーごと削除して作り直す」方式は不要になったので実装していない。UIDを日付以外のもの（ランダム等）に変えると、この性質が失われて半期ごとに重複が積み上がるので変えないこと。時刻はタイムゾーンを付けないフローティング時刻＋`X-WR-TIMEZONE:Asia/Tokyo` で書く（JSTとして正しく解釈されることを同時に確認済み）。

裏を返すと、**前回のicsには有ったが今回のicsには無いUID**（勤務日→週休日に変わった日）の予定はGoogle側に残り続ける。これは手動で足りる頻度でしか生じないため、掃除の仕組みは意図的に実装していない。また `Office hour` は `EXCLUDED_CALENDAR_KEYWORDS` に含まれないので「勤務」予定はサイボウズにも同期されるが、これも意図通り。

`Chrome/GoogleCalender.import_ics(ics_path, calendar_name)` が設定 > インポート/エクスポート画面（`.../r/settings/export`）を操作する。ファイル選択の `input[type=file][name="filename"]` はCSSで隠されているが `send_keys()` は通る — **クリックしてはいけない**（OSのファイル選択ダイアログが開いてSeleniumから操作できなくなる）。インポート先の「カレンダーに追加」は `<select>` ではなくGoogle独自のリストボックス（`[role=combobox][aria-haspopup=listbox]` → `ul[role=listbox] li[role=option]`）なので `Select` は使えず、**座標でもなくオプションの表示テキストで引く**必要がある。リストの表示位置は前回選択項目に応じて上下にずれるため、座標決め打ちだと別のカレンダーが選ばれる（実機で `Office hour` を狙って `Share` が選択される事象を確認済み）。`_select_import_calendar()` は選択後に combobox の表示テキストを検証してから戻る。`aria-label`（`Add to calendar`）はUI言語依存なのでセレクタに使っていない。カレンダー名は Google側の実表記 `Office hour`（hは小文字）に厳密に一致させること。

2026-09-02に下半期の実xlsxで通し確認済み: 103件を読み取り、`import_ics()` を2回実行しても`Imported 103 out of 103 events.` で1日1件のまま重複しなかった。**実行はpixi環境で行うこと** — `Chrome/status.binaryfile` は numpy 2.x でpickle化されており、システムのPython 3.10（numpy 1.24）で走らせると `Browser.open_status()` が `ModuleNotFoundError: No module named 'numpy._core'` で落ちる。

詳細は `docs/handoff_office_hour_sync.md`。

### SHR欠席者へのさくら連絡網（`shr_absence_sakura.py`）

`SHR.xlsx`（担任フォルダ、OneDrive）の「点呼簿」シートから対象日の不在者を読み、直近に送信済みの「SHRへの出席について【M/D（曜）】」をコピーして件名の日付を書き換え、宛先を「個人から選ぶ」→ `機械工学科３年` から不在者に差し替え、送信確認画面（「送信」ボタンがある画面）まで進めて止まる。**送信はユーザーが押す。** ScheduleSync.py とは独立したエントリポイント。

- **SHR.xlsx・さくらの受信者一覧・サイボウズの欠席連絡は個人情報。氏名をログや画面出力に出さないこと**（件数と出席番号だけを出す）。例外として、さくら連絡網で宛先に一致しなかった学生だけは手動対応のため氏名を表示する（ユーザーの指示。SHR・授業欠課の両方）。さくらの宛先ページのスクリーンショットも撮らない。調査は JS で件数や属性名、文字種の統計だけを取って行った。
- 点呼簿は **199行目が日付**（`=B2` 等）、**200〜245行目が「出席番号_苗字　名前」**（不在でなければ空文字）。どちらも数式なので `openpyxl` の `data_only=True` で読むのはキャッシュ値で、Excel で開いて保存していない日付は存在しない。
- Excel で開いている（OneDrive 自動保存）と SHR.xlsx がロックされ `openpyxl` は `PermissionError` になる。その場合は起動中の Excel から COM（`pywin32`）で同じ範囲を読む（計算済みの現在値なので保存不要）。ブックの `FullName` は OneDrive の URL になりうるのでブック名で照合している。
- 職場の OneDrive の場所は PC で違う（本番PCは `D:\`）ので、パスは環境変数 `OneDriveCommercial` から組み立てる。
- さくらの受信者 `data-name` は「苗字　名前(〇〇3〇)」と**末尾にクラスの括弧書きが付く**ため、Excel の氏名と完全一致しない。`Chrome.Sakura.normalize_name()` で括弧書きと空白を落として照合する（2026-10 の実データで9/28〜10/5の4日分が全件一致、過去の送信件数とも一致）。
- 画面操作はボタンの位置ではなく、`onclick` に書かれた JS を直接呼ぶ: `Worker.OpenResult(No)` → `ResultWorker.CopyDist()`（confirm と完了 alert が続けて出る）→ `OpenDistEdit_Update(No)` → `MsgEditWorker.MessageNextPage()` → `OpenSubModal('screen-send-select')` → `DefineSendSelect(DIST_SEND_SELECT_TYPE.ACCOUNT)` → `OpenAccountAddModal(MsgEditWorker.LvSendAccount)` → `#cmbAccountSearchAff` で学年クラスを選択 → `#lstAccountAdd` のチェックボックス → `DefineAccountAddModal()` → `DefineSendDetail()`。学年クラスには同名の「（保護者）」グループもあるので、表示名の完全一致で選ぶ。
- コピー元が「個人から選ぶ」で宛先を入れたメール（＝このスクリプトで送ったもの）だと、コピーした下書きに個人の宛先一覧がそのまま残る（Excel 取込で宛先を入れたメールからのコピーでは残らない）。`set_recipients()` は追加前に `MsgEditWorker.LvSendAccount.Clear()` で空にする。
- 編集ダイアログの `txtSubject` は `MsgEditWorker` の初期化より先に表示されるので、件名の値が入るまで待ってから操作する（待たないと `MsgEditWorker` が null で落ちる）。
- `AutoSyncData` プロファイルにはさくらのパスワードが保存されていないため、`Sakura.login()` は自動入力が無ければ手動ログインを待つ。開発時は `--remote-debugging-port=9333` で起動した Chrome に `--debugger-address 127.0.0.1:9333` で接続すれば、ログインし直さずに済む。
- Garoon の「学生欠席等連絡」カレンダーとの自動照合は未実装（`docs/backlog_garoon.md` の4）。当面は `-x` で出席番号を手で渡す。
- 送信は授業欠課と同じ `Sakura.wait_for_send()` で完了の alert を検知する（`q` で送らずに終了）。以前は Enter 待ちだった。

### 授業欠課者へのさくら連絡網（`class_absence_sakura.py`）

丸一日ではなく一部の授業だけ欠課した学生に、学務係への事前連絡を促すメッセージを1人ずつ送る準備をする。`pixi run absence [MMDD]`。日付省略時は行事予定から前回の授業日を求める。欠課の内容（`format_lessons()` の文字列）がまったく同じ学生は1通に複数宛先でまとめ（宛名は「受信者氏名を差し込む」で個別になる）、1通ごとに送信確認画面で止まり、**送信はユーザーが押す**。記録は学生ごとに書く。送信はブラウザで送信した後の alert「メッセージの登録が完了しました。」を `Sakura.wait_for_send()` が検知して記録する（`msvcrt` でキー入力も同時に待つ。`s` で送らずに次へ、`q` で中断）。以前は Enter を送信とみなしていたが、送信できていない学生（出席番号16、2026-10-27）を送信済みと記録したのでやめた。送信前の確認など、それ以外の alert には触らない。

- 送信記録は OneDrive の `Work/講義/そのた科目/class_absence_sent.csv`（列: 日付・出席番号・欠課・結果・記録日時。結果は `送信`/`送らず`/`欠席連絡あり`（`-x` で除外）/`完了`。BOM 付き UTF-8）。1人ごとに即座に追記するので、`q` で中断しても再実行で残りの学生から続く。最後まで終えた日は `完了` 行があり、次からは何もしない。`--force` は `完了` を無視し `送らず` の学生も聞き直すが、`送信` 済みの学生は常に飛ばす（二重送信防止）。**氏名は書かない**（出席番号のみ）。Excel で開いているとロックされるので、書けなければ閉じるよう促して再試行する。以前の `data/class_absence_done.json` は廃止。
- さくら連絡網の表示名が Excel/KOSEN WEB の氏名と一致しない学生は、`sakura_names.py` の辞書（OneDrive `Work/講義/そのた科目/sakura_name_alias.csv`、列: 氏名・さくら表示名）で置き換えてから照合する。照合できなかったら表示名の入力を促して辞書に追記し、授業欠課ではそのメッセージを作り直す（SHR は1通にまとめて送るので作り直さず、今回は手動で追加してもらい次回から効く）。**辞書の中身は個人情報。Claude は絶対に読まないこと**（ユーザーの指示）。
- OneDrive のパスは `paths.py`（`../GRADING/packages/paths.py` と同じ方式: `OneDriveCommercial` → 候補ルートを順に試し `Work/講義` まであるものを優先）。`shr_absence_sakura.py` もこれを使う。

- **KOSEN WEB の出力ファイルは個人情報。Claude は中身を見ないこと**（ユーザーの指示）。出力は `tempfile.mkdtemp()` の一時フォルダに保存し（CDP `Browser.setDownloadBehavior` で切り替え、`data/` には落とさない）、読み終えたらすぐ消す。構造の確認は `--inspect`（見出し2行・授業列・出欠記号の件数だけ表示）で行う。
- 出力は xlsx（`read_only=True` だと右側の列が欠けるので通常モードで読む）。A列=出席番号、B列=氏名、I列以降=その日の授業1列ずつ。**1行目は `2026/10/23 1`（日付 時限）**で、時限はここからしか取らない（列位置から数えない。同じ時限に複数授業がある: 実例 5限に「物理学Ⅱ」と「大掃除」）。先頭の日付を除いて「N限」か数値だけのときに時限とみなし、読めなければ例外。2行目=授業名。セルの値は 空欄=出席 / `欠` / `遅` / `公` / `休` / `休講`。
- **全時限欠課（＝丸一日欠席、SHR 側で対応）と欠が無い学生は除外**。丸一日欠席は「`休講` 以外の列がすべて `欠`」で判定する（欠の数と列数の比較では休講の列で外れる）。同じ授業の連続時限は「1・2限 科目名」にまとめる。
- さくら連絡網の新規作成では、「次へ」の後に宛先一覧ページを経ず「宛先の選び方」画面が直接開く（コピーした下書きでは宛先一覧ページ → `OpenSubModal('screen-send-select')`）。`Sakura.new_message()` / `set_recipients()` は両方に対応。
- 行事予定は `data/*行事予定*.xlsx`（最新のもの）。月ブロックが横に並び、2行目の「N月」の列が曜、3行目でその右の「高松」列のさらに右隣が授業週番号（授業日は数字、試験・行事日は「〇」、休日は空欄）。日 d は d+3 行目。曜の列と実際の曜日を照合して、形が変わったら例外にしている。年度はファイル名の「令和N年度」から。
- KOSEN WEB（`Chrome/KosenWeb.py`）: 「日別出欠の閲覧（期間指定）」は `/kosen-web/wku0121/index/31/31-W-6-3-7`。項目は `#vi-con-nendo` / `#vi-con-datefrom`・`#vi-con-dateto`（`YYYY/MM/DD`、jQuery datepicker）/ `#vi-drp-years`（`3年`）/ `#vi-drp-classex`（`機械工学科`。「機械工学科（旧）」があるので完全一致）/ `#vi-btn-output`（JSON を POST してファイルが返る。`<form>` は無い）。ログインフォームは `#LoginID` / `#Password`。初回はパスワードが保存されていないので手動ログインを待つ。
- さくら連絡網は新規作成（`Sakura.new_message()`: `OpenDistEdit_New()` → `MsgEditWorker.DefineMessageType(DIST_MESSAGE_TYPE.MESSAGE)`）。本文は Quill エディタ（`MsgEditWorker.Editor.setText()`。「文字装飾OFF」時のみ `#txtaBody`）。宛先は SHR と同じ `set_recipients()`。送信確認画面で `Sakura.set_insert_recipient_name()` が `MsgEditWorker.OpenOptionDialog()` → `#rdoInsertAccountName_ON` → `DefineOptionDialog()` で「受信者氏名を差し込む」を「する」にする。
- KOSEN WEB の取得は既定でヘッドレス（`Browser(headless=True)` → `--headless=new`。`--show` で画面あり）。未ログインでパスワードの自動入力も無いと `KosenWeb.login()` が `LoginRequired` を投げ、画面ありで起動し直して手動ログインを待つ。ヘッドレスで取得した場合、さくら連絡網は画面ありの Chrome を新たに開く（送信内容を目で確認するため）。出力 xlsx は `read_only=True` で読むと右側の列が欠けたので通常モードで読む。
- KOSEN WEB とさくら連絡網は、画面ありで取得した場合は同じ Chrome を使う（`Browser.share_driver()`）。`--debugger-address` は `Browser.__init__` に移した（以前は `Sakura` 独自）。
- Garoon の「学生欠席等連絡」との照合は未実装（`docs/backlog_garoon.md` の4と同じ）。

### File locations

- `./data/` — downloaded files (Cybozu CSV, Google Calendar ICS/ZIP); files are deleted after parsing
- `./data/GoogleCalender/` — extracted/individually-fetched ICS files
- `Chrome/status.binaryfile` — persisted status (user IDs, names, Google account ID, `extra_calendar_*` registrations)

### Legacy code

`Edge/` contains an older version using `msedge-selenium-tools` (Edge WebDriver), superseded by the `Chrome/` implementations. `Other/` has standalone utility scripts — note that `Other/WorkingCalenderToIcalender.py` is *not* legacy, it is the active Office Hour entry point (see above).

## Known Limitations

- Moving a recurring event in Google Calendar does not delete the original from Cybozu
- `MultiDay.input_cyboze()` is a no-op (multi-day spans are not synced)
- Hardcoded user paths (`C:/Users/Yusaku/...`) appear throughout scripts
- The `.ics` parser (`Calender.GoogleCalender.__init__`) used to be manual regex-ish string extraction, which silently failed to expand almost all real-world recurring events (see `docs/investigation_recurring_events.md`). It was rewritten to use `icalendar` (real iCalendar parsing, including RFC5545 text unescaping/line-unfolding) plus `dateutil.rrule` for recurrence expansion (`WEEKLY`/`DAILY`/`MONTHLY`/`YEARLY`, `BYDAY` nth-weekday forms like `1MO`/`-1FR`, `EXDATE`, and `RECURRENCE-ID` per-occurrence overrides). A single-moment VEVENT with `DTSTART` but no `DTEND` is treated as a zero-duration event. Recurring events with neither `UNTIL` nor `COUNT` (unbounded) are capped at a `now + 100 years` horizon (`Calender.Calender._RECUR_HORIZON`), reusing the same "effectively unlimited" convention `ScheduleSync.py` already uses for `music_room`'s widened sync window — this avoids ever needing to fully materialize a truly-infinite `RRULE`.
