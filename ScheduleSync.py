from datetime import datetime, timedelta

from Chrome.GoogleCalender import GoogleCalender
from Chrome.Cyboze import Cyboze
from Calender import Calender

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
        chrome.close()

        # 展開されたICSファイルをすべて自動検出して結合
        import os
        gcal_dir = './data/GoogleCalender'
        calender_list = sorted([f for f in os.listdir(gcal_dir) if f.endswith('.ics')])
        print(f"Found {len(calender_list)} calendars: {calender_list}")

        gcal = []
        for calender in calender_list:
            buf = Calender.GoogleCalender('gcal', calender)
            if gcal == []:
                gcal = buf
            else:
                gcal = buf.union(gcal)
            print(calender)

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
        input_events = gcal_filter.substract(ccal_filter, 'input')
        if len(input_events.events) > 0:
            input_events.view()
            cyboze.input_schedule(input_events)
        else:
            print("No input event")

        """終了"""
        cyboze.close()

        break

    except Exception as e:
        print(f"Error occurred: {e}")
        print("Chrome の起動に失敗した可能性があります。")
        print("1. Chrome が最新バージョンであることを確認してください。")
        print("2. 他の Chrome ウィンドウをすべて閉じてから再試行してください。")
        
        input("再試行するには何かキーを押してください。終了するには Ctrl + C を押してください。")

input("finish sync. press enter to close this window.")
