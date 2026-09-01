import glob
import os
import re
from datetime import datetime

import pandas as pd
from icalendar import Calendar, Event

SHEET_NAME = '教員修正用'
CALENDAR_NAME = 'Office Hour'
REIWA_EPOCH = 2018  # 令和1年 = 西暦2019年


def find_source_xlsx():
    """変形労働カレンダーのxlsxを1つ探す。
    ファイル名には年度・上期/下期・修正状況等が含まれ実行の度に変わる
    (例:令和8年度変形労働カレンダー（高松キャンパス教員）下半期マスター_ME前田 ★修正あり.xlsx)
    ため、固定ファイル名では拾えない。"""
    candidates = glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), '*変形労働カレンダー*.xlsx'))
    if not candidates:
        raise FileNotFoundError('変形労働カレンダーのxlsxが見つかりません（*変形労働カレンダー*.xlsx）。')
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


def workcalender_to_ical(working_times, output_path):
    cal = Calendar()
    cal.add('prodid', '-//ChromeTools//OfficeHour//JP')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', CALENDAR_NAME)
    cal.add('x-wr-timezone', 'Asia/Tokyo')

    for year, month, day, working_time in working_times:
        start_h, start_m = (int(x) for x in working_time.split('～')[0].split(':'))
        end_h, end_m = (int(x) for x in working_time.split('～')[1].split(':'))

        event = Event()
        event.add('summary', '勤務')
        event.add('dtstart', datetime(year, month, day, start_h, start_m))
        event.add('dtend', datetime(year, month, day, end_h, end_m))
        cal.add_component(event)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(cal.to_ical())
    print(f'{output_path} に書き出しました。')


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    source_path = find_source_xlsx()
    working_times = get_working_calender(source_path)
    workcalender_to_ical(working_times, os.path.join('data', 'Office_Hour.ics'))
