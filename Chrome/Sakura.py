from .Browser import Browser
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
import pandas

class Sakura(Browser):
    def __init__(self, userdata_path):
        super().__init__(userdata_path)
        self.driver.get('https://www.390390.jp/admin/login?ENV_CODE=webasp3') 
        self.wait_element((By.CLASS_NAME, 'work_btn'))

        #ログイン
        print("login...")
        self.driver.find_element(By.CLASS_NAME, 'work_btn').click()

    def make_mail(self, message):
        print("make mail...")
        self.driver.get('https://www.390390.jp/admin/main') 
        self.wait_element((By.LINK_TEXT, 'メッセージ作成'))
        self.driver.find_element(By.LINK_TEXT, 'メッセージ作成').click()

        self.wait_element((By.CLASS_NAME, 'message.work_btn'))
        self.driver.find_element(By.CLASS_NAME, 'message.work_btn').click()

        #メッセージ入力
        self.driver.find_element(By.ID, 'txtSubject').send_keys(message.title)
        self.driver.find_element(By.ID, 'txtaBody').send_keys(message.text)

        #送信者の選択
        self.driver.find_elements(By.CLASS_NAME, "work_btn.work_next.rightbtn")[1].click()
        self.driver.find_element(By.XPATH, '//div[text()="個人から選ぶ"]').click()
        self.driver.find_elements(By.CLASS_NAME, "work_btn.work_add.small")[2].click()

        Select(self.driver.find_element(By.ID, 'cmbAccountSearchAff')).select_by_visible_text('　高松キャンパス(全員)')

        for to in message.to:
            self.driver.find_element(By.XPATH, f"//*[@data-name='{to}']").click()

        self.driver.find_elements(By.CLASS_NAME, "work_btn.work_add.rightbtn")[0].click()
        self.driver.find_elements(By.CLASS_NAME, "work_btn.work_next.rightbtn")[3].click()

        #送信設定
        self.driver.find_element(By.XPATH, '//div[text()="設定"]').click()
        self.driver.find_element(By.XPATH, f"//*[@for='rdoInsertAccountName_ON']").click()
        self.driver.find_element(By.XPATH, "//*[@onclick='MsgEditWorker.DefineOptionDialog()']").click()
        print("mail maked")        



class Message():
    def __init__(self):
        self.title = ""
        self.text = ""
        self.to = []
        self.datetime = ""

    def get_data_from_excel(self, excelpath, sheetname):
        """エクセルから文章データを取得"""
        print("get mail data...")
        df = pandas.read_excel(excelpath, sheetname)

        self.title = df['表題'][0]
        self.text = df['本文'][0]
        self.to = df['対象者']


if __name__ == "__main__":
    print("test")

    excelpath = r"C:\Users\Yusaku\OneDrive - 独立行政法人 国立高等専門学校機構\Work\講義\そのた科目\さくら連絡網.xlsx"
    sheetname = r"出力"

    message = Message()
    message.get_data_from_excel(excelpath, sheetname)

    user_data_path = "C:/Users/Yusaku/AppData/Local/Google/Chrome/User Data/"
    sakura = Sakura(user_data_path)

    sakura.make_mail(message)

    
