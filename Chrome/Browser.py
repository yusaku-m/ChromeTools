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
        self.userdata_path = userdata_path
        print("1. Terminating existing Chrome processes...")
        self.terminate_chrome_processes()

        print("2. Opening status file...")
        self.open_status()
        
        print("3. Setting up Chrome options...")
        options = webdriver.ChromeOptions()
        options.add_argument("--remote-allow-origins=*")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("disable-infobars")
        options.add_argument('--lang=ja-JP')
        options.add_argument('--disable-gpu')

        # 強制終了後の「クラッシュ復元ダイアログ」でハングするのを防ぐ
        options.add_argument('--no-first-run')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-default-apps')
        options.add_argument('--hide-crash-restore-bubble')

        # Seleniumによる自動化をGoogleに検知させないための設定
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features=AutomationControlled")

        # ユーザーデータディレクトリの正規化
        clean_path = os.path.normpath(self.userdata_path)
        options.add_argument(f'--user-data-dir={clean_path}')
        options.add_argument('--profile-directory=Default')
        
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
        """自動化プロファイルを使用しているChromeプロセスのみ終了させる"""
        clean_path = os.path.normpath(self.userdata_path).lower()
        count = 0
        for proc in psutil.process_iter(attrs=['pid', 'name', 'cmdline']):
            try:
                if 'chrome' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info.get('cmdline') or [])
                    if clean_path in cmdline.lower():
                        proc.kill()
                        count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        if count > 0:
            print(f"   Killed {count} Chrome processes (for automation profile).")
        else:
            print("   No automation-profile Chrome processes found.")
        time.sleep(2)

        # プロセス終了後に残るロックファイルを削除
        for lock_name in ['lockfile', 'SingletonLock', 'SingletonCookie']:
            lock_path = os.path.join(self.userdata_path, lock_name)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                    print(f"   Removed lock file: {lock_name}")
                except Exception as e:
                    print(f"   Could not remove {lock_name}: {e}")

    def open_status(self):
        """現状ステータスの読み込み"""
        status_file = './Chrome/status.binaryfile'
        if os.path.isfile(status_file):
            with open(status_file, 'rb') as f:
                self.status = pickle.load(f)
        else:
            self.status = pd.DataFrame(index=[], columns=['value'])
            self.save_status()

    def set_status(self, key, value):
        self.status.at[key, 'value'] = value

    def save_status(self):
        with open('./Chrome/status.binaryfile', 'wb') as f:
            pickle.dump(self.status, f)

    def wait_element(self, element):
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.wait import WebDriverWait
        wait = WebDriverWait(self.driver, 20)
        wait.until(EC.presence_of_element_located(element))

    def wait_for_manual_step(self, ready_check, description="操作", poll_interval=5, status_interval=60, timeout_hours=None):
        """OSダイアログ(Windows Hello等)の手動入力待ちなど、時間の読めない待機に使う。
        ready_check() が True を返すまでポーリングし続ける。"""
        start = time.time()
        last_status = start
        while True:
            try:
                if ready_check():
                    break
            except Exception:
                pass
            now = time.time()
            if now - last_status >= status_interval:
                print(f"{description}の完了をお待ちしています…(経過 {int((now - start) / 60)}分)")
                last_status = now
            if timeout_hours is not None and now - start > timeout_hours * 3600:
                raise TimeoutError(f"{description}が{timeout_hours}時間以内に完了しませんでした。")
            time.sleep(poll_interval)

    def patient_get(self, url, description="ページの読み込み"):
        """driver.get()がpage_load_timeoutで例外を出しても諦めず、
        実際にページが準備できるまで待つ。Windows HelloのPINダイアログ等で
        ナビゲーションがブロックされるケースに対応するため。"""
        from selenium.common.exceptions import TimeoutException
        try:
            self.driver.get(url)
        except TimeoutException:
            print(f"{description}が既定時間内に終わりませんでした。手動操作(PIN入力等)待ちの可能性があります。")

        domain = url.split('/')[2] if '//' in url else url

        def _ready():
            state = self.driver.execute_script('return document.readyState')
            return state == 'complete' and domain in self.driver.current_url

        self.wait_for_manual_step(_ready, description=description)

    def wait_download(self, timeout_start=15):
        import glob
        download_dir = os.path.join(os.getcwd(), "data")

        # まずダウンロード開始（.crdownload出現）を最大timeout_start秒待つ
        # ダウンロードが既に始まっている・または高速完了した場合は即抜け
        deadline = time.time() + timeout_start
        while time.time() < deadline:
            if glob.glob(os.path.join(download_dir, "*.crdownload")):
                break
            time.sleep(0.5)
        else:
            print('Download appears to have completed already (no .crdownload found).')
            return

        # .crdownloadが消えるまで待つ（完了）
        print('Download in progress...')
        while glob.glob(os.path.join(download_dir, "*.crdownload")):
            time.sleep(0.5)
        print('Download finished.')

    def close(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

if __name__ == "__main__":
    user_data_path = "C:/Users/Yusaku/AppData/Local/Google/Chrome/User Data/"
    browser = Browser(user_data_path)
    browser.driver.get('https://www.google.com/')
    time.sleep(5)
    browser.close()
