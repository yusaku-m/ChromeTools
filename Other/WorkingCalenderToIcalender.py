"""変形労働カレンダー(xlsx) → Googleカレンダー「Office hour」用のics生成。

半期ごとに配布される変形労働カレンダーのxlsx(教員修正用シート)から勤務時間を
読み取り、Googleカレンダーへインポートできるicsを書き出す。

旧実装3本(Other/WorkingCalenderToIcalender.py, Other/WorkingCalenderToICAL.py,
リポジトリ直下の「変形労働カレンダーical化.py」)を統合したもの。旧2本は固定
ファイル名のcsv(calender.csv / WorkingCalender.csv)を前提にしていたが、現在の
運用ではxlsxが直接配布されるためxlsx読み込みに一本化した。
"""
import glob
import os
import re
from datetime import datetime, timezone

import pandas as pd
from icalendar import Calendar, Event

SHEET_NAME = '教員修正用'
# Googleカレンダー上の実際のカレンダー名。インポート先の選択を表示テキストで
# 引くため、Google側の表記(小文字のh)と厳密に一致させる必要がある。
CALENDAR_NAME = 'Office hour'
# UIDのドメイン部。実在ドメインである必要はないがRFC5545上は一意であればよい。
UID_DOMAIN = 'officehour.chrometools'
REIWA_EPOCH = 2018  # 令和1年 = 西暦2019年

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
# ScheduleSync.pyと同じ自動化専用Chromeプロファイル(メインのChromeを閉じなくてよい)
CHROME_USER_DATA_PATH = "C:/Users/Yusaku/AppData/Local/Google/Chrome/AutoSyncData/"


def find_source_xlsx():
    """変形労働カレンダーのxlsxを1つ探す。
    ファイル名には年度・上期/下期・修正状況等が含まれ実行の度に変わる
    (例:令和8年度変形労働カレンダー（高松キャンパス教員）下半期マスター_ME前田 ★修正あり.xlsx)
    ため、固定ファイル名では拾えない。

    このスクリプトはOther/配下にあるが、xlsxはリポジトリ直下に置かれる運用のため、
    リポジトリ直下とスクリプトと同じディレクトリの両方を探す。"""
    candidates = []
    for directory in (REPO_ROOT, SCRIPT_DIR):
        candidates.extend(glob.glob(os.path.join(directory, '*変形労働カレンダー*.xlsx')))
    # 同一ディレクトリを2回見る構成ではないが、念のため重複を除く
    candidates = sorted(set(os.path.normpath(p) for p in candidates))
    if not candidates:
        raise FileNotFoundError(
            f'変形労働カレンダーのxlsxが見つかりません（*変形労働カレンダー*.xlsx）。'
            f'探索先: {REPO_ROOT}, {SCRIPT_DIR}')
    if len(candidates) > 1:
        raise RuntimeError(f'変形労働カレンダーのxlsxが複数見つかりました。1つに絞ってください: {candidates}')
    return candidates[0]


def fiscal_year_from_filename(path):
    """ファイル名の「令和N年度」から4月始まりの西暦年度を求める。"""
    m = re.search(r'令和(\d+)年度', os.path.basename(path))
    if not m:
        raise ValueError(f'ファイル名から年度(令和N年度)を読み取れません: {path}')
    return int(m.group(1)) + REIWA_EPOCH


