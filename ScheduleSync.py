from datetime import datetime, timedelta

from Chrome.GoogleCalender import GoogleCalender
from Chrome.Cyboze import Cyboze
from Calender import Calender

"""
when you first use selenium, you have to install driver by pip command.

pip install chromedriver-binary== (your chrome version: eg. 125.0.6422.78)
"""

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
    "Office Hour_c04ca1c5bc84b675f8deec736a75ef5f2a3bd9636dc7ad0280f34bb5f0461dd9@group.calendar.google.com.ics",
    ]

gcal = []
for calender in calender_list:
    buf = Calender.GoogleCalender('gcal', calender)
    if gcal == []:
        gcal = buf
    else:
        gcal = buf.union(gcal)
    
    print(calender)
    print(gcal.view())

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
delete.view(id=False)
cyboze.delete_schedule(delete)

"""グーグルカレンダーにしかない予定の入力"""
input = gcal_filter.substract(ccal_filter, 'input')
input.view()
cyboze.input_schedule(input)

"""終了"""
cyboze.close(1)