# 変形労働カレンダー → Google Calendar 自動同期

## 目的
半期ごとに手動でやっている以下の作業を自動化する。
1. 変形労働カレンダーのxlsx（教員修正用シート）から勤務時間を抽出してicsを作る
2. 新しいicsを Googleカレンダーの「Office hour」カレンダーへ取り込む

当初は「2. 既存のOffice Hourカレンダーを削除して作り直す」「3. icsをインポートする」の
2段構えを想定していたが、**カレンダー削除は不要になった**（下記「UID上書きの検証結果」）。

## 現状: 実装・実データでの通し確認まで完了

### スクリプトの一本化
同じ目的のスクリプトが3本あったのを `Other/WorkingCalenderToIcalender.py` に統合した。
- 削除: `変形労働カレンダーical化.py`（リポジトリ直下・xlsx対応版）
- 削除: `Other/WorkingCalenderToICAL.py`（`WorkingCalender.csv` を読む3列組レイアウト版。
  勤務時間の前後を「不在」として出力する別仕様だった。加えて `data_list[1:31]` の
  スライスで毎月31日を取りこぼすバグがあった）
- 残す: `Other/WorkingCalenderToIcalender.py` ← ここに集約

`find_source_xlsx()` はスクリプトがOther/配下に移ったため、**リポジトリ直下と
スクリプトと同じディレクトリの両方**から `*変形労働カレンダー*.xlsx` を探す
（xlsxはリポジトリ直下に置かれる運用）。

### UID上書きの検証結果（2026-09-02、実カレンダーで確認）
生成する各VEVENTに日付固定のUID `officehour-YYYYMMDD@officehour.chrometools` を
振るようにした。これにより **Googleカレンダーへの再インポートは重複作成ではなく
既存予定の更新になる**。

検証手順と結果:
- 2030-06-05 / 06-06 の 9:00–10:00「勤務」2件を含むicsを `Office hour` へインポート
  → `Imported 2 out of 2 events.`、2件作成された
- **同じUIDのまま時刻だけ 14:00–15:00 に変えた**icsを再インポート
  → `Imported 2 out of 2 events.`、件数は2件のまま**時刻だけが置き換わった**（重複なし）
- 時刻のズレなし。タイムゾーンを付けないフローティング時刻＋`X-WR-TIMEZONE:Asia/Tokyo`
  で JST として正しく解釈される（旧実装から変えていない形式）
- 検証に使った2件は削除済み

したがって「取り消し不能なカレンダー削除 → 再作成」は実装しない。

### Googleカレンダーへの取り込み（`Chrome/GoogleCalender.import_ics()`）
設定 > インポート/エクスポート（`https://calendar.google.com/calendar/u/0/r/settings/export`）
のフォームを操作する。確認済みのDOM構造:

| 要素 | セレクタ | 注意点 |
|---|---|---|
| ファイル選択 | `input[type=file][name="filename"]` | CSSで隠されているが `send_keys()` は通る。**クリックするとOSのファイル選択ダイアログが開く**ので絶対にクリックしない |
| インポート先 | `[role=combobox][aria-haspopup=listbox]` → `//ul[@role="listbox"]//li[@role="option"]` | `<select>` ではないので `Select` は使えない |
| インポート実行 | `button[jsname="N8B8lb"]` | ファイル未選択の間は `disabled` |
| 結果ダイアログ | `div[role=alertdialog]` | 文言は `Imported N out of M events.`（英語UI） |

**インポート先の選択は座標ではなくオプションの表示テキストで引くこと。**
リストの表示位置は「前回選択した項目」に応じて上下にずれるため、座標決め打ちだと
別のカレンダーが選ばれる。実機で `Office hour` を狙って `Share` が選択される事象を
確認済み（インポート前に選択内容を目視確認して事なきを得た）。`import_ics()` は
選択後に combobox の表示テキストを検証してから実行するようにしてある。

`aria-label`（`Add to calendar`）はUI言語に依存するのでセレクタに使っていない。
このアカウントのGoogleカレンダーUIは現在 English (US)。

カレンダー名は Google側の実表記に合わせて **`Office hour`（hは小文字）**。
統合前のスクリプトは `'Office Hour'` だったので、表示テキストで引く以上ここは一致必須。

### エントリポイント
```
python Other/WorkingCalenderToIcalender.py
```
xlsxを探す → ics生成（`data/Office_Hour.ics`）→ 取り込むか対話で確認 → `import_ics()`。
Chromeプロファイルは ScheduleSync.py と同じ自動化専用プロファイル
（`C:/Users/Yusaku/AppData/Local/Google/Chrome/AutoSyncData/`）。

## 実データでの通し確認（2026-09-02）
`令和8年度変形労働カレンダー（高松キャンパス教員）下半期マスター_ME前田 ★修正あり.xlsx`（下半期）で実施。
- xlsx読み取り: 103件（2026-10-02〜2027-03-31、月別 10月22/11月16/12月16/1月16/2月17/3月16）、UID重複なし
- インポート前の `Office hour` は2026-09-30までしか勤務予定が無く（上半期分）、下半期は空だったため既存予定との衝突なし
- `import_ics()` を2回実行。1回目も2回目も `Imported 103 out of 103 events.`、
  カレンダーは1日1件のままで**重複は発生しなかった**（実データでも冪等）

**実行はpixi環境で行うこと。** `Chrome/status.binaryfile` は numpy 2.x でpickle化されているため、
システムのPython 3.10（numpy 1.24）で実行すると `open_status()` が
`ModuleNotFoundError: No module named 'numpy._core'` で落ちる。
`pixi run python Other/WorkingCalenderToIcalender.py` のように起動する。

## 既知の割り切り（対応しない）
- **勤務日→週休日に変わった日の予定がGoogle側に残る。** 今回のicsに無いUIDの予定は
  インポートでは消えない。手動で足りる頻度でしか生じないため、掃除の仕組みは実装しない。
- **`Office hour` がScheduleSync.pyの同期対象に入っている**（`EXCLUDED_CALENDAR_KEYWORDS` に
  含まれない）ので「勤務」予定はサイボウズにも入力される。これは意図通り。

## 関連ファイル
- `Other/WorkingCalenderToIcalender.py` — 統合済みエントリスクリプト
- `Chrome/GoogleCalender.py` — `import_ics()` / `_select_import_calendar()`
- `Chrome/Browser.py` — `patient_get`/`safe_click`/`wait_for_manual_step` 等の共通部品
- `Chrome/status.binaryfile` — `googleID` 等の永続設定
