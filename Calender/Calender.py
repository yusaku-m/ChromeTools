from Calender import Event

class Calender():
    """複数予定の集合"""
    def __init__(self, name ='calender', source = []):
        self.name = name
        self.events = source


    def view(self, id = False):
        for i, event in enumerate(self.events):
            print(f'{self.name}{i}', end=':')
            event.view(id)

    def union(self, calender, new_name = 'union'):
        """入力カレンダーと結合"""
        return Calender(new_name, self.events + calender.events)

    def substract(self, calender, new_name = 'substract'):
        """入力カレンダーとの重複予定を削除"""
        events = self.events
        for eventB in calender.events:
            events = [eventA for eventA in events if not eventA.match(eventB)]
        return Calender(new_name, events)

    def filtering_by_date(self, start, end, new_name = 'filtered'):
        """datetime形式で入力した期間の予定のみ抽出"""
        events = self.events
        events = [event for event in events if event.start_time > start]
        events = [event for event in events if event.start_time < end]
        return Calender(new_name, events)

class OfficeHour(Calender):
    """変形労働カレンダー"""
    def __init__(self, name ='calender', source = None):
        """csvから勤務予定取得"""
        super().__init__(name)
        self.name = 'OfficeHour'
        import pandas as pd
        data_list = pd.read_csv(source, sep=",", header = None)
        import numpy as np
        data_list = np.array(data_list)
        #ヘッダー・フッターを削除
        data_list = np.array(data_list[4:40,1:], dtype = 'unicode')
        #print(data_list.shape)
        #print(data_list)
        from datetime import datetime
        if datetime.now().month < 4:
            bussinessyear = datetime.now().year - 1
        else:
            bussinessyear = datetime.now().year
        for rawmonth in range(12):
            if rawmonth < 6:
                offset = 0
            else:
                offset = 2
            start = rawmonth * 4 + offset
            end = start + 4 + offset
            month_raw = data_list[:, start:end]
            actmonth = (rawmonth + 3) % 12 + 1
            print(actmonth)
            month_calender = np.array([])
            for day in range(month_raw.shape[0]):
                if month_raw[day][3] != 'nan':
                    buftime = month_raw[day][3]
                    buftime = buftime.split('～') 
                    begintime = np.array(buftime[0].split(':'), dtype = 'int64')
                    finishtime = np.array(buftime[1].split(':'), dtype = 'int64')
                    start_time = datetime(bussinessyear, actmonth, int(month_raw[day][0]), begintime[0], begintime[1])
                    end_time = datetime(bussinessyear, actmonth, int(month_raw[day][0]), finishtime[0], finishtime[1])
                    self.events.append = Event.Event('勤務', start_time, end_time, 'non')

class CybozeCalender(Calender):
    """サイボウズ予定"""
    def __init__(self, name ='CybozeCalender', source = None):
        """sourceにはファイルパスを"""
        super().__init__(name)
        self.name = name
        import pandas as pd
        try:
            df = pd.read_csv(source, sep=',', header = 0, encoding = 'cp932')
        except:
            df = pd.read_csv(source, sep=',', header = 0, encoding = 'utf-8')
        for index, row in df.iterrows():
            from datetime import datetime
            from datetime import timedelta
            if pd.isnull(row["開始時刻"]) or pd.isnull(row["終了時刻"]):
                #終日予定
                start_time = datetime.strptime(f'{row["開始日付"]}', "%Y/%m/%d")
                end_time = datetime.strptime(f'{row["終了日付"]}', "%Y/%m/%d") + timedelta(days=1)
            else:
                #時間予定
                start_time = datetime.strptime(f'{row["開始日付"]} {row["開始時刻"]}', "%Y/%m/%d %H:%M:%S")
                end_time = datetime.strptime(f'{row["終了日付"]} {row["終了時刻"]}', "%Y/%m/%d %H:%M:%S")
            if not pd.isnull(row["メモ"]): #nanエラー会費
                if 'datetime.datetime(' in row["メモ"]: #他の方が入力した予定はカウントしない 
                    self.events.append(Event.Event(row["予定詳細"], start_time, end_time, row["メモ"]))
        #読み込み完了後，sourceを削除
        import os
        os.remove(source)

