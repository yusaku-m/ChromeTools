"""一部の授業だけ欠課した学生に、学務係への連絡を促すさくら連絡網を1人ずつ送る準備をする。

    pixi run absence             # 前回の授業日の分(行事予定から求める)
    pixi run absence 1026        # 日付指定(MMDD、年は今年。YYYY-MM-DD も可)
    pixi run absence --inspect   # 出力ファイルの構造(見出し行と件数)だけ表示して終わる
    pixi run absence --show      # KOSEN WEB の取得もブラウザ画面を出して行う

KOSEN WEB からの取得はヘッドレスで行う。ログインしていなければ(パスワードの自動入力も無ければ)
画面ありで起動し直してログインを待つ。さくら連絡網は送信確認を目で見るので常に画面ありで開く。

1. 行事予定(data/*行事予定*.xlsx)から前回の授業日を求める。対応済みの日なら終了
2. KOSEN WEB「日別出欠の閲覧（期間指定）」でその日の 3年・機械工学科 を出力
3. 全時限欠課(=丸一日欠席。SHR 側で連絡済み)と欠課なしを除き、残りの学生ごとに欠課した時限を集める
4. 欠課の内容が同じ学生ごとに(まったく同じなら1通に複数宛先で)さくら連絡網のメッセージを新規作成し
   (受信者氏名を差し込む)、送信確認画面で止まる。**送信ボタンはユーザーが押す。** Enter で次へ進む。

送信したかどうかは日付・出席番号ごとに OneDrive の Work/講義/そのた科目/class_absence_sent.csv に
記録する(SENT_LOG。どの PC から実行しても共有される)。送信済みの学生はやり直しても飛ばし、
最後まで終えた日には「完了」の行を書いて、次からその日は何もしない。氏名は書かない。

出力ファイルと氏名は個人情報なので、画面にもログにも出さない(件数・出席番号・時限だけ出す)。
出力ファイルは一時フォルダに保存し、読み終えたらすぐ消す。

TODO(docs/backlog_garoon.md の4): Garoon の「学生欠席等連絡」に欠席連絡がある学生を除外する。
"""

import argparse
import csv
import datetime
import glob
import os
import re
import shutil
import sys
import tempfile
import unicodedata

import openpyxl

from Chrome.KosenWeb import KosenWeb, LoginRequired
from Chrome.Sakura import Sakura
from paths import onedrive_dir
from sakura_names import ask_aliases, to_sakura_names

GRADE = '3年'
DEPARTMENT = '機械工学科'
AFFILIATION = '機械工学科３年'
SUBJECT_PREFIX = '授業の欠席について'
WEEKDAYS = '月火水木金土日'
BODY = """機械工学科３年生担任の前田です。

{date}の{lessons}を欠席されていたようですが，学務係へは連絡が無かったようです。
欠席がお分かりの場合は，必ず学務係への事前連絡をお願いいたします。
以上よろしくお願いいたします。"""

#出力ファイルの列位置(ユーザー指定)。B列=氏名、I列以降=その日の各授業(1行目=時限、2行目=授業名)
NAME_COL = 1
FIRST_LESSON_COL = 8
LESSON_NAME_ROW = 1
ABSENT_MARK = '欠'
#授業が無かったことを表す値。丸一日欠席の判定でその時限を数えない(空欄は出席)
NO_CLASS_MARKS = {'休講'}

SCHEDULE_GLOB = os.path.join('data', '*行事予定*.xlsx')
SENT_LOG = ('Work', '講義', 'そのた科目', 'class_absence_sent.csv')
SENT_LOG_HEADER = ['日付', '出席番号', '欠課', '結果', '記録日時']
RESULT_SENT, RESULT_SKIPPED, RESULT_DONE = '送信', '送らず', '完了'
USER_DATA_PATH = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Google', 'Chrome', 'AutoSyncData')


