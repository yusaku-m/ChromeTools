"""サイボウズ Garoon 6 の REST API クライアント。

2026-11-09 の Office 10 → Garoon 6 移行に伴い、Selenium で画面を操作していた
`Chrome/Cyboze.py` を置き換えるためのもの。Office 10 では CSV エクスポートと
フォーム操作しか手段が無かったが、Garoon には REST API があるので、予定の
取得・登録・削除をすべて HTTP で行える。

Office 10 時代にあった以下の不安定要因がまとめて不要になる:
  - Chrome の全プロセス kill とプロファイル競合
  - Windows Hello の PIN 入力待ち(`Browser.patient_get`)
  - CSV エクスポート画面のフィールド名当て(`SetDate.*`)とダウンロード待ち
  - 検索結果からタイトル完全一致でリンクを探す処理(`Event._find_schedule_link`)
  - 参加者/施設の <option> 注入、Member ラジオ、ネイティブ alert() の後始末

認証は `X-Cybozu-Authorization: base64("ログイン名:パスワード")` ヘッダのみ。
`Authorization: Basic` も Windows 統合認証もブラウザのセッションクッキーも
通らないことを実機で確認済み。
"""

import base64
import datetime
import os

import requests

BASE_URL = 'https://garoon.da.kagawa-nct.ac.jp/scripts/cbgrn/grn.exe/api/v1'

#Windows資格情報マネージャー(keyring)の保存先。
#登録は Other/set_garoon_password.py で行う。
KEYRING_SERVICE = 'ChromeTools-Garoon'

#環境変数でも渡せるようにしておく(CI や別マシンでの実行用)
ENV_LOGIN = 'GAROON_LOGIN'
ENV_PASSWORD = 'GAROON_PASSWORD'

#予定APIの rangeEnd に指定できる絶対的な上限。これを超えると 400
#GRN_REST_API_00220 になる。期間の長さの制限ではなく絶対的な日付の天井で、
#rangeStart を後ろにずらしても同じ日付で切れることを実機で確認済み
#(いわゆる2038年問題の境界)。ScheduleSync.py の music_room 用「実質無制限」
#ウィンドウ(now + 100年)はここで頭打ちにする必要がある。
RANGE_END_MAX = datetime.datetime(2037, 12, 31, 0, 0, 0)

#1リクエストで取得できる最大件数(実機で1000まで通ることを確認済み)
PAGE_LIMIT = 1000

#サイボウズ側が自動同期した予定だと判別するためのメモ欄のマーカー。
#Office 10 時代から `Event.id`(タイトル・開始・終了・UID のリスト repr)を
#メモ欄に保存しており、Garoon へのコンバート後もそのまま残っていることを
#実機で確認済み。他の人が入力した予定を削除対象にしないための判定に使う。
SYNC_MARKER = 'datetime.datetime('

#実機で確認済みのエラーコード
ERR_AUTH = 'GRN_REST_API_00003'              #認証情報が無い/誤り
ERR_RANGE = 'GRN_REST_API_00220'             #rangeEnd が上限を超えている
ERR_FACILITY_CONFLICT = 'GRN_SCHD_13208'     #施設の二重予約(Office 10 の 14312 相当)
ERR_FACILITY_NEEDS_TIME = 'GRN_SCHD_13207'   #終日予定に施設は予約できない
ERR_EVENT_NOT_FOUND = 'GRN_SCHD_13001'       #予定が存在しない(削除済み等)