def get_working_calender(source_path):
    """変形労働カレンダーのxlsxの「教員修正用」シートから勤務予定を取得する。
    シートは4月始まり6ヶ月ずつ2列組で month*4(+2) 列目から4列(日,時間数,?,時刻範囲)が
    並ぶレイアウト固定。時刻範囲(4列目)に'～'を含む行のみ、時刻の指定がある勤務日として扱う
    (半期毎に片方の期間分しか時刻が入力されないため、もう片方は自然に除外される)。"""
    print('変形労働カレンダーを読み込み中:', os.path.basename(source_path))
    fiscal_year = fiscal_year_from_filename(source_path)

    df = pd.read_excel(source_path, sheet_name=SHEET_NAME, header=None)
    data = df.to_numpy()[4:40, 1:].astype('unicode')

    working_times = []
    for month in range(12):
        offset = 0 if month < 6 else 2
        start = month * 4 + offset
        end = start + 4
        month_raw = data[:, start:end]
        act_month = (month + 3) % 12 + 1  # 実際の月に補正
        year = fiscal_year + 1 if act_month <= 3 else fiscal_year

        for day in range(month_raw.shape[0]):
            working_time = month_raw[day][3]
            if '～' in working_time:
                act_day = int(month_raw[day][0])
                working_times.append((year, act_month, act_day, working_time))

    print(f'{len(working_times)}件の勤務予定を読み取りました。')
    return working_times


def event_uid(year, month, day):
    """日付から決まる固定のUID。

    勤務予定は1日1件なので、日付だけでUIDが一意に決まる。毎回同じUIDを振ることで、
    Googleカレンダーへ再インポートしたときに新規作成ではなく既存予定の更新として
    扱われることを狙う(=カレンダーを削除して作り直す運用を不要にする)。"""
    return f'officehour-{year:04d}{month:02d}{day:02d}@{UID_DOMAIN}'


def workcalender_to_ical(working_times, output_path):
    cal = Calendar()
    cal.add('prodid', '-//ChromeTools//OfficeHour//JP')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', CALENDAR_NAME)
    cal.add('x-wr-timezone', 'Asia/Tokyo')

    dtstamp = datetime.now(timezone.utc)
    # 同一UIDの予定を「より新しい版」として受け入れてもらうためのシーケンス番号。
    # RFC5545ではSEQUENCEが大きいほど新しい版とみなされるので、生成時刻(分)から
    # 単調増加する値を作る。
    sequence = int(dtstamp.timestamp() // 60)

    for year, month, day, working_time in working_times:
        start_h, start_m = (int(x) for x in working_time.split('～')[0].split(':'))
        end_h, end_m = (int(x) for x in working_time.split('～')[1].split(':'))

        event = Event()
        event.add('uid', event_uid(year, month, day))
        event.add('dtstamp', dtstamp)
        event.add('sequence', sequence)
        event.add('summary', '勤務')
        # 時刻はタイムゾーンを付けないフローティング時刻のまま書く(X-WR-TIMEZONEで
        # Asia/Tokyoを宣言済み)。旧実装から変えていない、実運用で通っている形式。
        event.add('dtstart', datetime(year, month, day, start_h, start_m))
        event.add('dtend', datetime(year, month, day, end_h, end_m))
        cal.add_component(event)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(cal.to_ical())
    print(f'{output_path} に書き出しました。')
    return output_path


def push_to_google(ics_path):
    """生成したicsをGoogleカレンダーの「Office hour」へ取り込む。

    UIDが日付固定なので、同じ日の予定は重複せず上書きされる(実カレンダーで確認済み)。
    ただし前回は勤務日で今回は週休日になった日の予定は、icsから消えるだけでは
    Google側から消えないので手動で削除する必要がある。"""
    import sys

    # Browserはstatus.binaryfileとdataディレクトリを相対パスで参照するため、
    # 実行ディレクトリをリポジトリ直下に揃える
    os.chdir(REPO_ROOT)
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    from Chrome.GoogleCalender import GoogleCalender

    chrome = GoogleCalender(CHROME_USER_DATA_PATH)
    try:
        chrome.import_ics(ics_path, CALENDAR_NAME)
    finally:
        chrome.close()


if __name__ == "__main__":
    source_path = find_source_xlsx()
    working_times = get_working_calender(source_path)
    ics_path = workcalender_to_ical(working_times, os.path.join(REPO_ROOT, 'data', 'Office_Hour.ics'))

    answer = input(f'このicsをGoogleカレンダー「{CALENDAR_NAME}」へ取り込みますか? [y/N]: ')
    if answer.strip().lower() in ('y', 'yes'):
        push_to_google(ics_path)
    else:
        print('icsの生成のみで終了しました。')