# ----------------------------------------------------------------------
# 行事予定
# ----------------------------------------------------------------------
def load_class_days(path):
    """行事予定 xlsx から高松キャンパスの授業日の集合を返す。

    シートは月ごとのブロックが横に並ぶ(2026-10 の「令和8年度行事予定案15」で確認)。
    2行目に「4月」等の月見出しがありその列が「曜」、3行目でその右にある「高松」列の
    さらに右隣が授業週の番号。授業日なら数字、試験・行事日は「〇」、休日は空欄。
    日付 d の行は d+3 行目。
    """
    m = re.search(r'令和(\d+)年度', os.path.basename(path))
    if not m:
        raise ValueError(f"ファイル名から年度を読めません: {path}")
    nendo = 2018 + int(m.group(1))
    ws = openpyxl.load_workbook(path, data_only=True, read_only=True).worksheets[0]
    rows = [list(r) for r in ws.iter_rows(min_row=1, max_row=34, values_only=True)]

    days = set()
    for col, header in enumerate(rows[1]):
        mm = re.fullmatch(r'(\d+)月', str(header or '').strip())
        if not mm:
            continue
        month = int(mm.group(1))
        year = nendo if month >= 4 else nendo + 1
        takamatsu = [c for c in range(col + 1, col + 6) if rows[2][c] == '高松']
        if len(takamatsu) != 1:
            raise ValueError(f"{month}月の「高松」列が見つかりません")
        week_col = takamatsu[0] + 1
        for d in range(1, 32):
            try:
                date = datetime.date(year, month, d)
            except ValueError:
                break
            row = rows[d + 2]
            if row[col] != WEEKDAYS[date.weekday()]:
                raise ValueError(f"行事予定の {date} の曜日が合いません({row[col]})。シートの形が変わった可能性があります")
            if isinstance(row[week_col], (int, float)):
                days.add(date)
    return days


def previous_class_day(today, class_days):
    earlier = [d for d in class_days if d < today]
    if not earlier:
        raise ValueError(f"{today} より前の授業日が行事予定にありません")
    return max(earlier)


def find_schedule_file():
    files = glob.glob(SCHEDULE_GLOB)
    if not files:
        sys.exit(f"行事予定が見つかりません({SCHEDULE_GLOB})")
    return max(files, key=os.path.getmtime)


# ----------------------------------------------------------------------
# 送信記録(OneDrive。日付・出席番号ごと)
# ----------------------------------------------------------------------
def sent_log_path():
    return onedrive_dir(*SENT_LOG)


def load_sent_log(date):
    """その日の記録を {出席番号: 結果} と「完了」の有無で返す。後の行ほど新しい。"""
    results, done = {}, False
    try:
        with open(sent_log_path(), encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                if row['日付'] != date.isoformat():
                    continue
                if row['結果'] == RESULT_DONE:
                    done = True
                else:
                    results[row['出席番号']] = row['結果']
    except FileNotFoundError:
        pass
    return results, done


def append_sent_log(date, number, lessons_text, result):
    """1行追記する。Excel で開いているとロックされて書けないので、閉じてもらって再試行する。"""
    path = sent_log_path()
    row = [date.isoformat(), number, lessons_text, result, datetime.datetime.now().isoformat(timespec='seconds')]
    while True:
        try:
            new = not os.path.exists(path)
            #Excel で文字化けしないよう BOM 付き UTF-8(先頭に書くときだけ BOM が付く)
            with open(path, 'a', encoding='utf-8-sig' if new else 'utf-8', newline='') as f:
                writer = csv.writer(f)
                if new:
                    writer.writerow(SENT_LOG_HEADER)
                writer.writerow(row)
            return
        except PermissionError:
            input(f"  送信記録に書き込めません(Excel で開いていれば閉じてください): {path}\n  Enter で再試行: ")


# ----------------------------------------------------------------------
# KOSEN WEB の出力ファイル(個人情報。中身は表示しない)
# ----------------------------------------------------------------------
def read_table(path):
    """CSV/xlsx を文字列の2次元リストで読む。"""
    if path.lower().endswith(('.xlsx', '.xlsm')):
        #read_only=True だとファイルに書かれた <dimension> の範囲しか読まない。KOSEN WEB の出力は
        #それが実データより狭く、右側の列が欠けるので通常モードで読む(ファイルは小さい)
        ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
        rows = [['' if v is None else str(v) for v in row] for row in ws.iter_rows(values_only=True)]
        #結合セルは左上にしか値が無いので、範囲全体に広げる(同じ時限に複数授業があると時限の見出しが結合される)
        for merged in ws.merged_cells.ranges:
            value = rows[merged.min_row - 1][merged.min_col - 1]
            for r in range(merged.min_row - 1, merged.max_row):
                for c in range(merged.min_col - 1, merged.max_col):
                    rows[r][c] = value
        return rows
    for encoding in ('utf-8-sig', 'cp932'):
        try:
            with open(path, encoding=encoding, newline='') as f:
                return list(csv.reader(f))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"文字コードを判別できません: {os.path.basename(path)}")


