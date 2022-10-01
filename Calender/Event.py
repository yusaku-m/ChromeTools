from selenium import webdriver
from selenium.webdriver.support.select import Select
from selenium.webdriver.common.by import By

class Event():
    """予定単体のクラス"""
    def __init__(self, title, st, et, id):
        self.title      = title
        self.start_time = st
        self.end_time   = et
        self.id         = id

    def view(self, id = False):
        print(f'{self.title}, {self.start_time}, {self.end_time}')
        if id:
            print(f'{self.id}') 

    def match(self, event):
        if self.title == event.title and self.start_time == event.start_time and self.end_time == event.end_time and self.id == event.id:
            return True
        else:
            return False

    def input_cyboze(self, driver):
        """サイボウズへの入力"""
        date = f'{self.start_time.year}.{self.start_time.month}.{self.start_time.day}'
        
        driver.get('https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=ScheduleEntry&UID=5791&GID=2100&Date=da.' + date + '&cp=sg')

        Select(driver.find_element(By.NAME, 'SetTime.Hour')).select_by_visible_text(str(self.start_time.hour) + '時')
        Select(driver.find_element(By.NAME, 'SetTime.Minute')).select_by_visible_text(str(self.start_time.minute).zfill(2) + '分')
        Select(driver.find_element(By.NAME, 'EndTime.Hour')).select_by_visible_text(str(self.end_time.hour) + '時')
        Select(driver.find_element(By.NAME, 'EndTime.Minute')).select_by_visible_text(str(self.end_time.minute).zfill(2) + '分')
        driver.find_element(By.NAME, 'Detail').send_keys(self.title)#予定名
        driver.find_element(By.NAME, 'Memo').send_keys(self.id)#uid含む全情報
        driver.find_element(By.NAME, "Entry").click()

    def delete_cyboze(self, driver):
        """サイボウズの予定削除"""
        #現在の西暦を取得
        from datetime import datetime
        date = f'{datetime.now().year}.{datetime.now().month}.{datetime.now().day}'
        driver.get("https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=ScheduleSimpleSearch&CP=sg&uid=5791&gid=2100&date=da." + date + "&Text=" + self.id)
        driver.find_element(By.LINK_TEXT, self.title).click()
        driver.find_element(By.LINK_TEXT, '削除する').click()
        driver.find_element(By.NAME, "Yes").click()

class AllDay(Event):
    """終日予定"""
    def input_cyboze(self, driver):
        date = f'{self.start_time.year}.{self.start_time.month}.{self.start_time.day}'
        driver.get('https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=ScheduleEntry&UID=5791&GID=2100&Date=da.' + date + '&cp=sg')
        driver.find_element(By.NAME, 'Detail').send_keys(self.title)#予定名
        driver.find_element(By.NAME, 'Memo').send_keys(self.id)#uid含む全情報
        driver.find_element(By.NAME, "Entry").click()

class MultiDay(Event):
    """複数日予定"""
    def __init__(self, title, st, et, id):
        super().__init__(title, st, et, id)
    def input_cyboze(self, driver):
        """期間予定はサイボウズでcsv出力できないので入力しない。"""
        pass     