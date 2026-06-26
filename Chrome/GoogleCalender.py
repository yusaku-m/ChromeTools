import os
from Chrome.Browser import Browser
from selenium.webdriver.common.by import By

class GoogleCalender(Browser):
    def get_calender(self):
        import time, zipfile, glob
        EXPORT_URL = 'https://calendar.google.com/calendar/u/0/exporticalzip'
        print("Accessing Google Calendar export URL...")
        self.driver.get(EXPORT_URL)
        time.sleep(3)

        current = self.driver.current_url
        print(f"  Current URL: {current}")

        # ログインが必要かどうかを判定（calendar.google.com 以外にいる場合、またはダウンロードが始まらない場合）
        needs_login = ('calendar.google.com' not in current) or ('accounts.google.com' in current)
        if not needs_login:
            # ダウンロードが3秒以内に始まらなければログインが必要と判断
            time.sleep(3)
            needs_login = not bool(glob.glob('./data/*.crdownload') or glob.glob('./data/*.ical.zip'))

        if needs_login:
            print("\n【Googleログインが必要です】")
            print("Chromeウィンドウで jagaimo13@gmail.com にログインしてください。")
            print("ログイン完了後、自動的にエクスポートが始まります（最大5分待機）...")
            deadline = time.time() + 300
            while time.time() < deadline:
                time.sleep(2)
                url = self.driver.current_url
                # ログイン完了してカレンダーに戻ったら再エクスポート
                if 'calendar.google.com' in url and 'accounts.google.com' not in url:
                    print("ログイン確認。エクスポートを再実行します...")
                    time.sleep(2)
                    self.driver.get(EXPORT_URL)
                    break
            else:
                raise TimeoutError("5分以内にGoogleログインが完了しませんでした。")

        self.wait_download()

        id = self.status.at['googleID', 'value']
        zip_path = os.path.join("./data", f"{id}@gmail.com.ical.zip")
        extract_path = os.path.join("./data", "GoogleCalender")

        print(f"Extracting {zip_path} to {extract_path}...")

        if os.path.exists(zip_path):
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            os.remove(zip_path)
            print("Google Calendar export successful.")
        else:
            print(f"Error: {zip_path} not found. Download might have failed.")
            raise FileNotFoundError(f"Google Calendar export zip not found: {zip_path}")
        
    def set_id(self, id):
        self.open_status()
        self.set_status('googleID', id)
        self.save_status()