def _cell(row, col):
    return unicodedata.normalize('NFKC', row[col]).strip() if col < len(row) and row[col] else ''


def lesson_columns(rows):
    """[(列, 時限, 授業名), ...]。授業名(2行目)が空の列は含めない。

    時限は1行目の見出しの数値。同じ時限に複数の授業がある(選択科目等)ので、列の位置からは決めない。
    見出しに数値が無い列があれば、推測せずに例外にする。
    """
    result = []
    col = FIRST_LESSON_COL
    #時限が重複しうるので、列は「最大8コマ」ではなく見出しが続く限り読む
    while col < max(len(rows[0]), len(rows[LESSON_NAME_ROW])):
        name = _cell(rows[LESSON_NAME_ROW], col)
        header = _cell(rows[0], col)
        if not name and not header:
            break
        if name:
            period = _period(header)
            if period is None:
                raise ValueError(f"{_col_letter(col)}列の1行目から時限を読めません({header!r})。--inspect で構造を確認してください")
            result.append((col, period, name))
        col += 1
    return result


def _period(header):
    """見出しから時限を返す。KOSEN WEB の見出しは「2026/10/23 1」(日付 時限)。
    先頭の日付を除いたうえで「N限」「N時限」か数値だけのときに限り時限とみなし、それ以外は None。"""
    header = re.sub(r'^\d{4}[/-]\d{1,2}[/-]\d{1,2}(?:\s*\(.\))?\s*', '', header)
    m = re.search(r'(\d+)\s*時?限', header)
    if not m:
        m = re.fullmatch(r'(\d+)(?:\.0)?', header)
    if not m or not 1 <= int(m.group(1)) <= 10:
        return None
    return int(m.group(1))


def _col_letter(col):
    letters = ''
    col += 1
    while col:
        col, r = divmod(col - 1, 26)
        letters = chr(ord('A') + r) + letters
    return letters


def find_targets(rows, lessons):
    """一部の時限だけ欠課した学生を [(行番号, 出席番号らしき値, 氏名, [(時限, 授業名), ...]), ...] で返す。
    あわせて (全時限欠課の人数, 欠課なしの人数) を返す。"""
    targets, all_absent, none_absent = [], 0, 0
    for r, row in enumerate(rows[LESSON_NAME_ROW + 1:], start=LESSON_NAME_ROW + 2):
        name = _cell(row, NAME_COL)
        if not name:
            continue
        absent = sorted({(period, lesson) for col, period, lesson in lessons if _cell(row, col) == ABSENT_MARK})
        if not absent:
            none_absent += 1
        #休講の列には欠が付かないので、休講以外の列がすべて欠なら丸一日欠席とみなす
        elif all(_cell(row, col) == ABSENT_MARK for col, _, _ in lessons
                 if _cell(row, col) not in NO_CLASS_MARKS):
            all_absent += 1
        else:
            targets.append((r, _cell(row, 0), name, absent))
    return targets, all_absent, none_absent


