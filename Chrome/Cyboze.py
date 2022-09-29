from Chrome.Browser import Browser
from selenium.webdriver.common.by import By

class Cyboze(Browser):
    def login(self):
        self.driver.get('https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?')

        import os
        import pandas as pd

        self.open_status()
        name = self.status.at['氏名', 'value']
        dep =  self.status.at['学科', 'value']
        self.driver.find_element(By.LINK_TEXT, "切り替える").click()
        from selenium.webdriver.support.select import Select
        Select(self.driver.find_element(By.NAME, 'Group')).select_by_visible_text(dep)
        self.driver.find_element(By.NAME, "Submit").click()
        Select(self.driver.find_element(By.NAME, '_ID')).select_by_visible_text(name)
        self.driver.find_element(By.NAME, "Submit").click()

    def set_id(self, name , department):
        self.open_status()
        self.set_status('氏名', name)
        self.set_status('学科', department)
        self.save_status()

    def begin_work(self):
        self.driver.get('https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=AGIndex')

        try:
            self.driver.find_element_by_name("PIn").click()
        except:
            pass
        element = self.driver.find_element_by_css_selector(".borderTable.vr_portletBd2")
        if '出社' in element.text:
            begintime = element.text.split('出社\n')[1].split(' ')[0]
            print('本日は' + begintime + 'に出勤')
        else:
            print('出勤時間の取得に失敗')

    def finish_work(self):
        driver = self.driver
        driver.get('https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=AGIndex')
        try:
            driver.find_element_by_name("POut").click()
        except:
            pass
        element = driver.find_element_by_css_selector(".borderTable.vr_portletBd2")
        if '退社' in element.text:
            finishtime = element.text.split('退社\n')[1].split(' ')[0]
            print('本日は' + finishtime + 'に退勤')
        else:
            finishtime = ''
            print('退勤時間の取得に失敗')

    def get_calender(self):
        driver = self.driver
        driver.get('https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=PersonalScheduleExport')
        #現在の西暦を取得
        import datetime
        ThisYear = datetime.date.today().year
        ThisMonth = datetime.date.today().month
        #今月から1年後までを選択
        from selenium.webdriver.support.select import Select
        #古いカレンダーを削除したいときに検索範囲に含める
        #Select(driver.find_element_by_name('SetDate.Year')).select_by_visible_text('1997年')
        #Select(driver.find_element_by_name('SetDate.Month')).select_by_visible_text('1月')
        #10年後までを選択
        Select(driver.find_element(By.NAME, 'EndDate.Year')).select_by_visible_text(str(ThisYear + 7) + '年')
        Select(driver.find_element(By.NAME, 'EndDate.Month')).select_by_visible_text(str(ThisMonth + 1) + '月')
        #ダウンロード
        driver.find_element(By.NAME, "Export").click()
        self.wait_download()

        #ファイルの削除
        import shutil
        import os
        self.calenderpath = os.getcwd() + '/CybozeSchedule.csv'
        shutil.move('schedule.csv', self.calenderpath)   

    def input_schedule(self, calender):
        from tqdm import tqdm
        for event in tqdm(calender.events, desc='予定入力中'):
            event.input_cyboze(self.browser)

    def delete_schedule(self, calender):
        from tqdm import tqdm
        for event in tqdm(calender.events, desc='予定削除中'):
            event.delete_cyboze(self.browser)
