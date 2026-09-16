# バックログ（Garoon 移行まわり）

2026-11-09 の Office 10 → Garoon 6 移行に向けた作業のうち、**移行そのものには必須でない**ものを
ここに残しておく。移行必須の部分（Google → Garoon の同期）は実装・実機検証とも完了済み。

移行そのものの詳細（実測したAPI仕様、踏んだ落とし穴、当日の切替方法）は
`CLAUDE.md` の「サイボウズ Garoon 6 への移行」節を参照。

---

## 1. 移行当日の手順書を用意する

**状態**: 未着手
**期限**: 2026-11-09 まで
**なぜ必要か**: 実装から移行まで2か月空くため、当日に手順を思い出せない可能性が高い。

`docs/` に短いチェックリストを置く。少なくとも次を含めること。

- `ScheduleSync.py` の `BACKEND` を `'cybozu'` → `'garoon'` に変更する
  （ファイルを書き換えずに試すなら環境変数 `SCHEDULE_SYNC_BACKEND=garoon`）
- **まず dry-run で差分を確認してから本実行する**

  ```powershell
  $env:SCHEDULE_SYNC_BACKEND='garoon'; $env:SCHEDULE_SYNC_DRY_RUN='1'; pixi run python ScheduleSync.py
  ```

  差分が数千件規模になっていたら何かが壊れているので、そのまま本実行しないこと。
  特に**終日予定が大量に input に出ていたら `GaroonCalender` の終日正規化を疑う**。
- 資格情報が未登録なら `pixi run python Other/set_garoon_password.py`
- `ScheduleSync.py` の `GAROON_MUSIC_ROOM_EXTRA_PARTICIPANTS` /
  `GAROON_MUSIC_ROOM_EXTRA_FACILITIES` は code 指定（`band` / `kitamura-d` /
  `of_1_音楽練習室`）。本番で code が変わっていたら、
  `GaroonClient.find_user()` / `find_facility()` で引き直して差し替える。
  解決できなかった場合は警告を出して**その予定には付与せずに登録される**ので、
  初回は警告が出ていないかログを確認すること。
- Office 10 側（`Chrome/Cyboze.py` 経路）は当面そのまま残す。
  ライセンス終了は 2027-03-31 なので、慌てて消さない。

## 2. 逆方向の同期（Garoon → Google カレンダー）

**状態**: 未着手（方式だけ決定済み）
**きっかけ**: 他の方がサイボウズ側に入れてくださった予定も Google カレンダーで見たい。

`GET /schedule/events` は他人が登録した予定も返すことを実機で確認済み
（例: 藤岡先生が登録した「企業面談」に前田が参加者として入っているもの）。

**採用方式: Google Calendar API（OAuth）**。
`Chrome/GoogleCalender.import_ics()` を再利用する ics 方式も検討したが、
**Garoon 側で削除された予定を Google から消せない**ため見送った。
Office Hour（`Other/WorkingCalenderToIcalender.py`）は変更頻度が低いので
ics 方式のままで問題ないが、会議のキャンセルは日常的に起きるため逆方向には向かない。

設計上の注意:

- **同期ループを防ぐこと。** 取り込み先は Google 側に専用カレンダー（例: `Cybozu`）を作り、
  そのキーワードを `ScheduleSync.py` の `EXCLUDED_CALENDAR_KEYWORDS` に追加して
  Google → Garoon 方向に戻ってこないようにする。
- あわせて、`notes` に `datetime.datetime(` を含む予定＝このツールが入れた予定なので、
  逆方向では除外する（二重の安全弁）。
- Garoon 側の予定ID（`event.garoon_id`）を Google 側の UID に埋めておくと、
  更新・削除の対応付けが楽になる。

## 3. 過去日に残った `前田` プレースホルダの掃除

**状態**: 未着手（やるかどうか未決）

`skip_titles` 導入前に誤同期された music_room の個人名プレースホルダが、
**過去日**に8件残っている（試験環境で 2026-08-20〜09-11 を確認）。
`ScheduleSync.py` の削除ウィンドウが `now - 1日` 始まりなので通常同期では届かない。
本移行後の Garoon にも同じものが残る見込み。

実害は「過去の予定表に空の予定が数件見える」だけなので優先度は低い。
消すなら、過去日を対象に `title == '前田'` かつ同期マーカー付きの予定だけを
`GaroonClient.delete_event()` で消す単発スクリプトを書く。

**注意**: 読み戻した `Calender` をそのまま `delete_schedule()` に渡してはいけない。
2026-09-16 に検証スクリプトでこれをやり、試験環境の実予定22件を実際に削除した。
削除対象は必ず明示的に絞り込んだIDのリストにすること。
