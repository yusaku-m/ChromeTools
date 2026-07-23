import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from icalendar import Calendar as ICalendar
from dateutil.rrule import rrulestr

from Calender import Event
from tqdm import tqdm

JST = ZoneInfo('Asia/Tokyo')
_RECUR_HORIZON = timedelta(days=365 * 100)  # UNTIL/COUNTが無い無制限の繰り返しに対する実質的な上限


def _to_naive_jst(dt):
    """aware/naiveなdatetime、またはdateを、tzinfo無しのJST datetimeに正規化する"""
    if isinstance(dt, datetime):
        if dt.tzinfo is not None:
            return dt.astimezone(JST).replace(tzinfo=None)
        return dt
    return datetime.combine(dt, datetime.min.time())


def _normalize_rrule_until(rrule_str):
    """RRULE文字列中のUNTILを、dtstartと同じnaive-JST形式(YYYYMMDDTHHMMSS、Z無し)に書き換える。
    GoogleのRRULEはUNTILがUTC(...Z)の場合と、非標準な時刻無しの裸の日付の場合があり
    (実データのFREQ=DAILY;UNTIL=20190829で確認済み)、dtstart側をnaiveにして渡すには
    UNTIL側も型を揃える必要がある(揃えないとdateutilの
    「DTSTARTがaware(tzinfo付き)ならUNTILはUTC必須」制約に非標準な裸日付が違反しValueErrorになる)。"""
    m = re.search(r'UNTIL=(\d{8})(T(\d{6})(Z)?)?', rrule_str)
    if not m:
        return rrule_str
    date_part, _, time_part, has_z = m.groups()
    if has_z:
        until_utc = datetime.strptime(date_part + time_part, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
        new_until = _to_naive_jst(until_utc).strftime('%Y%m%dT%H%M%S')
    elif time_part:
        new_until = date_part + 'T' + time_part
    else:
        new_until = date_part + 'T235959'
    return rrule_str[:m.start()] + f'UNTIL={new_until}' + rrule_str[m.end():]

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
        events = list(self.events)  # コピーして元リストを破壊しない
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
        for index, row in tqdm(df.iterrows()):
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
    def __init__(self, name ='calender', source = None, unifiedeventname = None, extra_participants = None, extra_facilities = None, skip_allday = False, skip_titles = None):
        super().__init__(name)
        self.name = name
        self.events = []

        path = f"./data/GoogleCalender/{source}"
        with open(path, 'rb') as f:
            ical = ICalendar.from_ical(f.read())

        vevents = [c for c in ical.walk() if c.name == 'VEVENT']

        #繰り返しの例外予定(RECURRENCE-IDを持つ上書きイベント)を先に集めておく。
        #マスター側の展開時に、該当オカレンスをこちらの内容で置き換える
        overrides = {}
        for comp in vevents:
            recurrence_id = comp.get('RECURRENCE-ID')
            if recurrence_id is not None:
                uid = str(comp.get('UID'))
                overrides[(uid, _to_naive_jst(recurrence_id.dt))] = comp

        for comp in tqdm(vevents):
            if comp.get('RECURRENCE-ID') is not None:
                continue  #上書きイベント自体はマスター側の展開時に反映するのでここでは無視

            event_name = self._extract_name(comp, unifiedeventname)

            #予定名で丸ごとスキップ(例:施設と重複する個人名の仮予約予定)
            if skip_titles and event_name in skip_titles:
                continue

            uid = str(comp.get('UID'))
            dtstart = comp.get('DTSTART').dt
            #dateutil.rruleでの展開後は常にdatetimeになってしまうため、終日予定かどうかは
            #展開前のDTSTARTの型(date/datetime)で判定して個別に持ち歩く
            is_allday = not isinstance(dtstart, datetime)
            dtend_prop = comp.get('DTEND')
            #DTENDが存在しない予定(瞬間的な予定)は開始時刻と同じ終了時刻を仮定する
            dtend = dtend_prop.dt if dtend_prop is not None else dtstart

            rrule_prop = comp.get('RRULE')

            #単発予定の場合
            if rrule_prop is None:
                self._append_occurrence(event_name, dtstart, dtend, uid, extra_participants, extra_facilities, skip_allday, is_allday)
                continue

            #繰り返し予定の場合: dateutil.rruleで実際のオカレンス日時に展開する
            naive_dtstart = _to_naive_jst(dtstart)
            duration = _to_naive_jst(dtend) - naive_dtstart
            rrule_str = _normalize_rrule_until(rrule_prop.to_ical().decode())
            rr = rrulestr(f"RRULE:{rrule_str}", dtstart=naive_dtstart)
            horizon = datetime.now() + _RECUR_HORIZON
            exdates = self._extract_exdates(comp)

            for occ_start in rr.between(naive_dtstart, horizon, inc=True):
                if occ_start in exdates:
                    continue

                override = overrides.get((uid, occ_start))
                if override is not None:
                    o_name = self._extract_name(override, unifiedeventname)
                    if skip_titles and o_name in skip_titles:
                        continue
                    o_dtstart = override.get('DTSTART').dt
                    o_is_allday = not isinstance(o_dtstart, datetime)
                    o_dtend_prop = override.get('DTEND')
                    o_dtend = o_dtend_prop.dt if o_dtend_prop is not None else o_dtstart
                    self._append_occurrence(o_name, o_dtstart, o_dtend, uid, extra_participants, extra_facilities, skip_allday, o_is_allday)
                else:
                    self._append_occurrence(event_name, occ_start, occ_start + duration, uid, extra_participants, extra_facilities, skip_allday, is_allday)

        #読み込み完了後，sourceを削除
        import os
        os.remove(path)

    def _append_occurrence(self, name, dtstart, dtend, uid, extra_participants, extra_facilities, skip_allday, is_allday):
        """単発予定・繰り返し展開後の1件のオカレンスをself.eventsに追加する"""
        sdaytime = _to_naive_jst(dtstart)
        edaytime = _to_naive_jst(dtend)
        id = str([name, sdaytime, edaytime, uid])

        if is_allday:
            if skip_allday:
                return
            delta = edaytime - sdaytime
            for i in range(delta.days):
                self.events.append(Event.AllDay(name, sdaytime+timedelta(days=i), sdaytime+timedelta(days=i+1), id, participants=extra_participants, facilities=extra_facilities))
        else:
            self.events.append(Event.Event(name, sdaytime, edaytime, id, participants=extra_participants, facilities=extra_facilities))

    @staticmethod
    def _extract_name(comp, unifiedeventname):
        if unifiedeventname is not None:
            return unifiedeventname
        summary = comp.get('SUMMARY')
        return str(summary) if summary is not None else ''

    @staticmethod
    def _extract_exdates(comp):
        exdates = set()
        exdate_prop = comp.get('EXDATE')
        if exdate_prop is None:
            return exdates
        items = exdate_prop if isinstance(exdate_prop, list) else [exdate_prop]
        for item in items:
            for d in item.dts:
                exdates.add(_to_naive_jst(d.dt))
        return exdates
