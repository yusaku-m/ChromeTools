from selenium import webdriver
from selenium.webdriver.support.select import Select

from selenium.webdriver.common.by import By

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
        if self.title == event.title and self.start_time == event.start_time and self.end_time == event.end_time and self.id == event.id:
            return True
        else:
            return False

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

    def input_cyboze(self, browser):
        """サイボウズへの入力"""
        driver = browser.driver
        status = browser.status
        uid = status.at['CybozeUID', 'value']
        gid = status.at['CybozeGID', 'value']

        date = f'{self.start_time.year}.{self.start_time.month}.{self.start_time.day}'
        terget_url = f'https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=ScheduleEntry&UID={uid}&GID={gid}&Date=da.{date}&cp=sg'

        while True:
            try:
                driver.get(terget_url)
                Select(driver.find_element(By.NAME, 'SetTime.Hour')).select_by_visible_text(str(self.start_time.hour) + '時')
                Select(driver.find_element(By.NAME, 'SetTime.Minute')).select_by_visible_text(str(self.start_time.minute).zfill(2) + '分')
                Select(driver.find_element(By.NAME, 'EndTime.Hour')).select_by_visible_text(str(self.end_time.hour) + '時')
                Select(driver.find_element(By.NAME, 'EndTime.Minute')).select_by_visible_text(str(self.end_time.minute).zfill(2) + '分')
                break

            except:
                print("Wait for loading page")
                pass


        driver.find_element(By.NAME, 'Detail').send_keys(self.title)#予定名
        driver.find_element(By.NAME, 'Memo').send_keys(self.id)#uid含む全情報
        self._add_participants(driver)
        self._add_facilities(driver)
        driver.find_element(By.NAME, "Entry").click()
        #入力完了まで待機
        browser.wait_element((By.NAME, "Submit"))


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
        browser.safe_click((By.PARTIAL_LINK_TEXT, self.title))
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
        driver = browser.driver
        status = browser.status
        uid = status.at['CybozeUID', 'value']
        gid = status.at['CybozeGID', 'value']

        date = f'{self.start_time.year}.{self.start_time.month}.{self.start_time.day}'
        terget_url = f'https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=ScheduleEntry&UID={uid}&GID={gid}&Date=da.' + date + '&cp=sg'

        while True:
            try:
                driver.get(terget_url)
                detail_field = driver.find_element(By.NAME, 'Detail')
                break

            except:
                print("Wait for loading page")
                pass

        detail_field.send_keys(self.title)#予定名
        driver.find_element(By.NAME, 'Memo').send_keys(self.id)#uid含む全情報
        self._add_participants(driver)
        self._add_facilities(driver)
        driver.find_element(By.NAME, "Entry").click()

        browser.wait_element((By.NAME, "Submit"))

class MultiDay(Event):
    """複数日予定"""
    def __init__(self, title, st, et, id):
        super().__init__(title, st, et, id)
    def input_cyboze(self, driver):
        """期間予定はサイボウズでcsv出力できないので入力しない。"""
        """または，複数の終日予定に分割？"""
        pass     