class GaroonError(RuntimeError):
    """Garoon API がエラーを返したときの例外。

    サイボウズ側の事情による想定内の失敗(施設の二重予約など)を呼び出し側が
    `code` で判別できるようにしている。Office 10 時代はネイティブ alert() を
    read して判別するしかなかったが、API では HTTP 400 とエラーコードで返る。
    """

    def __init__(self, status_code, code, message, path=None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.path = path
        super().__init__(f'{status_code} {code}: {message} ({path})')


def _to_naive(dt):
    """タイムゾーン付き datetime を naive な JST に落とす。

    このプロジェクトの Event/Calender は一貫して naive な JST の datetime を
    使っている(`Calender._to_naive_jst` と同じ方針)ため、API 由来の
    aware な datetime はここで揃えておく。
    """
    if dt.tzinfo is None:
        return dt
    jst = datetime.timezone(datetime.timedelta(hours=9))
    return dt.astimezone(jst).replace(tzinfo=None)


def _iso_jst(dt):
    """naive な JST の datetime を API が受け付ける ISO8601 文字列にする。"""
    return _to_naive(dt).strftime('%Y-%m-%dT%H:%M:%S+09:00')


def _parse_api_datetime(value):
    """API が返す ISO8601 文字列を naive な JST の datetime にする。"""
    #Python 3.10 の fromisoformat は 'Z' を解釈できないので置換しておく
    return _to_naive(datetime.datetime.fromisoformat(value.replace('Z', '+00:00')))


class GaroonClient:
    """Garoon の予定を読み書きするクライアント。

    `Chrome/Cyboze.py` の `Cyboze` と同じ役回りだが、ブラウザを一切使わない。
    `input_schedule()` / `delete_schedule()` は Cyboze と同じシグネチャなので、
    ScheduleSync.py 側はバックエンドを差し替えるだけで済む。
    """

    def __init__(self, login=None, password=None, base_url=BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.login, password = self._resolve_credentials(login, password)
        token = base64.b64encode(f'{self.login}:{password}'.encode('utf-8')).decode('ascii')
        self.session = requests.Session()
        self.session.headers.update({
            'X-Cybozu-Authorization': token,
            'Content-Type': 'application/json',
        })
        #code -> {'id', 'name', 'code'} のキャッシュ。ユーザーIDも施設IDも
        #Garoon 内部の連番で、Office 10 のものとは全く別物。しかも本移行時に
        #試験環境とは違う値になる可能性があるため、常に code から引く。
        self._user_cache = {}
        self._facility_cache = None

    # ------------------------------------------------------------------
    # 認証
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_credentials(login, password):
        """引数 → 環境変数 → Windows資格情報マネージャー の順に探す。

        パスワードをリポジトリやコマンド履歴に残さないため、通常運用では
        keyring(Windows資格情報マネージャー)に入れておく。
        """
        login = login or os.environ.get(ENV_LOGIN)
        password = password or os.environ.get(ENV_PASSWORD)
        if login and password:
            return login, password

        try:
            import keyring
        except ImportError as exc:
            raise RuntimeError(
                'Garoon の資格情報が見つかりません。keyring が入っていないため'
                '資格情報マネージャーからも読めません。`pixi install` を実行するか、'
                f'環境変数 {ENV_LOGIN} / {ENV_PASSWORD} を設定してください。'
            ) from exc

        if not login:
            #ログイン名はパスワードほど秘密ではないので、保存済みのものを使う
            login = keyring.get_password(KEYRING_SERVICE, '__login__')
        if not login:
            raise RuntimeError(
                'Garoon のログイン名が分かりません。Other/set_garoon_password.py を'
                f'実行して保存するか、環境変数 {ENV_LOGIN} を設定してください。'
            )
        password = keyring.get_password(KEYRING_SERVICE, login)
        if not password:
            raise RuntimeError(
                f'Garoon ({login}) のパスワードが資格情報マネージャーにありません。'
                'Other/set_garoon_password.py を実行して保存してください。'
            )
        return login, password

    # ------------------------------------------------------------------
    # 低レベル
    # ------------------------------------------------------------------
    def _request(self, method, path, **kwargs):
        kwargs.setdefault('timeout', 120)
        response = self.session.request(method, self.base_url + path, **kwargs)
        if response.status_code >= 400:
            #エラー種別はレスポンスヘッダの X-Cybozu-Error に入る。本文は IIS の
            #カスタムHTMLエラーページに差し替えられていることがある(401がそう)ので、
            #本文のJSONだけを当てにしてはいけない。
            code = response.headers.get('X-Cybozu-Error', '')
            message = ''
            try:
                body = response.json()
                code = body.get('code') or code
                message = body.get('message') or ''
            except ValueError:
                message = response.text[:200].replace('\n', ' ')
            raise GaroonError(response.status_code, code, message, path)
        if not response.content:
            return {}
        return response.json()

    # ------------------------------------------------------------------
    # ユーザー・施設の解決
    # ------------------------------------------------------------------
    def find_user(self, code):
        """ログイン名(code)からユーザーを引く。見つからなければ None。

        絞り込みパラメータは `name` であって `code` ではない。`code` を渡すと
        **黙って無視され全件の先頭が返る**(実機で確認済み: `?code=maeda-y` が
        Administrator 以下の無関係なユーザーを返した)。`name` にログイン名を
        渡すと当該ユーザーが引けるので、その上で code の完全一致を確認する。
        """
        if code in self._user_cache:
            return self._user_cache[code]
        data = self._request('GET', '/base/users', params={'name': code, 'limit': 50})
        users = data.get('users', [])
        found = next((u for u in users if u.get('code') == code), None)
        self._user_cache[code] = found
        return found

    def _all_facilities(self):
        """施設を全件取得する。

        `limit` の既定・最大が何であれ取りこぼさないようページングする。
        実機では全127件あり、音楽練習室がちょうど127番目だったため
        `limit=100` の1回だけでは取得できず空振りした。
        """
        if self._facility_cache is not None:
            return self._facility_cache
        facilities = []
        offset = 0
        while True:
            data = self._request('GET', '/schedule/facilities',
                                 params={'limit': 100, 'offset': offset})
            facilities.extend(data.get('facilities', []))
            if not data.get('hasNext'):
                break
            offset += 100
        self._facility_cache = facilities
        return facilities

    def find_facility(self, code=None, name=None):
        """施設を code か name で引く。見つからなければ None。"""
        for facility in self._all_facilities():
            if code is not None and facility.get('code') == code:
                return facility
            if name is not None and facility.get('name') == name:
                return facility
        return None

    def resolve_members(self, entries, kind):
        """[(code, 表示名), ...] を API に渡す形の辞書リストに変換する。

        `kind` は 'user' か 'facility'。解決できなかったものは警告を出して
        除外する(黙って落とすと施設予約が無いまま登録されてしまうため)。
        """
        resolved = []
        for code, display_name in entries or []:
            if kind == 'user':
                found = self.find_user(code)
                if found:
                    resolved.append({'id': found['id'], 'type': 'USER'})
            else:
                found = self.find_facility(code=code, name=display_name)
                if found:
                    resolved.append({'id': found['id']})
            if not found:
                print(f'警告: Garoon 上に {kind} 「{display_name}」(code={code}) が'
                      f'見つかりませんでした。この予定には付与されません。')
        return resolved

    # ------------------------------------------------------------------
    # 予定の取得
    # ------------------------------------------------------------------
    def get_events(self, start, end, fields=None):
        """指定期間の予定を全件取得する(ページング込み)。

        `end` は API の上限(RANGE_END_MAX)を超えないよう自動で切り詰める。
        """
        if end > RANGE_END_MAX:
            print(f'情報: 取得終了日を API の上限 {RANGE_END_MAX.date()} に切り詰めます'
                  f'(指定値 {end.date()})。')
            end = RANGE_END_MAX
        if start >= end:
            return []

        if fields is None:
            fields = 'id,subject,start,end,isAllDay,notes,attendees,facilities,eventType'

        events = []
        offset = 0
        while True:
            data = self._request('GET', '/schedule/events', params={
                'rangeStart': _iso_jst(start),
                'rangeEnd': _iso_jst(end),
                'limit': PAGE_LIMIT,
                'offset': offset,
                'fields': fields,
            })
            page = data.get('events', [])
            events.extend(page)
            if not data.get('hasNext') or not page:
                break
            offset += len(page)
        return events

    # ------------------------------------------------------------------
    # 予定の登録・削除
    # ------------------------------------------------------------------
    def add_event(self, title, start_time, end_time, notes='',
                  attendees=None, facilities=None, is_all_day=False):
        """予定を1件登録し、API のレスポンス(登録された予定)を返す。"""
        body = {
            'eventType': 'REGULAR',
            'subject': title,
            'notes': notes,
            'isAllDay': bool(is_all_day),
            'start': {'dateTime': _iso_jst(start_time), 'timeZone': 'Asia/Tokyo'},
            'end': {'dateTime': _iso_jst(end_time), 'timeZone': 'Asia/Tokyo'},
        }
        #本人は常に参加者に入れる(Office 10 のフォームでも sUID に本人が
        #あらかじめ入っていた)
        me = self.find_user(self.login)
        members = [{'id': me['id'], 'type': 'USER'}] if me else []
        for attendee in attendees or []:
            if attendee not in members:
                members.append(attendee)
        body['attendees'] = members
        if facilities:
            body['facilities'] = facilities
        return self._request('POST', '/schedule/events', json=body)

    def delete_event(self, event_id):
        """予定を1件削除する。既に無い場合は何もしない。"""
        try:
            self._request('DELETE', f'/schedule/events/{event_id}')
        except GaroonError as exc:
            if exc.code == ERR_EVENT_NOT_FOUND:
                print(f'情報: 予定(id={event_id})は既に存在しません。削除をスキップします。')
                return
            raise

    # ------------------------------------------------------------------
    # Calender オブジェクト単位の操作(Cyboze と同じインターフェース)
    # ------------------------------------------------------------------
    def input_schedule(self, calender):
        """Calender の予定をまとめて登録する。

        1件の失敗(施設の二重予約など)で同期全体を止めないよう、Cyboze と同じく
        個別に try/except して次へ進む。
        """
        from tqdm import tqdm
        from Calender import Event as EventModule

        for event in tqdm(calender.events, desc='予定入力中(Garoon)'):
            if isinstance(event, EventModule.MultiDay):
                #期間予定は Office 10 時代から同期対象外
                continue
            is_all_day = isinstance(event, EventModule.AllDay)
            try:
                attendees = self.resolve_members(event.participants, 'user')
                facilities = self.resolve_members(event.facilities, 'facility')
                self.add_event(
                    title=event.title,
                    start_time=event.start_time,
                    end_time=event.end_time,
                    notes=event.id,
                    attendees=attendees,
                    facilities=facilities,
                    is_all_day=is_all_day,
                )
            except GaroonError as exc:
                if exc.code == ERR_FACILITY_CONFLICT:
                    reason = '施設が他の予約と重なっています'
                elif exc.code == ERR_FACILITY_NEEDS_TIME:
                    reason = '終日予定に施設は予約できません'
                else:
                    reason = exc.message or exc.code
                print(f'警告: 「{event.title}」({event.start_time}~{event.end_time})の'
                      f'入力に失敗したためスキップします: {reason} [{exc.code}]')
            except Exception as exc:  # noqa: BLE001 - 1件の失敗で全体を止めない
                print(f'警告: 「{event.title}」({event.start_time}~{event.end_time})の'
                      f'入力に失敗したためスキップします: {exc}')

    def delete_schedule(self, calender):
        """Calender の予定をまとめて削除する。

        Office 10 では予定を特定するのにタイトルで検索してリンクを探す必要が
        あったが、Garoon では取得時の予定IDをそのまま使える。
        `GaroonCalender` が各 Event に `garoon_id` を持たせている。
        """
        from tqdm import tqdm

        for event in tqdm(calender.events, desc='予定削除中(Garoon)'):
            event_id = getattr(event, 'garoon_id', None)
            if event_id is None:
                print(f'警告: 「{event.title}」({event.start_time}~{event.end_time})に'
                      'Garoon の予定IDがないため削除をスキップします。')
                continue
            try:
                self.delete_event(event_id)
            except Exception as exc:  # noqa: BLE001 - 1件の失敗で全体を止めない
                print(f'警告: 「{event.title}」({event.start_time}~{event.end_time})の'
                      f'削除に失敗したためスキップします: {exc}')

    # ------------------------------------------------------------------
    # 互換用
    # ------------------------------------------------------------------
    def close(self):
        """Cyboze(Browser) と同じ呼び出しで終われるようにしておく。"""
        self.session.close()
