import os
from Chrome.Browser import Browser
from selenium.webdriver.common.by import By

class GoogleCalender(Browser):
    # 「インポート/エクスポート」画面(設定 > Import & export)のURL。
    IMPORT_URL = 'https://calendar.google.com/calendar/u/0/r/settings/export'
    # インポート結果ダイアログの文言。英語UIは "Imported 2 out of 2 events."、
    # 日本語UIは「2 件中 2 件の予定をインポートしました。」のような形になる。
    _IMPORT_RESULT_RE = r'(\d+)\D+(\d+)'

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

    def import_ics(self, ics_path, calendar_name):
        """設定 > インポート/エクスポート から ics を指定カレンダーへ取り込む。

        icsの各予定に固定UIDが振ってあれば、同じUIDの予定は重複作成ではなく
        更新として扱われる(2026-09-02に実カレンダーで確認済み: 9:00-10:00で
        取り込んだ2件を、同UID・14:00-15:00のicsで再取り込みしたところ、
        件数は2件のまま時刻だけが置き換わった)。このためカレンダーごと削除して
        作り直す必要はない。

        ただし、前回のicsには有ったが今回のicsには無いUIDの予定(勤務日→週休日に
        変わった日など)は消えずに残る。それらの掃除はこのメソッドの責任外。
        """
        import re
        import time
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.wait import WebDriverWait

        ics_path = os.path.abspath(ics_path)
        if not os.path.isfile(ics_path):
            raise FileNotFoundError(f'インポートするicsが見つかりません: {ics_path}')

        # ファイル選択のinputは常にDOM上にあるので、これを目印にページの到達を待つ
        # (Windows HelloのPINダイアログ等で遷移がブロックされるケースへの対策)
        file_input_locator = (By.CSS_SELECTOR, 'input[type="file"][name="filename"]')
        self.patient_get(self.IMPORT_URL, description='Googleカレンダーのインポート画面', wait_for=file_input_locator)

        # CSSで隠されたinputだが、send_keys()はdisplay:noneでも受け付ける
        # (クリックするとOSのファイル選択ダイアログが開いてしまうのでクリックしない)
        self.driver.find_element(*file_input_locator).send_keys(ics_path)

        self._select_import_calendar(calendar_name)

        # 「インポート」ボタン。ファイル未選択の間はdisabledなので、有効になるまで待つ
        import_button = WebDriverWait(self.driver, 20).until(
            lambda d: next((b for b in d.find_elements(By.CSS_SELECTOR, 'button[jsname="N8B8lb"]') if b.is_enabled()), None)
        )
        self.safe_click(import_button)

        # 結果ダイアログ(「Imported N out of M events.」)の出現を待つ。
        # 要素の存在だけを条件にすると、文言が描画される前の空のダイアログを掴んでしまい
        # メッセージが空文字で返る(実行時に確認済み)ので、テキストが入るまで待つ。
        def _result_dialog(driver):
            for d in driver.find_elements(By.CSS_SELECTOR, 'div[role="alertdialog"], div[role="dialog"]'):
                try:
                    if (d.text or '').strip():
                        return d
                except Exception:
                    pass
            return None

        dialog = WebDriverWait(self.driver, 300).until(_result_dialog)
        # dialog.textにはOKボタンの文字も含まれるので、1行目(結果の文言)だけ使う
        message = (dialog.text or '').strip().splitlines()[0]
        print(f'インポート結果: {message}')

        m = re.search(self._IMPORT_RESULT_RE, message)
        imported, total = (int(m.group(1)), int(m.group(2))) if m else (None, None)
        if imported is not None and imported != total:
            print(f'警告: {total}件中{imported}件しかインポートされませんでした。')

        # OKで閉じる。閉じないと次の操作がダイアログに遮られる
        for ok in dialog.find_elements(By.TAG_NAME, 'button'):
            if (ok.text or '').strip():
                self.safe_click(ok)
                break
        time.sleep(1)
        return imported, total

    def _select_import_calendar(self, calendar_name):
        """インポート画面の「カレンダーに追加」でインポート先カレンダーを選ぶ。

        これは<select>ではなくGoogle独自のリストボックスウィジェットなので、
        Selectクラスは使えない。またリストの表示位置は前回選択項目に応じて
        変わるため、座標ではなくオプションの表示テキストで引く必要がある
        (座標決め打ちで別カレンダーを選んでしまう事象を実機で確認済み)。
        aria-labelはUI言語に依存するので使わない。"""
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.wait import WebDriverWait

        combobox_locator = (By.CSS_SELECTOR, '[role="combobox"][aria-haspopup="listbox"]')
        combobox = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located(combobox_locator))
        self.safe_click(combobox)

        option_xpath = f'//ul[@role="listbox"]//li[@role="option"][normalize-space(.)="{calendar_name}"]'
        options = self.driver.find_elements(By.XPATH, option_xpath)
        if not options:
            available = [(li.text or '').strip() for li in self.driver.find_elements(By.CSS_SELECTOR, 'ul[role="listbox"] li[role="option"]')]
            raise RuntimeError(f'インポート先カレンダー「{calendar_name}」が見つかりません。候補: {available}')
        self.safe_click(options[0])

        # 選択が実際に反映されたか確認する。反映前にインポートを押すと
        # 別のカレンダーへ取り込まれてしまい、取り消しが面倒になる
        WebDriverWait(self.driver, 10).until(
            lambda d: calendar_name in (d.find_element(*combobox_locator).text or '')
        )
        print(f'インポート先: {calendar_name}')
