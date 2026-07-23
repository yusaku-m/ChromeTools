import time
from datetime import datetime, timedelta

from Chrome.GoogleCalender import GoogleCalender
from Chrome.Cyboze import Cyboze
from Calender import Calender

# 音楽練習室カレンダー由来の予定にのみ追加する参加者・施設(サイボウズ内部ID, 表示名)
# 「音楽練習室」はサイボウズ上では参加者ではなく施設として登録されているため、
# sUID(参加者)ではなくsFID(施設)側に追加する。
MUSIC_ROOM_EXTRA_PARTICIPANTS = [
    ('5575', '軽音楽部'),
    ('5994', '北村　大地'),
]
MUSIC_ROOM_EXTRA_FACILITIES = [
    ('7919', '音楽練習室'),
]
# 音楽練習室カレンダー由来の予定のうち、これらのタイトルは同期しない
# (個人の仮予約枠で、実際の練習予定と時間帯が重なり施設予約が衝突するため)
MUSIC_ROOM_SKIP_TITLES = ['北村', '前田']

# ファイル名(ics)にこれらのキーワードを含むカレンダーは同期対象から完全に除外する
# (例: Personal_xxxx@group.calendar.google.com.ics, Share_xxxx@group.calendar.google.com.ics)
EXCLUDED_CALENDAR_KEYWORDS = ['personal', 'share']

"""
Selenium のドライバ管理は自動化されました。
もし Chrome の起動に失敗する場合は、Chrome が最新バージョンであることを確認してください。
また、実行時に Chrome のウィンドウが開いているとプロファイルの競合で失敗することがあるため、
このスクリプトは実行時に既存の Chrome プロセスを終了させます。
"""
print("sync start")

while True:
    try:

        """グーグルカレンダーの取得"""
        # 自動化専用プロファイル（メインChromeを閉じなくてよい）
        # 初回のみ別ウィンドウでGoogleにログインが必要
        user_data_path = "C:/Users/Yusaku/AppData/Local/Google/Chrome/AutoSyncData/"
        chrome = GoogleCalender(user_data_path)
        chrome.set_id('jagaimo13')
        chrome.get_calender()
        # 一括エクスポート(exporticalzip)に含まれないカレンダー（他アカウント所有・
        # 編集権限のみ共有されているカレンダー等）を個別取得する
        chrome.get_extra_calendars()
        chrome.close()

        # 展開されたICSファイルをすべて自動検出して結合
        import os
        gcal_dir = './data/GoogleCalender'
        calender_list = sorted([f for f in os.listdir(gcal_dir) if f.endswith('.ics')])
        print(f"Found {len(calender_list)} calendars: {calender_list}")

        # 音楽練習室カレンダーは同期範囲(過去〜未来)を無制限にしたいので、
        # 他カレンダー分とは別に集計しておく
        gcal_other = []
        gcal_music_room = []
        for calender in calender_list:
            if any(keyword.lower() in calender.lower() for keyword in EXCLUDED_CALENDAR_KEYWORDS):
                print(f"  Skipping excluded calendar: {calender}")
                continue
            is_music_room = calender == 'music_room.ics'
            extra_participants = MUSIC_ROOM_EXTRA_PARTICIPANTS if is_music_room else None
            extra_facilities = MUSIC_ROOM_EXTRA_FACILITIES if is_music_room else None
            skip_titles = MUSIC_ROOM_SKIP_TITLES if is_music_room else None
            buf = Calender.GoogleCalender('gcal', calender, extra_participants=extra_participants, extra_facilities=extra_facilities, skip_allday=is_music_room, skip_titles=skip_titles)
            if is_music_room:
                gcal_music_room = buf if gcal_music_room == [] else buf.union(gcal_music_room)
            else:
                gcal_other = buf if gcal_other == [] else buf.union(gcal_other)
            print(calender)

        if gcal_other == []:
            gcal_other = Calender.Calender('gcal_other', [])
        if gcal_music_room == []:
            gcal_music_room = Calender.Calender('gcal_music_room', [])

        gcal = gcal_other.union(gcal_music_room)

        """サイボウズカレンダーに自動入力された予定の取得"""
        user_data_path = "C:/Users/Yusaku/AppData/Local/Google/Chrome/AutoSyncData/"
        cyboze = Cyboze(user_data_path)
        cyboze.set_id(name='前田　祐作',uid='5791',department='機械工学科',gid='2100')
        cyboze.login()
        cyboze.get_calender()

        ccal = Calender.CybozeCalender('ccal','./data/CybozeSchedule.csv')

        """予定を期間で絞り込み"""

        now = datetime.now()
        start = now-timedelta(days = 1)
        end =   now+timedelta(days = 365)

        gcal_filter = gcal.filtering_by_date(start,end)
        ccal_filter = ccal.filtering_by_date(start,end)

        """サイボウズにしかない予定の削除"""
        delete = ccal_filter.substract(gcal_filter, 'delete')
        if len(delete.events) > 0:
            delete.view(id=False)
            cyboze.delete_schedule(delete)
        else:
            print("No delete event")

        """グーグルカレンダーにしかない予定の入力"""
        # 音楽練習室以外は通常ウィンドウで判定
        gcal_other_filter = gcal_other.filtering_by_date(start, end)
        input_events = gcal_other_filter.substract(ccal_filter, 'input')

        # 音楽練習室は同期範囲を2025年4月1日以降(未来は無制限)にする。ccalを通常
        # ウィンドウで絞り込むと範囲外に既に入力済みの予定を見落として二重入力
        # してしまうため、フィルタしていない全件のccalと突き合わせる
        music_room_start = datetime(2025, 4, 1)
        music_room_end = now + timedelta(days=365 * 100)  # 実質無制限
        gcal_music_room_filter = gcal_music_room.filtering_by_date(music_room_start, music_room_end)
        music_room_input = gcal_music_room_filter.substract(ccal, 'music_room_input')
        input_events = input_events.union(music_room_input, 'input')

        if len(input_events.events) > 0:
            input_events.view()
            cyboze.input_schedule(input_events)
        else:
            print("No input event")

        """終了"""
        cyboze.close()

        break

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error occurred: {e}")
        print("Chrome の起動に失敗した可能性があります。")
        print("1. Chrome が最新バージョンであることを確認してください。")
        print("2. 他の Chrome ウィンドウをすべて閉じてから再試行してください。")
        print("5秒後に自動的に再試行します。終了するには Ctrl + C を押してください。")

        time.sleep(5)

input("finish sync. press enter to close this window.")
