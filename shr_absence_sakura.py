"""SHR の欠席者に「SHRへの出席について【M/D（曜）】」をさくら連絡網で送る準備をする。

    pixi run python shr_absence_sakura.py            # 今日の分
    pixi run python shr_absence_sakura.py 2026-10-26 # 日付指定

1. SHR.xlsx の「点呼簿」シートから対象日の不在者を読む
2. さくら連絡網で直近に送信済みの「SHRへの出席について【…】」をコピー
3. 件名の日付を書き換え、宛先を「個人から選ぶ」→ 機械工学科３年 から不在者に差し替え
4. 宛先ページの「次へ」まで進めて止まる。**送信ボタンはユーザーが押す。**

氏名は個人情報なので、画面にもログにも出さない(件数と出席番号だけ出す)。
SHR.xlsx は数式の計算結果(キャッシュ値)を読むため、Excel で開いて保存してから実行すること。

TODO(docs/backlog_garoon.md の4): Garoon の「学生欠席等連絡」カレンダーに
欠席連絡がある学生を宛先から除外する。
"""

import argparse
import datetime
import os
import sys

import openpyxl

from Chrome.Sakura import Sakura

EXCEL_PATH = os.path.join(
    os.path.expanduser('~'),
    'OneDrive - 独立行政法人 国立高等専門学校機構', 'Work', '講義', '3ME_担任', '2026_3ME', 'SHR.xlsx')
SHEET = '点呼簿'
#点呼簿シートの行位置(2026-10 実ファイルで確認)。199行目が日付(=B2 等)、
#200〜245行目がその日の不在者「出席番号_苗字　名前」(不在でなければ空文字)。
DATE_ROW = 199
NAME_ROWS = range(200, 246)

AFFILIATION = '機械工学科３年'
SUBJECT_PREFIX = 'SHRへの出席について'
WEEKDAYS = '月火水木金土日'

USER_DATA_PATH = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Google', 'Chrome', 'AutoSyncData')


def read_absentees(path, date):
    """対象日の不在者を [(出席番号, 氏名), ...] で返す。日付列が無ければ None。"""
    ws = openpyxl.load_workbook(path, data_only=True, read_only=False)[SHEET]
    col = None
    for cell in ws[DATE_ROW]:
        value = cell.value
        if isinstance(value, datetime.datetime):
            value = value.date()
        if value == date:
            col = cell.column
            break
    if col is None:
        return None

    result = []
    for row in NAME_ROWS:
        value = ws.cell(row, col).value
        if isinstance(value, str) and '_' in value:
            number, name = value.split('_', 1)
            result.append((number.strip(), name.strip()))
    return result


def make_subject(date):
    return f'{SUBJECT_PREFIX}【{date.month}/{date.day}（{WEEKDAYS[date.weekday()]}）】'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('date', nargs='?', help='対象日 YYYY-MM-DD(省略時は今日)')
    parser.add_argument('--excel', default=EXCEL_PATH)
    parser.add_argument('--debugger-address', help='起動済みChromeに接続する(例 127.0.0.1:9333)')
    args = parser.parse_args()

    date = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    subject = make_subject(date)
    print(f"対象日: {date}  件名: {subject}")

    absentees = read_absentees(args.excel, date)
    if absentees is None:
        sys.exit(f"点呼簿の{DATE_ROW}行目に {date} がありません。"
                 "SHR.xlsx を Excel で開いて保存(再計算)してから実行してください。")
    print(f"不在者: {len(absentees)} 名")
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
    unmatched = sakura.set_recipients([name for _, name in absentees], AFFILIATION)
    print(f"宛先: {len(absentees) - len(unmatched)} 名を追加")
    if unmatched:
        numbers = ', '.join(absentees[i][0] for i in unmatched)
        print(f"警告: さくら連絡網で見つからなかった学生 {len(unmatched)} 名(出席番号 {numbers})。手動で追加してください。")

    for text in sakura.go_send_detail():
        print("  ", text)
    print("送信前の確認画面まで進めました。内容を確認して、ブラウザで送信してください。")
    input("送信が済んだら Enter を押してください(ブラウザを閉じて終了します)...")


if __name__ == '__main__':
    main()
