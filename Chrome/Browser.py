import os
import pandas as pd
import pickle

class Browser:
    """ブラウザ操作クラス"""
    def __init__(self, userdata_path):
        """userdata_pathはChrome://version/の「Profile path」を使用すると保存しているパスワードが有効に"""
        #初期設定
        self.driver_path = "./Chrome/Chromedriver.exe"
        self.open_status()

        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        
        #バージョンの確認,Chromeが更新されていればドライバを更新
        options = Options()
        options.add_argument("disable-infobars")
        options.add_argument('--lang=en')
        options.add_argument(f'--user-data-dir={userdata_path}')
        options.add_argument('--profile-directory=Default')#ユーザーとして起動（パスワード自動入力のため）
        options.add_argument("--remote-debugging-port=9222") 

        #ダウンロード先を変更
        options.add_experimental_option('prefs', {'download.default_directory': f"{os.getcwd()}\\data"})
        options.add_experimental_option('excludeSwitches', ['enable-logging']) #エラー非表示
        #ドライバの読み込み
        driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
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
    def close(self):
        self.driver.quit()