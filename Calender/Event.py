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

    def input_cyboze(self, browser):
        """サイボウズへの入力"""
        driver = browser.driver
        status = browser.status
        uid = status.at['CybozeUID', 'value']
        gid = status.at['CybozeGID', 'value']

        date = f'{self.start_time.year}.{self.start_time.month}.{self.start_time.day}'
        
        driver.get(f'https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=ScheduleEntry&UID={uid}&GID={gid}&Date=da.{date}&cp=sg')

        Select(driver.find_element(By.NAME, 'SetTime.Hour')).select_by_visible_text(str(self.start_time.hour) + '時')
        Select(driver.find_element(By.NAME, 'SetTime.Minute')).select_by_visible_text(str(self.start_time.minute).zfill(2) + '分')
        Select(driver.find_element(By.NAME, 'EndTime.Hour')).select_by_visible_text(str(self.end_time.hour) + '時')
        Select(driver.find_element(By.NAME, 'EndTime.Minute')).select_by_visible_text(str(self.end_time.minute).zfill(2) + '分')
        driver.find_element(By.NAME, 'Detail').send_keys(self.title)#予定名
        driver.find_element(By.NAME, 'Memo').send_keys(self.id)#uid含む全情報
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
        driver.find_element(By.LINK_TEXT, self.title).click()
        driver.find_element(By.LINK_TEXT, '削除する').click()
        driver.find_element(By.NAME, "Yes").click()
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
        driver.get(f'https://cybozu.da.kagawa-nct.ac.jp/scripts/cbag/ag.exe?page=ScheduleEntry&UID={uid}&GID={gid}&Date=da.' + date + '&cp=sg')
        driver.find_element(By.NAME, 'Detail').send_keys(self.title)#予定名
        driver.find_element(By.NAME, 'Memo').send_keys(self.id)#uid含む全情報
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