import os
from Chrome.Browser import Browser
from selenium.webdriver.common.by import By

class GoogleCalender(Browser):
    def get_calender(self):
        import time, zipfile, glob
        EXPORT_URL = 'https://calendar.google.com/calendar/u/0/exporticalzip'
        id_val = self.status.at['googleID', 'value']
        download_dir = os.path.join(os.getcwd(), "data")
        zip_pattern = os.path.join(download_dir, f"{id_val}@gmail.com.ical*.zip")

        # 古いicalzipを削除（コピー番号付きも含む）
        for old in glob.glob(zip_pattern):
            os.remove(old)
            print(f"  Removed old zip: {os.path.basename(old)}")

        print("Accessing Google Calendar export URL...")
        self.driver.get(EXPORT_URL)
        time.sleep(3)

        current = self.driver.current_url
        print(f"  Current URL: {current}")

        # chrome:// = ダウンロード開始済み（ログイン済み）
        # accounts.google.com や calendar 以外 = ログインが必要
        download_started = current.startswith('chrome://')
        is_login_page = (not download_started) and (
            'accounts.google.com' in current or 'calendar.google.com' not in current
        )

        if is_login_page:
            print("\n【Googleログインが必要です】")
            print(f"Chromeウィンドウで {id_val}@gmail.com にログインしてください。")
            print("ログイン完了後、自動的にエクスポートが始まります（最大5分待機）...")
            deadline = time.time() + 300
            while time.time() < deadline:
                time.sleep(2)
                url = self.driver.current_url
                if 'calendar.google.com' in url and 'accounts.google.com' not in url:
                    print("ログイン確認。エクスポートを再実行します...")
                    time.sleep(2)
                    self.driver.get(EXPORT_URL)
                    break
            else:
                raise TimeoutError("5分以内にGoogleログインが完了しませんでした。")

        self.wait_download()

        # コピー番号付きのファイルも含めて最新のzipを探す
        zip_files = sorted(glob.glob(zip_pattern), key=os.path.getmtime, reverse=True)
        if not zip_files:
            raise FileNotFoundError(f"Google Calendar export zip not found. (pattern: {zip_pattern})")

        zip_path = zip_files[0]
        extract_path = os.path.join(download_dir, "GoogleCalender")
        print(f"Extracting {os.path.basename(zip_path)} to {extract_path}...")

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        os.remove(zip_path)
        print("Google Calendar export successful.")
        
    def set_id(self, id):
        self.open_status()
        self.set_status('googleID', id)
        self.save_status()