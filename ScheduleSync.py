from datetime import datetime, timedelta

from Chrome.GoogleCalender import GoogleCalender
from Chrome.Cyboze import Cyboze
from Calender import Calender

"""
when you first use selenium, you have to install driver by pip command.

pip install chromedriver-binary== (your chrome version: eg. 125.0.6422.78)

2025/3/27現在，以下のコマンドでインストールしたバージョンは即閉じが発生
or you have to install chromedriver-binary-auto

You can see your chrome version by 'chrome://version/'
"""
print("sync start")

while True:
    try:

        """グーグルカレンダーの取得"""
        user_data_path = "C:/Users/Yusaku/AppData/Local/Google/Chrome/User Data/"
        chrome = GoogleCalender(user_data_path)
        chrome.set_id('jagaimo13')
        chrome.get_calender()
        chrome.close()

        #指定カレンダーの結合

        calender_list = [
            'Lab_maedalab17@gmail.com.ics',
            "Work_jagaimo13@gmail.com.ics",
            "Office_Hour_277ef437beac7b8e071b76be72a8d55738862bf290b78395133241b387847800@group.calendar.google.com.ics",
            ]

        gcal = []
        for calender in calender_list:
            buf = Calender.GoogleCalender('gcal', calender)
            if gcal == []:
                gcal = buf
            else:
                gcal = buf.union(gcal)
            
            print(calender)
            #print(gcal.view())

        """サイボウズカレンダーに自動入力された予定の取得"""
        user_data_path = "C:/Users/Yusaku/AppData/Local/Google/Chrome/User Data/"
        cyboze = Cyboze(user_data_path)
        cyboze.set_id(name='前田　祐作',uid='5791',department='機械工学科',gid='2100')
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
        cyboze.close(1)

        break

    except Exception as e:
        print(e)
        print("error is occured. meybe you have to install driver by pip command.")
        print("pip install chromedriver-binary== (your chrome version: eg. 125.0.6422.78)")
        print("or you have to install chromedriver-binary-auto")
        print("You can see your chrome version by 'chrome://version/'")
        print("or pip install chromedriver-binary-auto")
        
        input("If you want to continue, press any key. If you want to stop, press Ctrl + C")

input("finish sync. press enter to close this window.")