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

    def add_extra_calendar(self, key, secret_ics_url, display_name=None):
        """`/exporticalzip`（全カレンダー一括エクスポート）に含まれないカレンダーを登録する。

        オーナーではなく「共有」で編集権限を得ているだけのカレンダー（他アカウント所有の
        カレンダーなど）は、権限の有無に関わらず一括エクスポートの対象から漏れることがある。
        該当カレンダーの設定画面 > 「カレンダーの統合」 > 「非公開アドレス（iCal形式）」の
        URLをここに登録しておくと、get_extra_calendars() で個別に取得できるようになる。

        key: 'extra_calendar_<key>_url' として status.binaryfile に保存する識別子（英数字推奨）
        """
        self.open_status()
        self.set_status(f'extra_calendar_{key}_name', display_name or key)
        self.set_status(f'extra_calendar_{key}_url', secret_ics_url)
        self.save_status()

    def get_extra_calendars(self):
        """add_extra_calendar() で登録済みのカレンダーを、非公開iCalアドレス経由で個別取得する。"""
        import glob

        download_dir = os.path.join(os.getcwd(), "data")
        extract_path = os.path.join(download_dir, "GoogleCalender")
        os.makedirs(extract_path, exist_ok=True)

        url_keys = [k for k in self.status.index if str(k).startswith('extra_calendar_') and str(k).endswith('_url')]
        for url_key in url_keys:
            key = url_key[len('extra_calendar_'):-len('_url')]
            name_key = f'extra_calendar_{key}_name'
            display_name = self.status.at[name_key, 'value'] if name_key in self.status.index else key
            url = self.status.at[url_key, 'value']

            print(f"Fetching extra calendar: {display_name}")
            before = set(os.listdir(download_dir))
            self.driver.get(url)
            self.wait_download()
            new_files = set(os.listdir(download_dir)) - before
            new_files = {f for f in new_files if not f.endswith('.crdownload')}

            if not new_files:
                candidates = sorted(glob.glob(os.path.join(download_dir, "*.ics")), key=os.path.getmtime, reverse=True)
                if not candidates:
                    print(f"  Warning: {display_name} のダウンロードファイルが見つかりませんでした。")
                    continue
                new_files = {os.path.basename(candidates[0])}

            src = os.path.join(download_dir, next(iter(new_files)))
            dst = os.path.join(extract_path, f"{key}.ics")
            if os.path.exists(dst):
                os.remove(dst)
            os.replace(src, dst)
            print(f"  Saved: {dst}")