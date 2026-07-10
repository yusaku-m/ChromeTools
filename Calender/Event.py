from selenium import webdriver
from selenium.webdriver.support.select import Select

from selenium.webdriver.common.by import By

from Chrome.Browser import DatabaseBusyError

class Event():
    """予定単体のクラス"""
    def __init__(self, title, st, et, id, participants=None, facilities=None):
        self.title      = title
        self.start_time = st
        self.end_time   = et
        self.id         = id
        self.participants = participants or []  # [(uid, name), ...] 本人以外に追加する参加者
        self.facilities   = facilities or []     # [(fid, name), ...] 予約する施設

    def view(self, id = False):
        print(f'{self.title}, {self.start_time}, {self.end_time}')
        if id:
            print(f'{self.id}')

    def match(self, event):
        """title・start_time・end_timeの一致のみで同一予定と判定する。
        以前はidの完全一致(uidを含む)も条件にしていたが、Google側で予定が
        削除・再作成される(タイトル・時刻はそのまま新しいUIDが振られる)ケースが
        実際に確認された(音楽練習室カレンダーの「個人練習(他の部員も参加可)」等)。
        idまで一致を要求すると、既にサイボウズに入力済みでも「未入力」と誤判定して
        再入力を試み、施設予約なら二重予約エラーで停止・リトライを繰り返し、
        施設予約でなければ気付かれないままサイボウズ側に重複行が増え続けていた
        (実データ確認済み: 同一タイトル・同一時刻の重複行が複数件見つかった)。"""
        return self.title == event.title and self.start_time == event.start_time and self.end_time == event.end_time

    def _add_participants(self, driver):
        """参加者(sUID)セレクトに追加の参加者を差し込む。
        サイボウズの「← 追加」ボタン(CB7.SelectOrder.AddSelectedItems)がsUIDに
        追加するのと同じ形の素の<option>を直接挿入する。登録ボタン押下時に
        呼ばれるPreSubmitCGID()がselected属性を問わず全<option>を送信対象にするため、
        これだけでUI操作と同じ結果になる。"""
        for uid, name in self.participants:
            driver.execute_script(
                """
                var select = document.getElementsByName('sUID')[0];
                var uid = arguments[0], name = arguments[1];
                for (var i = 0; i < select.options.length; i++) {
                    if (select.options[i].value === uid) { return; }
                }
                var opt = document.createElement('option');
                opt.value = uid;
                opt.text = name;
                select.add(opt, select.options.length - 1);
                """,
                uid, name
            )

    def _add_facilities(self, driver):
        """施設(sFID)セレクトに予約する施設を差し込む。仕組みは_add_participants()と同じ
        (PreSubmitFGID()がsFID内の全<option>を送信対象にする)。"""
        for fid, name in self.facilities:
            driver.execute_script(
                """
                var select = document.getElementsByName('sFID')[0];
                var fid = arguments[0], name = arguments[1];
                for (var i = 0; i < select.options.length; i++) {
                    if (select.options[i].value === fid) { return; }
                }
                var opt = document.createElement('option');
                opt.value = fid;
                opt.text = name;
                select.add(opt, select.options.length - 1);
                """,
                fid, name
            )

    def _submit_schedule_entry(self, browser, target_url, set_time, max_retries=10, retry_wait=30):
        """ScheduleEntryフォームへの入力〜登録を行う共通処理。
        登録(Entry)押下直後にサイボウズがエラー番号102(「データベースにアクセスが
        集中しています。しばらく経ってから再度アクセスしてください。」)を返すことが
        あるため、その場合はretry_wait秒待ってフォーム読み込みからやり直す。
        ネイティブalert()ではなく通常ページとして返るためbrowser.is_database_busy()で
        page_sourceを見て判定する(browser.wait_elementのTimeoutExceptionには頼らない
        ―"Submit"要素が無いだけの別要因と区別できないため)。"""
        driver = browser.driver

        for attempt in range(max_retries + 1):
            while True:
                try:
                    driver.get(target_url)
                    if set_time:
                        Select(driver.find_element(By.NAME, 'SetTime.Hour')).select_by_visible_text(str(self.start_time.hour) + '時')
                        Select(driver.find_element(By.NAME, 'SetTime.Minute')).select_by_visible_text(str(self.start_time.minute).zfill(2) + '分')
                        Select(driver.find_element(By.NAME, 'EndTime.Hour')).select_by_visible_text(str(self.end_time.hour) + '時')
                        Select(driver.find_element(By.NAME, 'EndTime.Minute')).select_by_visible_text(str(self.end_time.minute).zfill(2) + '分')
                    else:
                        driver.find_element(By.NAME, 'Detail')
                    break

                except:
                    print("Wait for loading page")
                    pass

            driver.find_element(By.NAME, 'Detail').send_keys(self.title)#予定名
            driver.find_element(By.NAME, 'Memo').send_keys(self.id)#uid含む全情報
            self._add_participants(driver)
            self._add_facilities(driver)
            driver.find_element(By.NAME, "Entry").click()

            if browser.is_database_busy():
                if attempt >= max_retries:
                    break
                print(f"サイボウズがデータベース混雑(エラー番号102)を返しました。{retry_wait}秒待って再試行します。({attempt + 1}/{max_retries})")
                import time
                time.sleep(retry_wait)
                continue

            #入力完了まで待機
            browser.wait_element((By.NAME, "Submit"))
            return

        raise DatabaseBusyError(f"'{self.title}'の登録が{max_retries}回リトライしてもサイボウズのデータベース混雑エラー(102)から回復しませんでした。")

    def input_cyboze(self, browser):
        """サイボウズへの入力"""
        status = browser.status
        uid = status.at['CybozeUID', 'value']
        gid = status.at['CybozeGID', 'value']

        date = f'{self.start_time.year}.{self.start_time.month}.{self.start_time.day}'
        terget_url = f'https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=ScheduleEntry&UID={uid}&GID={gid}&Date=da.{date}&cp=sg'

        self._submit_schedule_entry(browser, terget_url, set_time=True)


    def delete_cyboze(self, browser,monitor = False):
        """サイボウズの予定削除"""
        #現在の西暦を取得
        driver = browser.driver
        status = browser.status
        uid = status.at['CybozeUID', 'value']
        gid = status.at['CybozeGID', 'value']

        from datetime import datetime
        date = f'{datetime.now().year}.{datetime.now().month}.{datetime.now().day}'
        terget_url = f'https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=ScheduleSearch&CP=sg&uid={uid}&gid={gid}&date=da.{date}&Text='
        
        while True:
            try:
                if monitor:
                    print(terget_url)
                driver.get(terget_url)
                driver.find_element(By.XPATH, "//input[@type='text'][@class=''][@name='Text']").send_keys(self.id)
                break

            except:
                print("Wait for loading page")
                pass

        select = Select(driver.find_element(By.NAME, "ED.Year"))
        select.select_by_index(len(select.options)-1)
        driver.find_element(By.NAME, "Submit").click()
        #削除
        #参加者・施設が複数ある予定はリンクテキスト末尾に"+"が付くため部分一致で検索する
        #検索結果に見つからない(既に手動削除された等)場合、safe_clickはTimeoutExceptionを
        #投げる。1件見つからないだけで同期全体を止めないよう、警告を出してこのイベントの
        #削除だけスキップする
        from selenium.common.exceptions import TimeoutException
        try:
            browser.safe_click((By.PARTIAL_LINK_TEXT, self.title))
        except TimeoutException:
            print(f"警告: 削除対象「{self.title}」({self.start_time}~{self.end_time})がサイボウズの検索結果に見つからないためスキップします。")
            return
        browser.safe_click((By.LINK_TEXT, '削除する'))
        #参加者が2名以上いる予定は「全参加者の予定を削除する/自分の予定だけ削除する」の
        #選択が必須(未選択のままYesを押すと"条件を選択してください。"のalertで弾かれる)
        #このラジオボタンはCSSで見た目上隠されておりWebDriverの通常クリックでは
        #ElementNotInteractableExceptionになることがあるため safe_click を使う
        member_radios = driver.find_elements(By.CSS_SELECTOR, 'input[name="Member"][value="all"]')
        if member_radios:
            browser.safe_click(member_radios[0])
        browser.safe_click((By.NAME, "Yes"))
        #参加者・施設がある予定を削除するとネイティブalert()が出ることがあるため、あれば閉じる
        from selenium.common.exceptions import NoAlertPresentException
        try:
            driver.switch_to.alert.accept()
        except NoAlertPresentException:
            pass
        #削除完了まで待機
        browser.wait_element((By.LINK_TEXT, "タイムカード"))
    
class AllDay(Event):
    """終日予定"""
    def input_cyboze(self, browser):
        status = browser.status
        uid = status.at['CybozeUID', 'value']
        gid = status.at['CybozeGID', 'value']

        date = f'{self.start_time.year}.{self.start_time.month}.{self.start_time.day}'
        terget_url = f'https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=ScheduleEntry&UID={uid}&GID={gid}&Date=da.' + date + '&cp=sg'

        self._submit_schedule_entry(browser, terget_url, set_time=False)

class MultiDay(Event):
    """複数日予定"""
    def __init__(self, title, st, et, id):
        super().__init__(title, st, et, id)
    def input_cyboze(self, driver):
        """期間予定はサイボウズでcsv出力できないので入力しない。"""
        """または，複数の終日予定に分割？"""
        pass     