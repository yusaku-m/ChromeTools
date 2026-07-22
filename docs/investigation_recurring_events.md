# 調査レポート: Googleカレンダーの繰り返し予定がサイボウズに同期されていない

- 調査日: 2026-07-22
- 対象: `ScheduleSync.py` / `Calender/Calender.py` の `GoogleCalender` パーサー
- 結論: **RRULE(繰り返し)を持つ予定は、実質的に一つも展開・同期されていない。** 単発予定は正常に動作している。

## 調査方法

1. `Chrome/GoogleCalender.py` の `GoogleCalender` クラスを使い、サイボウズ側には触れずにGoogleカレンダーの
   一括エクスポート(`get_calender()`)だけを実行し、実際の `.ics` を取得した(自動化用Chromeプロファイルが
   初回だったため、手動でのGoogleログインを一度実施)。
2. 取得できたカレンダーは以下7件(`music_room`等の個別取得カレンダーは、`Chrome/status.binaryfile` に
   現在`extra_calendar_*`の登録が無く未取得。別途調査が必要):
   - `Work_jagaimo13@gmail.com.ics`(4156件のVEVENT、うち132件がRRULE付き)
   - `Lab_maedalab17@gmail.com.ics`(308件、うち17件がRRULE付き)
   - `Research_...ics`(112件、うち4件)
   - `Hidden_...ics`(27件、うち5件)
   - `Personal_...ics`(434件、うち1件)
   - `Share_...ics`(43件、うち2件)
   - `Office hour_...ics`(356件、RRULE付きは0件)
3. 取得した `.ics` は `./data/GoogleCalender_backup/` にコピーを保持した上で(パーサーが読み込み後に
   元ファイルを`os.remove`するため)、実際に `Calender.Calender.GoogleCalender(...)` へ通して挙動を確認。
4. 疑わしい箇所(`Calender/Calender.py` 137〜152行目)に一時的にデバッグ出力を追加して実データで検証し、
   確認後に元に戻した(`git diff` で差分が残っていないことを確認済み)。

## 実データの内訳(FREQ・DTSTART形式)

| カレンダー | RRULE付きVEVENT数 | FREQ内訳 | DTSTART形式内訳 |
|---|---|---|---|
| Work | 132 | WEEKLY:130 / MONTHLY:2 | TZID:126 / VALUE=DATE(終日):6 |
| Lab | 17 | WEEKLY:15 / MONTHLY:2 | TZID:17 |
| Research | 4 | WEEKLY:3 / DAILY:1 | TZID:4 |
| Hidden | 5 | WEEKLY:5 | TZID:5 |
| Personal | 1 | YEARLY:1 | VALUE=DATE:1 |
| Share | 2 | YEARLY:2 | VALUE=DATE:2 |
| Office hour | 0 | - | - |

**重要な事実**: TZID形式のRRULE付き予定(152件全て)は、`DTSTART`・`DTEND`とも一貫して
`DTSTART;TZID=Asia/Tokyo:...` / `DTEND;TZID=Asia/Tokyo:...` の形式で、UTC(`...Z`)形式の
`DTSTART:` / `DTEND:` は一件も存在しなかった。

## 根本原因1(最大の原因): 変数の上書きによる判定ミス — `Calender/Calender.py` 136〜194行目

```python
136:  #開始時間の検索
137:  start_time  = self.extract(raw_schedule, 'DTSTART:')            # ← UTC形式で取得
138:  if start_time != "":
139:      sdaytime = datetime.strptime(start_time, '%Y%m%dT%H%M%SZ') + timedelta(hours = 9)
140:
141:  start_time = self.extract(raw_schedule, 'DTSTART;TZID=Asia/Tokyo:')  # ← ここで上書き！
142:  if start_time != "":
143:      sdaytime = datetime.strptime(start_time, '%Y%m%dT%H%M%S')
144:
145:  #修了時間の検索
146:  end_time    = self.extract(raw_schedule, 'DTEND:')               # ← UTC形式のまま(上書きなし)
147:  if end_time != "":
148:      edaytime = datetime.strptime(end_time, '%Y%m%dT%H%M%SZ') + timedelta(hours = 9)
149:
150:  end_time2   = self.extract(raw_schedule, 'DTEND;TZID=Asia/Tokyo:')  # ← 別変数に格納
151:  if end_time2 != "":
152:      edaytime = datetime.strptime(end_time2, '%Y%m%dT%H%M%S')
...
194:  if repeat_rule != '' and start_time != '' and end_time != '':   # ← ここが問題
```

141行目で `start_time` は「TZIDのDTSTARTがあるか」だけを表す変数に上書きされる。一方 `end_time` は
146行目のUTC形式(`DTEND:`)のままで、TZID形式は別変数 `end_time2` に入る。

つまり194行目の条件は「**TZID形式のDTSTARTがあり、かつUTC形式のDTEND(`end_time`)がある**」という、
実データ上ほぼ成立しない組み合わせを要求している。実際に取得した152件のTZID形式RRULE付き予定は、
DTEND側もすべてTZID形式なので `end_time`(UTC形式)は常に空文字になる。

### 実データでの直接検証(デバッグ出力による確認)

`Work_jagaimo13@gmail.com.ics` の132件のRRULE付きVEVENT全件に対し、194行目の条件に入る直前の
`start_time` / `end_time` の値を出力したところ:

```
DEBUG_RRULE 検出件数: 132
end_time_repr=''(空) の件数: 132 / 132   ← 全件が空
start_time_repr=''(空) の件数: 6 / 132    ← 終日繰り返し予定(VALUE=DATE)の6件
194行目の条件を通過した件数: 0 / 132       ← ゼロ
```

