from Chrome.Browser import Browser
from selenium.webdriver.common.by import By
import os
import pandas as pd
import shutil
import datetime
from selenium.webdriver.support.select import Select

class Cyboze(Browser):
    def login(self):
        print("Logging into Cybozu...")
        login_url = 'https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?'
        self.patient_get(login_url, description="Cybozuログイン(PIN入力)")

        self.open_status()
        name = self.status.at['氏名', 'value']
        dep =  self.status.at['学科', 'value']
        
        try:
            # 「切り替える」リンクがあるか確認
            links = self.driver.find_elements(By.LINK_TEXT, "切り替える")
            if links:
                links[0].click()
                Select(self.driver.find_element(By.NAME, 'Group')).select_by_visible_text(dep)
                self.driver.find_element(By.NAME, "Submit").click()
                Select(self.driver.find_element(By.NAME, '_ID')).select_by_visible_text(name)
                self.driver.find_element(By.NAME, "Submit").click()
                print(f"Logged in as {name}.")
            else:
                print("Skip login steps or already at user selection page.")
        except Exception as e:
            print(f"Login process might have failed or skipped: {e}")

    def set_id(self, name, uid, department, gid):
        self.open_status()
        self.set_status('氏名', name)
        self.set_status('学科', department)
        self.set_status('CybozeUID', uid)
        self.set_status('CybozeGID', gid)
        self.save_status()

    def begin_work(self):
        self.driver.get('https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=AGIndex')

        try:
            self.driver.find_element(By.NAME, "PIn").click()
        except:
            pass
        element = self.driver.find_element(By.CSS_SELECTOR, ".borderTable.vr_portletBd2")
        if '出社' in element.text:
            begintime = element.text.split('出社\n')[1].split(' ')[0]
            print('本日は' + begintime + 'に出勤')
        else:
            print('出勤時間の取得に失敗')

    def finish_work(self):
        driver = self.driver
        driver.get('https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=AGIndex')
        try:
            driver.find_element(By.NAME, "POut").click()
        except:
            pass
        element = driver.find_element(By.CSS_SELECTOR, ".borderTable.vr_portletBd2")
        if '退社' in element.text:
            finishtime = element.text.split('退社\n')[1].split(' ')[0]
            print('本日は' + finishtime + 'に退勤')
        else:
            finishtime = ''
            print('退勤時間の取得に失敗')

    def get_calender(self):
        print("Exporting Cybozu schedule...")
        driver = self.driver
        # wait_forでEndDate.Yearの実在を確認するまで待つ。domain+readyStateだけの
        # 判定だとWindows HelloのPIN入力待ちで前ページのままなのに「準備完了」と
        # 誤判定してしまい、この直後のfind_elementがNoSuchElementExceptionになる
        # ことがあったため(PIN未入力の状態で再現済み)。
        self.patient_get('https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=PersonalScheduleExport', description="Cybozu予定エクスポート画面(PIN入力待ちの可能性)", wait_for=(By.NAME, 'EndDate.Year'))

        # 開始日を選べるだけ過去にする(音楽練習室カレンダーは同期範囲を無制限にするため、
        # 過去に自動入力済みの予定もccal側で照合できるようにしたい。フォームにフィールドが
        # 無い/名前が違う場合は何もしない)
        try:
            start_year_select = Select(driver.find_element(By.NAME, 'StartDate.Year'))
            start_year_select.select_by_index(0)
            Select(driver.find_element(By.NAME, 'StartDate.Month')).select_by_visible_text('1月')
        except Exception:
            pass

        # 10年後までを選択
        select = Select(driver.find_element(By.NAME, 'EndDate.Year'))
        select.select_by_index(len(select.options)-1)
        
        ThisMonth = datetime.date.today().month
        NextMonth = ThisMonth % 12 + 1  # 12月→1月になるのを防ぐ
        Select(driver.find_element(By.NAME, 'EndDate.Month')).select_by_visible_text(str(NextMonth) + '月')
        
        # ダウンロード
        print("Clicking export button...")
        driver.find_element(By.NAME, "Export").click()
        self.wait_download()

        # ファイルの移動
        dest_path = os.path.join(os.getcwd(), 'data', 'CybozeSchedule.csv')
        src_path = os.path.join(os.getcwd(), 'data', 'schedule.csv')
        
        if os.path.exists(src_path):
            if os.path.exists(dest_path):
                os.remove(dest_path)
            shutil.move(src_path, dest_path)
            print(f"Cybozu schedule exported to {dest_path}")
        else:
            # ブラウザのデフォルトダウンロード先も確認
            home_download = os.path.join(os.path.expanduser('~'), 'Downloads', 'schedule.csv')
            if os.path.exists(home_download):
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                shutil.move(home_download, dest_path)
                print(f"Cybozu schedule found in Downloads and moved to {dest_path}")
            else:
                print(f"Error: schedule.csv not found in {src_path} or {home_download}")

    def input_schedule(self, calender):
        from tqdm import tqdm
        for event in tqdm(calender.events, desc='予定入力中'):
            event.input_cyboze(self)

    def delete_schedule(self, calender):
        from tqdm import tqdm
        for event in tqdm(calender.events, desc='予定削除中'):
            event.delete_cyboze(self)
