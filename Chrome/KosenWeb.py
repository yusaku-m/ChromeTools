from .Browser import Browser
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait
import os
import time

BASE_URL = 'https://tktsvr2.t.kagawa-nct.ac.jp/kosen-web'
#メニュー「日別出欠の閲覧（期間指定）」。31 は高松キャンパス(担任メニュー側)。
#同じ画面が 41 側のメニューにもあるが、学年・学科で絞れるのは 31 側で確認した(2026-10)。
DAILY_ATTENDANCE_URL = BASE_URL + '/wku0121/index/31/31-W-6-3-7'


class KosenWeb(Browser):
    """KOSEN WEB(教務システム)の操作。

    画面の項目は 2026-10 時点の実機で確認したもの:
    年度 #vi-con-nendo / 期間 #vi-con-datefrom・#vi-con-dateto(YYYY/MM/DD) /
    学年 #vi-drp-years / 学科・クラス #vi-drp-classex / 「CSVファイル出力」 #vi-btn-output。
    出力ボタンは JSON を POST してファイルを返す(ページ遷移しない)。
    """

    def login(self):
        """ログインする。パスワードが自動入力されていればボタンを押し、
        されていなければブラウザ上で手動ログインされるのを待つ。"""
        print("KOSEN WEB login...")
        self.driver.get(DAILY_ATTENDANCE_URL)
        if not self.driver.find_elements(By.ID, 'LoginID'):
            return
        #Chrome は自動入力したパスワードを、ユーザー操作があるまでページの JS に見せない。
        #自動入力済みかどうかは :-webkit-autofill で判定する(Sakura.login と同じ)。
        filled = False
        for _ in range(10):
            time.sleep(0.5)
            filled = self.driver.execute_script(
                "const p=document.getElementById('Password');"
                "return !!(p && (p.value || p.matches(':-webkit-autofill')))")
            if filled:
                break
        if filled:
            self.driver.find_element(By.CSS_SELECTOR, 'form[action$="/account/login"] input[type=submit]').click()
        else:
            print("パスワードが自動入力されていません。ブラウザで KOSEN WEB にログインしてください。")
        self.wait_for_manual_step(lambda: not self.driver.find_elements(By.ID, 'LoginID'),
                                  description="KOSEN WEB へのログイン")

    def _select_by_text(self, element_id, text):
        select = Select(self.driver.find_element(By.ID, element_id))
        target = [o for o in select.options if o.text.strip() == text]
        if len(target) != 1:
            raise RuntimeError(f"#{element_id} に「{text}」が {len(target)} 件あります")
        select.select_by_value(target[0].get_attribute('value'))

    def download_daily_attendance(self, date, grade, department, download_dir, timeout=60):
        """日別出欠の閲覧(期間指定)で date 1日分を grade(例 '3年')・department(例 '機械工学科')で
        絞って出力し、保存したファイルのパスを返す。

        出力ファイルは個人情報を含むので、download_dir は呼び出し側で専用の一時フォルダを用意し、
        読み終わったら消すこと。
        """
        self.login()
        if '/wku0121/' not in self.driver.current_url:
            self.driver.get(DAILY_ATTENDANCE_URL)
        WebDriverWait(self.driver, 20).until(
            lambda d: d.execute_script("return typeof $ === 'function' && !!document.getElementById('vi-btn-output')"))

        #年度(4月始まり)。変えると学年・学科の選択肢が作り直される可能性があるので先に選ぶ
        nendo = date.year if date.month >= 4 else date.year - 1
        Select(self.driver.find_element(By.ID, 'vi-con-nendo')).select_by_value(str(nendo))
        time.sleep(1)
        day = date.strftime('%Y/%m/%d')
        self.driver.execute_script(
            "$('#vi-con-datefrom').val(arguments[0]).trigger('change');"
            "$('#vi-con-dateto').val(arguments[0]).trigger('change');", day)
        self._select_by_text('vi-drp-years', grade)
        #「機械工学科（旧）」と取り違えないよう完全一致で選ぶ
        self._select_by_text('vi-drp-classex', department)

        os.makedirs(download_dir, exist_ok=True)
        self.driver.execute_cdp_cmd('Browser.setDownloadBehavior',
                                    {'behavior': 'allow', 'downloadPath': os.path.abspath(download_dir)})
        try:
            self.safe_click((By.ID, 'vi-btn-output'))
            return self._wait_downloaded_file(download_dir, timeout)
        finally:
            #以降のダウンロードは既定(Browser の data/)に戻す
            self.driver.execute_cdp_cmd('Browser.setDownloadBehavior',
                                        {'behavior': 'allow', 'downloadPath': os.path.join(os.getcwd(), 'data')})

    def _wait_downloaded_file(self, download_dir, timeout):
        end = time.time() + timeout
        last_size = None
        while time.time() < end:
            try:
                #該当データなし等はネイティブ alert で返ってくる
                alert = self.driver.switch_to.alert
                text = alert.text
                alert.accept()
                raise RuntimeError(f"KOSEN WEB: {text}")
            except NoAlertPresentException:
                pass
            files = [f for f in os.listdir(download_dir)
                     if not f.endswith(('.crdownload', '.tmp'))]
            if files:
                path = os.path.join(download_dir, files[0])
                size = os.path.getsize(path)
                if size and size == last_size:
                    return path
                last_size = size
            time.sleep(0.5)
        raise TimeoutError(f"KOSEN WEB の出力ファイルが {timeout} 秒以内に保存されませんでした")
