import os
import pandas as pd
import pickle
from pyautogui import sleep

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import chromedriver_binary
import psutil

class Browser:
    """ブラウザ操作クラス"""
    def __init__(self, userdata_path):
        #ドライバーのアップデートチェック
        import subprocess
        subprocess.run(["pip", "install", "chromedriver-binary-auto"], check=True)

        """userdata_pathはChrome://version/の「Profile path」を使用すると保存しているパスワードが有効に"""
        #初期設定
        self.driver_path = "./Chrome/Chromedriver.exe"
        self.terminate_chrome_processes()  # Chromeのプロセスを終了する処理を追加
        self.open_status()
        self.userdata_path = userdata_path
        
        options = Options()
        options.add_argument("disable-infobars")
        options.add_argument('--lang=en')
        options.add_argument(f'--user-data-dir={self.userdata_path}')
        options.add_argument('--profile-directory=Default') #ユーザーとして起動（パスワード自動入力のため）
        options.add_argument("--remote-debugging-port=9222") 

        # ダウンロード先を変更
        options.add_experimental_option('prefs', {
            'download.default_directory': f"{os.getcwd()}\\data",
            'download.directory_upgrade': True,  # 既存のダウンロード先をアップグレード
            'download.prompt_for_download': False,  # ダウンロード確認ダイアログを無効化
            'safebrowsing.enabled': True  # セーフブラウジングを有効にして、セキュリティ警告を無効に
        })        
        
        options.add_experimental_option('excludeSwitches', ['enable-logging']) #エラー非表示
        
        #ドライバの読み込み
        while True:
            try:
                print("Driver loading...")
                driver = webdriver.Chrome(options=options)
                print("OK.")
                break
            except:
                sleep(1)
        #driver.maximize_window()
        #タイムアウト設定
        driver.set_page_load_timeout(120)
        driver.implicitly_wait(10) #要素が見つかるまで待つ時間
        self.driver = driver

    def terminate_chrome_processes(self):
        """手動で開かれているChromeのプロセスを終了"""
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            try:
                # プロセス名がchromeの場合
                if 'chrome' in proc.info['name'].lower():
                    proc.terminate()  # プロセスを終了
                    print(f"Terminated Chrome process with PID {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

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
