"""SHR の欠席者に「SHRへの出席について【M/D（曜）】」をさくら連絡網で送る準備をする。

    pixi run shr             # 今日の分
    pixi run shr 1026        # 日付指定(MMDD、年は今年。YYYY-MM-DD も可)
    pixi run shr -x 3,15     # サイボウズで欠席連絡がある出席番号を宛先から除外

1. SHR.xlsx の「点呼簿」シートから対象日の不在者を読む
2. さくら連絡網で直近に送信済みの「SHRへの出席について【…】」をコピー
3. 件名の日付を書き換え、宛先を「個人から選ぶ」→ 機械工学科３年 から不在者に差し替え
4. 宛先ページの「次へ」まで進めて止まる。**送信ボタンはユーザーが押す。**
   送信完了の alert を検知して終了する(q で送らずに終了)。

氏名は個人情報なので、画面にもログにも出さない(件数と出席番号だけ出す)。
SHR.xlsx は数式の計算結果を読む。Excel で開いていればその現在値を、
開いていなければ保存時のキャッシュ値を読むので、閉じている場合は保存してから実行すること。

サイボウズに欠席連絡がある学生は -x で出席番号を渡して除外する。
TODO(docs/backlog_garoon.md の4): これを Garoon の「学生欠席等連絡」カレンダーから自動で引く。
"""

import argparse
import datetime
import os
import sys

import openpyxl

import absence_notice
from Chrome.Sakura import Sakura
from paths import onedrive_dir
from sakura_names import ask_aliases, to_sakura_names

#職場の OneDrive の場所は PC ごとに違う(開発PCはホーム直下、本番PCは D:\)ので paths で解決する
EXCEL_PATH = onedrive_dir('Work', '講義', '3ME_担任', '2026_3ME', 'SHR.xlsx')
SHEET = '点呼簿'
#点呼簿シートの行位置(2026-10 実ファイルで確認)。199行目が日付(=B2 等)、
#200〜245行目がその日の不在者「出席番号_苗字　名前」(不在でなければ空文字)。
DATE_ROW = 199
NAME_ROWS = range(200, 246)

AFFILIATION = '機械工学科３年'
SUBJECT_PREFIX = 'SHRへの出席について'
WEEKDAYS = '月火水木金土日'

USER_DATA_PATH = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Google', 'Chrome', 'AutoSyncData')


def _read_rows_file(path):
    """DATE_ROW〜NAME_ROWS の最終行を、行ごとの値のリストで返す(保存済みファイルのキャッシュ値)。"""
    ws = openpyxl.load_workbook(path, data_only=True, read_only=True)[SHEET]
    return [list(row) for row in ws.iter_rows(min_row=DATE_ROW, max_row=NAME_ROWS[-1], values_only=True)]


def _read_rows_excel(path):
    """Excel で開いている SHR.xlsx から同じ範囲を読む(計算済みの現在値)。

    OneDrive 上のブックを Excel で開いていると(自動保存時など)ファイルがロックされ、
    openpyxl では PermissionError になるため、その場合はこちらを使う。
    FullName は OneDrive の URL になることがあるので、ブック名で照合する。
    """
    import win32com.client
    try:
        excel = win32com.client.GetActiveObject('Excel.Application')
    except Exception:
        return None
    name = os.path.basename(path).lower()
    for wb in excel.Workbooks:
        if wb.Name.lower() == name:
            ws = wb.Worksheets(SHEET)
            last_col = ws.UsedRange.Column + ws.UsedRange.Columns.Count - 1
            values = ws.Range(ws.Cells(DATE_ROW, 1), ws.Cells(NAME_ROWS[-1], last_col)).Value
            return [list(row) for row in values]
    return None


def read_absentees(path, date):
    """対象日の不在者を [(出席番号, 氏名), ...] で返す。日付列が無ければ None。"""
    try:
        rows = _read_rows_file(path)
    except PermissionError:
        rows = _read_rows_excel(path)
        if rows is None:
            raise
        print("SHR.xlsx は Excel で開かれているため、Excel から直接読みました。")

    col = None
    for i, value in enumerate(rows[0]):
        if isinstance(value, datetime.datetime):
            value = value.date()
        if value == date:
            col = i
            break
    if col is None:
        return None

    result = []
    for row in NAME_ROWS:
        values = rows[row - DATE_ROW]
        value = values[col] if col < len(values) else None
        if isinstance(value, str) and '_' in value:
            number, name = value.split('_', 1)
            result.append((number.strip(), name.strip()))
    return result


def parse_date(text):
    """'1027' (MMDD、年は今年) または '2026-10-27' を date にする。"""
    try:
        if len(text) == 4 and text.isdigit():
            return datetime.date(datetime.date.today().year, int(text[:2]), int(text[2:]))
        return datetime.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"日付は MMDD か YYYY-MM-DD で指定してください: {text}")


def make_subject(date):
    return f'{SUBJECT_PREFIX}【{date.month}/{date.day}（{WEEKDAYS[date.weekday()]}）】'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('date', nargs='?', type=parse_date,
                        help='対象日 MMDD(今年) または YYYY-MM-DD。省略時は今日')
    absence_notice.add_argument(parser)
    parser.add_argument('--excel', default=EXCEL_PATH)
    parser.add_argument('--debugger-address', help='起動済みChromeに接続する(例 127.0.0.1:9333)')
    args = parser.parse_args()

    date = args.date or datetime.date.today()
    subject = make_subject(date)
    print(f"対象日: {date}  件名: {subject}")

    absentees = read_absentees(args.excel, date)
    if absentees is None:
        sys.exit(f"点呼簿の{DATE_ROW}行目に {date} がありません。"
                 "SHR.xlsx を Excel で開いて保存(再計算)してから実行してください。")
    print(f"不在者: {len(absentees)} 名")
    absentees, _ = absence_notice.split(absentees, absence_notice.excluded(args))
    if not absentees:
        print("送信対象がいないので終了します。")
        return

    sakura = Sakura(USER_DATA_PATH, debugger_address=args.debugger_address)

    pattern = '^' + SUBJECT_PREFIX + '【'
    sent = [m for m in sakura.list_messages(pattern) if m[2].startswith('送信済')]
    if not sent:
        sys.exit("コピー元になる送信済みの「SHRへの出席について【…】」が見つかりません。")
    print(f"コピー元: {sent[0][1]} (No.{sent[0][0]})")
    draft = sakura.copy_message(sent[0][0])
    print(f"下書きを作成: No.{draft}")

    sakura.edit_subject(draft, subject)
    unmatched = sakura.set_recipients(to_sakura_names([name for _, name in absentees]), AFFILIATION)
    print(f"宛先: {len(absentees) - len(unmatched)} 名を追加")
    if unmatched:
        print(f"警告: さくら連絡網で見つからなかった学生が {len(unmatched)} 名います。")
        #表示名を登録しておけば次回からは自動で入る。今回の分は手で追加してもらう
        ask_aliases([absentees[i] for i in unmatched])
        print("  上の学生は、今回はブラウザで宛先に手動で追加してください。")

    for text in sakura.go_send_detail():
        print("  ", text)
    print("送信前の確認画面まで進めました。内容を確認して、ブラウザで送信してください"
          "(送信の完了を検知して終了します)。送らずに終了するときは q: ", end='', flush=True)
    if sakura.wait_for_send(keys='q') == 'sent':
        print("送信を確認しました。")
    else:
        print("送信せずに終了します。")


if __name__ == '__main__':
    main()
