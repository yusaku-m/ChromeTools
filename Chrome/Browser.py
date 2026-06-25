import os
import pandas as pd
import pickle
import time
import psutil
from selenium import webdriver

class Browser:
    """ブラウザ操作クラス"""
    def __init__(self, userdata_path):
        # 初期設定
        print("1. Terminating existing Chrome processes...")
        self.terminate_chrome_processes()
        
        print("2. Opening status file...")
        self.open_status()
        self.userdata_path = userdata_path
        
        print("3. Setting up Chrome options...")
        options = webdriver.ChromeOptions()
        options.add_argument("--remote-allow-origins=*")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("disable-infobars")
        options.add_argument('--lang=ja-JP')
        
        # ユーザーデータディレクトリの正規化
        clean_path = os.path.normpath(self.userdata_path)
        options.add_argument(f'--user-data-dir={clean_path}')
        options.add_argument('--profile-directory=Default') 
        options.add_argument('--disable-gpu')
        
        # ログを詳細に出力するように設定
        # options.add_argument("--verbose")
    
        # ダウンロード先設定
        options.add_experimental_option('prefs', {
            'download.default_directory': os.path.join(os.getcwd(), "data"),
            'download.directory_upgrade': True,
            'download.prompt_for_download': False,
            'safebrowsing.enabled': True
        })        
        
        try:
            print(f"4. Starting WebDriver with profile: {clean_path}")
            print("   (This might take a few seconds if it's downloading a driver...)")
            
            # Selenium 4.6以降の標準機能（Selenium Manager）に任せる
            # webdriver-manager を介さず直接起動を試みる
            start_time = time.time()
            self.driver = webdriver.Chrome(options=options)
            end_time = time.time()
            
            print(f"5. Driver loaded successfully! (Time taken: {end_time - start_time:.2f}s)")
        except Exception as e:
            print(f"FAILED to load driver: {e}")
            raise e

        self.driver.set_page_load_timeout(120)
        self.driver.implicitly_wait(10)

    def terminate_chrome_processes(self):
        """Chromeのプロセスを完全に終了させる"""
        count = 0
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            try:
                if 'chrome' in proc.info['name'].lower():
                    proc.kill()
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        if count > 0:
            print(f"   Killed {count} Chrome processes.")
        time.sleep(2)

    def open_status(self):
        """現状ステータスの読み込み"""
        status_file = './Chrome/status.binaryfile'
        if os.path.isfile(status_file):
            with open(status_file, 'rb') as f:
                self.status = pickle.load(f)
        else:
            self.status = pd.DataFrame(index=[], columns=['value'])
            self.save_status()

    def save_status(self):
        with open('./Chrome/status.binaryfile', 'wb') as f:
            pickle.dump(self.status, f)

    def wait_element(self, element):
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.wait import WebDriverWait
        wait = WebDriverWait(self.driver, 20)
        wait.until(EC.presence_of_element_located(element))

    def wait_download(self):
        import glob
        download_dir = os.path.join(os.getcwd(), "data")
        print(f'Waiting for download in {download_dir}...')
        time.sleep(2)
        while True:
            downloading_files = glob.glob(os.path.join(download_dir, "*.crdownload"))
            if not downloading_files:
                print('Download finished.')
                break
            time.sleep(2)

    def close(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

if __name__ == "__main__":
    user_data_path = "C:/Users/Yusaku/AppData/Local/Google/Chrome/User Data/"
    browser = Browser(user_data_path)
    browser.driver.get('https://www.google.com/')
    time.sleep(5)
    browser.close()