class GoogleCalender(Calender):
    """googleカレンダー予定"""
    def __init__(self, name ='calender', source = None, unifiedeventname = None):
        super().__init__(name)  
        self.name = name
        self.events = []
        #カレンダー全体を読み込み
        raw_calender = open(f"./data/GoogleCalender/{source}", 'r', encoding='UTF-8').read()
        #イベント毎に分割
        raw_calender = raw_calender.split('BEGIN:VEVENT')
        #現在の西暦を取得
        from datetime import datetime
        from datetime import timedelta
        ThisYear = datetime.today().year
        ThisMonth = datetime.today().month
        #print(ThisYear, ThisMonth)
        except_num = 0
        from tqdm import tqdm
        for raw_schedule in tqdm(raw_calender[1:]):

            #単発予定の情報を抽出
            if unifiedeventname == None:
                name = self.extract(raw_schedule, 'SUMMARY:') 
            else:
                name = unifiedeventname
                
            start_day   = self.extract(raw_schedule, 'DTSTART;VALUE=DATE:')
            end_day     = self.extract(raw_schedule, 'DTEND;VALUE=DATE:')

            #開始時間の検索
            start_time  = self.extract(raw_schedule, 'DTSTART:')
            if start_time != "":
                sdaytime = datetime.strptime(start_time, '%Y%m%dT%H%M%SZ') + timedelta(hours = 9)

            start_time = self.extract(raw_schedule, 'DTSTART;TZID=Asia/Tokyo:')
            if start_time != "":
                sdaytime = datetime.strptime(start_time, '%Y%m%dT%H%M%S')
            
            #修了時間の検索
            end_time    = self.extract(raw_schedule, 'DTEND:')
            if end_time != "":
                edaytime = datetime.strptime(end_time, '%Y%m%dT%H%M%SZ') + timedelta(hours = 9)

            end_time    = end_time = self.extract(raw_schedule, 'DTEND;TZID=Asia/Tokyo:')
            if end_time != "":
                edaytime = datetime.strptime(end_time, '%Y%m%dT%H%M%S')

            uid         = self.extract(raw_schedule, 'UID:')

            #繰り返し予定の情報を抽出
            repeat_rule = self.extract(raw_schedule, 'RRULE:')
            on_weekday  = self.extract(raw_schedule, 'BYDAY=') # 実施曜日(MO,TU,WE,TH,FR,SA,SU)
            except_date = self.extract(raw_schedule, 'EXDATE;TZID=Asia/Tokyo:')
            origin_date = self.extract(raw_schedule, 'RECURRENCE-ID;TZID=Asia/Tokyo:')

            #日時情報を抽出
            #print(f'{name}, {start_time}, {end_time}, {rstart_time}, {rend_time}, {repeat_rule}, {uid}')

            #単発予定の場合
            if repeat_rule == '':
                #予定の追加
                #終日予定
                if start_day != '': 
                    sdaytime = datetime.strptime(start_day, '%Y%m%d')
                    edaytime = datetime.strptime(end_day, '%Y%m%d')
                    id = str([name, sdaytime, edaytime, uid])
                    delta = edaytime - sdaytime
                    for i in range(delta.days):
                        self.events.append(Event.AllDay(name,sdaytime+timedelta(days=i),sdaytime+timedelta(days=i+1),id))
                
                #時間予定
                if start_day == '':
                    #edaytime = sdaytime
                    id = str([name, sdaytime, edaytime, uid])
                    self.events.append(Event.Event(name, sdaytime, edaytime, id))

                #繰り返しの例外予定
                if origin_date != '':
                    odaytime = datetime.strptime(origin_date, '%Y%m%dT%H%M%S')
                    #print(odaytime)
                    #変更元の予定を削除
                    self.events = [event for event in self.events if not (event.start_time == odaytime and uid in event.id)]

            #繰り返し予定（かつ時間有）の場合
            if repeat_rule != '' and start_time != '' and end_time != '':
                #毎週繰り返しの場合
                if 'FREQ=WEEKLY' in repeat_rule:
                    #除外日を取得
                    exceptdaytimes = []
                    for i in range(int(len(except_date)/15)):
                        exceptdaytimes.append(datetime.strptime(except_date[i*15:(i+1)*15], '%Y%m%dT%H%M%S'))
                    #終了日を取得        
                    if 'UNTIL=' in repeat_rule:                    #日時指定の場合
                        untiltime = repeat_rule.split('UNTIL=')[1].split(';')[0]
                        #print(f'{name}, {rstart_time}, {untiltime}')
                        try:
                            untiltime = datetime.strptime(untiltime, '%Y%m%dT%H%M%SZ') + timedelta(hours = 9)
                        except:
                            untiltime = datetime.strptime(untiltime, '%Y%m%d')
                    if 'COUNT=' in repeat_rule:                    #回数指定の場合
                        count_num = int(repeat_rule.split('COUNT=')[1].split(';')[0])
                        untiltime = sdaytime
                        for i in range(count_num):
                            untiltime += timedelta(days = 7)

                    #終了まで予定を作成
                    weekdays = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
                    while sdaytime < untiltime:
                        if weekdays[sdaytime.weekday()] in on_weekday:
                            #除外予定の判定
                            ex_flag = 0
                            for daytime in exceptdaytimes:
                                if sdaytime == daytime:
                                    ex_flag = 1
                            if ex_flag == 0:
                                id = str([name, sdaytime, edaytime, uid])
                                self.events.append(Event.Event(name, sdaytime, edaytime, id))
                        #次の日へ
                        sdaytime += timedelta(days = 1)
                        edaytime += timedelta(days = 1)
        # 読み込み完了後，sourceを削除
        import os
        os.remove(f"./data/GoogleCalender/{source}")
        

    def extract(self, raw, search):
        if search in raw:
            buf = raw.split(search)
            result = ''
            for line in buf[1:]:
                result += line.split('\n')[0]
        else:
            result = ''
        return result
