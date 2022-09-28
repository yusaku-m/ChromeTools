import os
import pandas as pd
import pickle

class Browser:
    def __init__(self, userdata_path):
        """userdata_pathはedge://version/の「Profile path」を使用すると保存しているパスワードが有効に"""
        #初期設定
        self.driver_path = "./Edge/msedgedriver.exe"
        from msedge.selenium_tools import Edge, EdgeOptions

        #バージョンの確認,Edgeが更新されていればドライバを更新
        self.check_driver_version()
        options = EdgeOptions()
        options.use_chromium = True
        #options.add_argument('--headless')  #非表示で起動（するとパスワード自動入力が使用できない。）
        options.add_argument(f'--user-data-dir={userdata_path}')
        options.add_argument('--profile-directory=Default')#ユーザーとして起動（パスワード自動入力のため）
        options.add_argument("--remote-debugging-port=9222") 
        options.add_argument('--lang=en')
        #ダウンロード先を変更
        options.add_experimental_option('prefs', {'download.default_directory': os.getcwd()})
        options.add_experimental_option('excludeSwitches', ['enable-logging']) #エラー非表示
        #ドライバの読み込み
        driver = Edge(executable_path = self.driver_path, options=options)
        #driver.maximize_window()
        #タイムアウト設定
        driver.set_page_load_timeout(120)
        driver.implicitly_wait(10) #要素が見つかるまで待つ時間
        self.driver = driver
        
    def check_driver_version(self):
        """ドライバの自動更新"""
        #Edgeバージョンの確認
        import winreg
        path = r"SOFTWARE\Microsoft\Edge\BLBeacon"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
        data, regtype = winreg.QueryValueEx(key, 'version')
        winreg.CloseKey(key) 

        #現状ステータスの読み込み
        import pandas as pd
        status = self.open_status()
        print('Check Edge version...')

        #ドライババージョンと比較
        if 'Edge_Version' in status.index and data == status.at['Edge_Version', 'value']:
            #更新不要
            print(f'Your edge is latest verion ({data}).')
            return
        else:
            #更新
            print(f'Your edge is updeted. Driver update is needed to version {data}.')
            self.update_driver(data)

    def update_driver(self, terget_version):
        """ドライバの自動更新"""
        #既存ドライバの削除
        url = f"https://msedgedriver.azureedge.net/{terget_version}/edgedriver_win64.zip"
        filename = self.driver_path
        zipname = "./Edge/edgedriver_win64.zip"
        if os.path.isfile(filename)==True:
            os.remove(filename)

        #最新ドライバの取得(zip)        
        import requests
        urlData = requests.get(url).content
        with open(zipname ,mode='wb') as f: # wb でバイト型を書き込める
             f.write(urlData)
        #解凍
        import zipfile
        zfile = zipfile.ZipFile(zipname)
        zfile.extractall("./Edge")
        zfile.close()

        #不要ファイルの削除
        os.remove(zipname)
        import shutil
        shutil.rmtree("./Edge/Driver_Notes/")

        #更新バージョンをステータスに反映
        import pandas as pd
        status = self.open_status()
        
        if 'Edge_Version' in status.index:
            status.at['Edge_Version', 'value'] = terget_version
        else:
            df = pd.DataFrame(terget_version, index = ['Edge_Version'], columns=['value'])
            status = pd.concat([status, df])
            self.save_status(status)
             
    def open_status(self):
        #現状ステータスの読み込み
        if os.path.isfile('./Edge/status.binaryfile') == True:
            with open(f'./Edge/status.binaryfile','rb') as f:
                status = pickle.load(f)
        else:
            cols = ['value']
            status = pd.DataFrame(index=[], columns=cols)
            with open(f'./Edge/status.binaryfile','wb') as f:
                pickle.dump(status, f) 
        return status

    def save_status(self, status):
        import pickle
        with open(f'./Edge/status.binaryfile','wb') as f:
            pickle.dump(status, f) 

    def close(self):
        self.driver.quit()