**132件全ての繰り返し予定で、194行目の分岐が一度も実行されていないことを実データで確認した。**
これにより、`FREQ=WEEKLY`の予定は(展開ロジックの実装自体は195行目以降に存在するにもかかわらず)
実質的に到達不能なコードになっている。

### 具体例: 現在進行中の繰り返し予定「SHR」

調査時点(2026-07-22)で実際に有効な繰り返し予定の例:

```
SUMMARY:SHR
DTSTART;TZID=Asia/Tokyo:20260407T084000
DTEND;TZID=Asia/Tokyo:20260407T084500
RRULE:FREQ=WEEKLY;UNTIL=20260728T145959Z;BYDAY=FR,MO,TH,TU,WE
EXDATE;TZID=Asia/Tokyo:20260504T084000
EXDATE;TZID=Asia/Tokyo:20260505T084000
EXDATE;TZID=Asia/Tokyo:20260506T084000
EXDATE;TZID=Asia/Tokyo:20260717T084000
```

平日毎日08:40〜08:45に発生する予定だが、実際にパーサーへ通したところ **この予定は1件も
`Event`として生成されなかった**(タイトル`SHR`で検索して0件)。つまり2026年4月〜7月の間、
平日ほぼ毎日発生しているはずのこの予定は一度もサイボウズへ同期されていない。

## 根本原因2: `FREQ=WEEKLY`以外の繰り返しが未対応

195行目以降の展開ロジックは `'FREQ=WEEKLY' in repeat_rule` の場合しか処理しない。根本原因1を
修正しても、以下は依然として同期されない:

- `MONTHLY`(例: Work「機械H科職員会」隔月、Lab「【5M】ミーティング」「【AS】ミーティング」月1回、
  `BYDAY=1MO`の「北陸地区大会」など) — 実データで計4件確認
- `DAILY`(例: Research「卒業研究（実験）」`FREQ=DAILY;UNTIL=20190829`) — 実データで1件確認
- `YEARLY`(例: Personal「久美子さん誕生日」、Share「記念日」「誕生日」) — 実データで3件確認

## 根本原因3: 繰り返しの終日予定(`DTSTART;VALUE=DATE` + RRULE)が未対応

169行目の単発予定ブロックは `if repeat_rule == '':` が条件のため、繰り返し予定はそもそもこの
ブロックに入らない。終日の繰り返し予定を展開するコードはコード全体に存在しない。実データでは
Work 6件、Personal 1件、Share 2件、合計9件のVALUE=DATE形式RRULE予定が該当し、いずれも1件も
同期されない。

## 補足: 例外予定(EXDATE / RECURRENCE-ID)の実態

CLAUDE.mdおよびコード(186〜191行目)には「繰り返しの例外予定」を`RECURRENCE-ID`で検出し、
元の予定を削除する処理があるが、実データを確認した限り**`RECURRENCE-ID`を持つVEVENTは1件も
存在しなかった**。実際の変更・削除された回はすべて、元のRRULE側に`EXDATE`が追加される形で
表現されていた(132件中107件がEXDATE付き)。`EXDATE`自体はどの分岐でも読み取られているだけで
展開に使われる場所は195行目以降の週次展開ロジック内のみであり、そのロジック自体が根本原因1により
到達不能なため、EXDATEの実装が正しいかどうかは現時点では実データで検証できていない。

## 影響範囲のまとめ

| 分類 | 該当件数(7カレンダー合計) | 現状 |
|---|---|---|
| FREQ=WEEKLYの繰り返し(TZID形式) | 152件 | **0件が同期される(根本原因1)** |
| FREQ=MONTHLY | 4件 | 根本原因1修正後も0件(根本原因2) |
| FREQ=DAILY | 1件 | 同上 |
| FREQ=YEARLY | 3件 | 同上 |
| 終日の繰り返し(VALUE=DATE) | 9件 | 根本原因1・2修正後も0件(根本原因3) |

これらの繰り返し予定シリーズ(1シリーズが数十件の個別予定に展開されるものも多い。例: Work
「材料力学Ⅱ」は約50回相当)は、現在サイボウズに一切入力されていない。逆に単発予定(`repeat_rule == ''`)
は正常に動作しているため、これまでの同期は「単発予定だけが同期され続けていた」状態だったと考えられる。

## 今回のスコープと次のステップ(所感、未着手)

今回は調査・原因確認のみで、コード修正は行っていない。修正時の参考:

- 根本原因1: `start_time`/`end_time`を上書きせず、TZID形式・UTC形式それぞれ専用の変数を使い、
  「どちらかの形式でDTSTART/DTENDが両方取れていれば繰り返し扱いにする」よう判定を直す。
- 根本原因2: `FREQ=WEEKLY`専用ロジックを一般化するか、`DAILY`/`MONTHLY`/`YEARLY`ごとに展開処理を追加する。
  `python-dateutil`の`rrule`モジュールを使えば自前のBYDAY/BYMONTHDAY計算を大幅に削減できる可能性がある。
- 根本原因3: 終日予定の繰り返し展開を単発の終日分岐(173〜179行目)とは別に実装する必要がある。

## 再現・追加調査のための資材

- ダウンロード済みの実データ(7カレンダー分の `.ics`)を `./data/GoogleCalender_backup/` に保持済み
  (本来のパーサーは読み込み後に削除するため、これは削除されない別コピー)。
- `music_room` を含む「個別取得(`get_extra_calendars`)」カレンダーは、現在の `Chrome/status.binaryfile`
  に登録が見当たらず今回取得できていない。CLAUDE.mdに記載の`music_room`の繰り返し予定への影響は
  別途登録・調査が必要。
