import os
import pandas as pd
import pickle
from pyautogui import sleep

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import chromedriver_binary

class Browser:
    """ブラウザ操作クラス"""
    def __init__(self, userdata_path):
        """userdata_pathはChrome://version/の「Profile path」を使用すると保存しているパスワードが有効に"""
        #初期設定
        self.driver_path = "./Chrome/Chromedriver.exe"
        self.open_status()
        self.userdata_path = userdata_path
        
        options = Options()
        options.add_argument("disable-infobars")
        options.add_argument('--lang=en')
        options.add_argument(f'--user-data-dir={self.userdata_path}')
        options.add_argument('--profile-directory=Default') #ユーザーとして起動（パスワード自動入力のため）
        options.add_argument("--remote-debugging-port=9222") 

        #ダウンロード先を変更
        options.add_experimental_option('prefs', {'download.default_directory': f"{os.getcwd()}\\data"})
        options.add_experimental_option('excludeSwitches', ['enable-logging']) #エラー非表示
        #ドライバの読み込み
        driver = webdriver.Chrome(options=options)
        #driver.maximize_window()
        #タイムアウト設定
        driver.set_page_load_timeout(120)
        driver.implicitly_wait(10) #要素が見つかるまで待つ時間
        self.driver = driver
        

    def open_status(self):
        """現状ステータスの読み込み"""
        if os.path.isfile('./Chrome/status.binaryfile') == True:
            with open(f'./Chrome/status.binaryfile','rb') as f:
                self.status = pickle.load(f)
        else:
            self.status = pd.DataFrame(index=[], columns=['value'])
            with open(f'./Chrome/status.binaryfile','wb') as f:
                pickle.dump(self.status, f) 

    def set_status(self, index_name, value):
        if index_name in self.status.index:
            self.status.at[index_name, 'value'] = value
        else:
            df = pd.DataFrame(value, index = [index_name], columns=['value'])
            self.status = pd.concat([self.status, df])
            self.save_status()

    def save_status(self):
        import pickle
        with open(f'./Chrome/status.binaryfile','wb') as f:
            pickle.dump(self.status, f) 

    def set_id(self):
        """各サイトのidをセット"""
        pass

    def wait_element(self, element):
        driver = self.driver
        #入力完了まで待機
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.wait import WebDriverWait
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located(element))

    def wait_download(self):
        import glob
        n = 1
        while n != 0:
            print('waiting download...')
            import time
            time.sleep(2)
            n = 0
            import os
            for download_fileName in glob.glob(f'{os.getcwd()}/*.*'):
                extension = os.path.splitext(download_fileName)
                if '.crdownload' in extension:
                    n += 1 
    def close(self, initialize = 0):
        self.driver.quit()
        if initialize==1:
            options = Options()
            options.add_argument("disable-infobars")
            options.add_argument('--lang=en')
            options.add_argument('--profile-directory=Default') #ユーザーとして起動（パスワード自動入力のため）
            options.add_argument("--remote-debugging-port=9222") 

            #ダウンロード先を元に戻す
            import getpass
            options.add_argument(f'--user-data-dir={self.userdata_path}')
            options.add_experimental_option('prefs', {'download.default_directory': f"Downloads"})
            options.add_experimental_option('excludeSwitches', ['enable-logging']) #エラー非表示
            #ドライバの読み込み
            driver = webdriver.Chrome(options=options)
            #タイムアウト設定
            
            driver.quit()