def inspect(rows, lessons):
    """出力ファイルの構造だけを表示する(氏名や個々の学生の値は出さない)。"""
    print(f"行数: {len(rows)} / 列数: {max((len(r) for r in rows), default=0)}")
    for i in range(min(2, len(rows))):
        print(f"{i + 1}行目: {rows[i]}")
    print("授業の列:", [(_col_letter(c), p, n) for c, p, n in lessons])
    marks = {}
    for row in rows[LESSON_NAME_ROW + 1:]:
        if _cell(row, NAME_COL):
            for col, _, _ in lessons:
                v = _cell(row, col)
                marks[v] = marks.get(v, 0) + 1
    print("授業の列に現れる値と件数:", marks)


def format_lessons(absent):
    """[(1,'A'),(2,'A'),(4,'B')] → '1・2限 A，4限 B'。同じ授業の連続した時限はまとめる。"""
    groups = []
    for period, lesson in absent:
        if groups and groups[-1][1] == lesson and groups[-1][0][-1] == period - 1:
            groups[-1][0].append(period)
        else:
            groups.append(([period], lesson))
    return '，'.join('・'.join(map(str, periods)) + '限 ' + lesson for periods, lesson in groups)


def format_date(date):
    return f'{date.month}/{date.day}({WEEKDAYS[date.weekday()]})'


