def path_change():
    import os
    print(os.getcwd())
    print(__file__)
    if 'Temp' not in __file__:
        print('ディレクトリを変更')
        CURRENTPATH = os.path.dirname(__file__)
        os.chdir(CURRENTPATH)
    print(os.getcwd())

def get_working_calender():
    print('変形労働カレンダーを読み込み中') 
    import os
    import pandas as pd
    data_list = pd.read_csv(os.getcwd() + "/calender.csv", sep=",", header = None)
    import numpy as np
    data_list = np.array(data_list)
    #ヘッダー・フッターを削除
    data_list = np.array(data_list[4:40,1:], dtype = 'unicode')
    #print(data_list.shape)
    #print(data_list)
    working_times = np.array([])
    for month in range(12):
        if month < 6:
            offset = 0
        else:
            offset = 2
        start = month * 4 + offset
        end = start + 4 + offset
        month_raw = data_list[:, start:end]
        act_month = (month + 3) % 12 + 1 #実際の月に補正
        
        import datetime
        year = datetime.date.today().year
        if act_month <= 3:
            year += 1

        #print(month_raw)
        for day in range(month_raw.shape[0]):
            working_time = month_raw[day][3]
            if working_time != 'nan':
                act_day = int(month_raw[day][0])
                if len(working_times) == 0:
                    working_times = np.array([year, act_month, act_day, working_time])
                else:
                    working_times = np.vstack((working_times, [year, act_month, act_day, working_time])) 
    return working_times

def workcalender_to_ical(working_times):
    f = open('Office_Hour.ics', 'w', encoding='utf-8')
    #ヘッダーの書き込み
    f.write(
        'BEGIN:VCALENDAR\n'\
        'PRODID:-//Google Inc//Google Calendar 70.9054//EN\n'\
        'VERSION:2.0\n'\
        'CALSCALE:GREGORIAN\n'\
        'METHOD:PUBLISH\n'\
        'X-WR-CALNAME:Office Hour\n'\
        'X-WR-TIMEZONE:Asia/Tokyo\n'\
        'BEGIN:VTIMEZONE\n'\
        'TZID:Asia/Tokyo\n'\
        'X-LIC-LOCATION:Asia/Tokyo\n'\
        'BEGIN:STANDARD\n'\
        'TZOFFSETFROM:+0900\n'\
        'TZOFFSETTO:+0900\n'\
        'TZNAME:JST\n'\
        'DTSTART:19700101T000000\n'\
        'END:STANDARD\n'\
        'END:VTIMEZONE\n'\
    )
    
    for event in working_times:
        print(event)
        #開始時間（dtstart）の作成
        year = str(event[0])
        month = str(event[1]).zfill(2)
        day = str(event[2]).zfill(2)
        times = event[3].split('～')[0].split(':')        
        dtstart = year + month + day + 'T' + times[0].zfill(2) + times[1].zfill(2) + '00'
        #終了時間（dtend）の作成
        times = event[3].split('～')[1].split(':')        
        dtend = year + month + day + 'T' + times[0].zfill(2) + times[1].zfill(2) + '00'

        #イベントを書き込み
        f.write(
            'BEGIN:VEVENT\n'\
            'DTSTART:' + dtstart + '\n' \
            'DTEND:' + dtend + '\n' \
            'SUMMARY:勤務\n' \
            'END:VEVENT\n' \
        )
    # フッターの書き込み
    f.write('END:VCALENDAR\n')
    f.close()

#ここからメイン処理
path_change()
working_times = get_working_calender()
workcalender_to_ical(working_times)