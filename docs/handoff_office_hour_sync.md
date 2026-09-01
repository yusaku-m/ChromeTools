# 引継ぎ: 変形労働カレンダー → Google Calendar 自動同期

## 目的
半期ごとに手動でやっている以下の作業を自動化する。
1. 変形労働カレンダーのxlsx（教員修正用シート）から勤務時間を抽出してicsを作る
2. Googleカレンダーの既存「Office Hour」カレンダーを削除して作り直す
3. 新しいicsをその「Office Hour」カレンダーへインポートする

## 完了済み（1のみ）
`変形労働カレンダーical化.py` を修正済み。
- 旧実装は固定ファイル名`calender.csv`を読む前提だったが、現在の運用ではリポジトリ直下に
  `令和8年度変形労働カレンダー（高松キャンパス教員）下半期マスター_ME前田 ★修正あり.xlsx`
  のような、年度・上期/下期・修正状況で毎回名前が変わるxlsxが置かれる。
  `find_source_xlsx()`が`*変形労働カレンダー*.xlsx`をglobして1件に絞る（0件/複数件はエラー）。
- 年度はファイル名の「令和N年度」から`fiscal_year_from_filename()`で西暦に変換して求める
  （`datetime.date.today()`基準の推測はやめた）。
- xlsxの「教員修正用」シートを`pandas.read_excel(..., header=None)`で読み、
  行4:40・列(month*4(+2)):(+4)のレイアウト（旧calender.csv版と同じ構造）で
  時刻範囲（'～'を含む）が入っている行だけを勤務予定として拾う。半期のうち
  データが入っていない側の期間は自然に0件になる（正常動作、要修正ではない）。
- ics生成は手書き文字列連結から`icalendar`ライブラリ（pixi.tomlに既存の依存）に置き換え。
- 実データで動作確認済み: 103件を正しく読み取り`data/Office_Hour.ics`を生成できた。
- 個人の勤務表xlsxがコミットされないよう`.gitignore`に`*.xlsx`を追加済み。

## 未着手（2, 3）— ここがブロック中
GoogleカレンダーでOffice Hourカレンダーを削除→再作成→ics再インポートする部分は未実装。

ユーザーとの合意事項:
- 「削除」は個々の予定を検索して1件ずつ消すのではなく、**Office Hourカレンダー自体を削除して
  同名で作り直す**方式でよい（Google Calendarには予定の一括削除UIが無いため、既存の運用も
  カレンダーごと作り直している）。
- 実装前に、実際のGoogleカレンダーの設定画面をClaude in Chrome拡張で（閲覧のみ、削除や作成等の
  実操作はせず）確認し、正確なUI構造を把握してから自動化コードを書く方針で合意済み。
  Google CalendarはSPAでクラス名等が不安定なため、憶測でセレクタを書くのは避けたい。

作業が止まっていた理由: このセッションではClaude in Chrome拡張がPCに未接続
（`tabs_context_mcp`が「Browser extension is not connected」を返す）だったため、
実画面の確認ができていない。拡張のインストール/起動待ちの状態で中断。

### 次にやること
1. Claude in Chrome拡張を接続した状態で、`https://calendar.google.com/calendar/u/0/r/settings`
   から以下を閲覧のみで確認する:
   - 左側の「マイカレンダー」一覧で「Office Hour」を選んだときの設定ページ（削除ボタンの位置・
     確認ダイアログの構造）
   - 「+ 他のカレンダーを追加」→「新しいカレンダーを作成」で名前を指定して作る際のフォーム
   - 設定内「インポート/エクスポート」ページのインポートフォーム（ファイル選択input・
     インポート先カレンダーのプルダウン・インポートボタン）
2. 確認したセレクタを使って`Chrome/GoogleCalender.py`（クラス`GoogleCalender(Browser)`）に
   削除→作成→インポートをまとめたメソッドを追加する。実装は`Chrome/Browser.py`の
   `patient_get`/`safe_click`/`wait_for_manual_step`の流儀に合わせること
   （Windows Hello等の手動待ちが挟まる可能性があるため）。
3. `変形労働カレンダーical化.py`の`if __name__ == "__main__":`末尾で、ics生成後に
   上記メソッドを呼び出すように結線する（現状はics生成のみで止まっている）。
4. カレンダー削除は取り消せない操作なので、初回実行はユーザー立ち会いのもとで確認しながら
   行うこと。

## 関連ファイル
- `変形労働カレンダーical化.py` — 今回修正したエントリスクリプト
- `Chrome/GoogleCalender.py` — Googleカレンダー操作クラス（削除/作成/インポートを追加する場所）
- `Chrome/Browser.py` — `patient_get`/`safe_click`/`wait_for_manual_step`等の共通部品
- `Chrome/status.binaryfile` — `googleID`等の永続設定