def parse_date(text):
    """'1026' (MMDD、年は今年) または '2026-10-26' を date にする。"""
    try:
        if len(text) == 4 and text.isdigit():
            return datetime.date(datetime.date.today().year, int(text[:2]), int(text[2:]))
        return datetime.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"日付は MMDD か YYYY-MM-DD で指定してください: {text}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('date', nargs='?', type=parse_date,
                        help='対象日 MMDD(今年) または YYYY-MM-DD。省略時は行事予定から求めた前回の授業日')
    parser.add_argument('--force', action='store_true',
                        help='完了済みの日でも実行し、「送らず」にした学生も聞き直す(送信済みの学生は常に飛ばす)')
    parser.add_argument('--inspect', action='store_true', help='出力ファイルの構造だけ表示して終わる')
    parser.add_argument('--list-days', action='store_true', help='行事予定から求めた授業日の一覧を表示して終わる')
    parser.add_argument('--show', action='store_true', help='KOSEN WEB の取得もヘッドレスにせず画面を出して行う')
    parser.add_argument('--debugger-address', help='起動済みChromeに接続する(例 127.0.0.1:9333)')
    args = parser.parse_args()

    if args.list_days:
        schedule = find_schedule_file()
        days = sorted(load_class_days(schedule))
        print(f"行事予定: {os.path.basename(schedule)}  授業日 {len(days)} 日")
        for month in sorted({(d.year, d.month) for d in days}):
            in_month = [d for d in days if (d.year, d.month) == month]
            print(f"{month[0]}/{month[1]:02d} ({len(in_month)}日): "
                  + ' '.join(f"{d.day}{WEEKDAYS[d.weekday()]}" for d in in_month))
        return

    date = args.date
    if date is None:
        schedule = find_schedule_file()
        date = previous_class_day(datetime.date.today(), load_class_days(schedule))
        print(f"行事予定: {os.path.basename(schedule)}")
    print(f"対象日: {date} ({WEEKDAYS[date.weekday()]})")
    sent, done = load_sent_log(date)
    if done and not (args.force or args.inspect):
        print("この日は対応済みです(やり直すときは --force)。")
        return

    kosen = KosenWeb(USER_DATA_PATH, debugger_address=args.debugger_address, headless=not args.show)
    download_dir = tempfile.mkdtemp(prefix='kosenweb_')
    try:
        try:
            path = kosen.download_daily_attendance(date, GRADE, DEPARTMENT, download_dir)
        except LoginRequired:
            print("KOSEN WEB にログインしていないので、ブラウザ画面を出して起動し直します。")
            kosen.driver.quit()
            kosen = KosenWeb(USER_DATA_PATH, debugger_address=args.debugger_address)
            path = kosen.download_daily_attendance(date, GRADE, DEPARTMENT, download_dir)
        rows = read_table(path)
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)

    if kosen.headless:
        #画面の無い Chrome はもう使わない(さくら連絡網は画面ありで開き直す)
        kosen.driver.quit()
    if args.inspect:
        try:
            lessons = lesson_columns(rows) if len(rows) > LESSON_NAME_ROW else []
        except ValueError as e:
            print(e)
            lessons = []
        inspect(rows, lessons)
        return
    lessons = lesson_columns(rows) if len(rows) > LESSON_NAME_ROW else []
    if not lessons:
        sys.exit("出力ファイルに授業の列がありません。--inspect で構造を確認してください。")
    print("時限:", ' / '.join(f"{p}限 {n}" for _, p, n in lessons))
    targets, all_absent, none_absent = find_targets(rows, lessons)
    print(f"授業 {len(lessons)} コマ / 全時限欠課 {all_absent} 名(除外) / 欠課なし {none_absent} 名(除外) / 対象 {len(targets)} 名")
    handled = {RESULT_SENT} if args.force else {RESULT_SENT, RESULT_SKIPPED}
    remaining = [t for t in targets if sent.get(t[1]) not in handled]
    if len(remaining) < len(targets):
        print(f"記録済みの {len(targets) - len(remaining)} 名を飛ばします(残り {len(remaining)} 名)。")
    if not remaining:
        append_sent_log(date, '', '', RESULT_DONE)
        print("送信対象がいないので終了します。")
        return

    if kosen.headless:
        #送信内容を目で確認するので、さくら連絡網は画面ありの Chrome で開く
        sakura = Sakura(USER_DATA_PATH)
    else:
        sakura = Sakura.share_driver(kosen)
        sakura.login()
    subject = f'{SUBJECT_PREFIX}【{date.month}/{date.day}（{WEEKDAYS[date.weekday()]}）】'
    #欠課の内容がまったく同じ学生は1通にまとめる(宛名は「受信者氏名を差し込む」で一人ずつ変わる)
    groups = {}
    for _, number, name, absent in remaining:
        groups.setdefault(format_lessons(absent), []).append((number, name))
    print(f"{len(remaining)} 名を {len(groups)} 通にまとめました。")

    sent_count = skipped = 0
    for i, (lessons_text, students) in enumerate(groups.items(), start=1):
        print(f"[{i}/{len(groups)}] 出席番号 {', '.join(n for n, _ in students)}: {lessons_text}")
        body = BODY.format(date=format_date(date), lessons=lessons_text)
        while True:
            sakura.new_message(subject, body)
            unmatched = set(sakura.set_recipients(to_sakura_names([name for _, name in students]), AFFILIATION))
            #照合できなかった学生の表示名を辞書に登録できたら、このメッセージを作り直す
            if not unmatched or not ask_aliases([students[j] for j in sorted(unmatched)]):
                break
        for j in sorted(unmatched):
            print(f"  出席番号 {students[j][0]} は宛先に入れていません。手動で対応してください。")
        skipped += len(unmatched)
        matched = [st for j, st in enumerate(students) if j not in unmatched]
        if not matched:
            continue
        if unmatched:
            print(f"  宛先: {len(matched)} 名(出席番号 {', '.join(n for n, _ in matched)})")
        for text in sakura.go_send_detail():
            print("  ", text)
        for text in sakura.set_insert_recipient_name():
            print("  ", text)
        print("  ブラウザで内容を確認して送信してください(送信の完了を検知して次へ進みます)。"
              "送らない場合は s / 中断は q: ", end='', flush=True)
        answer = sakura.wait_for_send()
        if answer == 'q':
            print("中断しました(この日は対応済みにしません)。")
            return
        result = RESULT_SENT if answer == 'sent' else RESULT_SKIPPED
        if result == RESULT_SENT:
            print("送信を確認しました。")
        for number, _ in matched:
            append_sent_log(date, number, lessons_text, result)
        if result == RESULT_SENT:
            sent_count += len(matched)
        else:
            skipped += len(matched)

    append_sent_log(date, '', '', RESULT_DONE)
    print(f"完了: {sent_count} 名に送信、{skipped} 名は送信せず。{date} を対応済みにしました。")


if __name__ == '__main__':
    main()
