from .Browser import Browser
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait
import pandas
import re
import time

LOGIN_URL = 'https://www.390390.jp/admin/login?ENV_CODE=webasp3'
MAIN_URL = 'https://www.390390.jp/admin/main'
MSGLIST_URL = 'https://www.390390.jp/admin/msglist'

#受信者の data-name は「苗字　名前(〇〇3〇)」のように末尾にクラスの括弧書きが付く
#(2026-10 実機確認、45件すべて同じ形)。氏名照合ではこれを落として比較する。
_CLASS_SUFFIX = re.compile(r'[（(][^（()）]*[)）]\s*$')


def normalize_name(name):
    """氏名照合用の正規化。クラスの括弧書きと空白(全角/半角)を除く。"""
    import unicodedata
    name = _CLASS_SUFFIX.sub('', name)
    return re.sub(r'[\s\u3000]+', '', unicodedata.normalize('NFKC', name))


class Sakura(Browser):
    def __init__(self, userdata_path, debugger_address=None):
        super().__init__(userdata_path, debugger_address)
        self.login()

    def login(self):
        """ログインする。パスワードが自動入力されていればボタンを押し、
        されていなければブラウザ上で手動ログインされるのを待つ。"""
        print("login...")
        if '/admin/main' in self.driver.current_url or '/admin/msglist' in self.driver.current_url:
            return
        self.driver.get(LOGIN_URL)
        self.wait_element((By.CLASS_NAME, 'work_btn'))
        #Chrome は自動入力したパスワードを、ユーザー操作があるまでページの JS に見せない
        #(value が空文字のまま)。自動入力済みかどうかは :-webkit-autofill で判定する。
        filled = False
        for _ in range(10):
            time.sleep(0.5)
            filled = self.driver.execute_script(
                "const p=document.querySelector('input[type=password]');"
                "return !!(p && (p.value || p.matches(':-webkit-autofill')))")
            if filled:
                break
        if filled:
            self.driver.find_element(By.CLASS_NAME, 'work_btn').click()
        else:
            print("パスワードが自動入力されていません。ブラウザでログインしてください。")
        self.wait_for_manual_step(lambda: '/admin/main' in self.driver.current_url,
                                  description="さくら連絡網へのログイン")

    def make_mail(self, message):
        print("make mail...")
        self.driver.get('https://www.390390.jp/admin/main')
        self.wait_element((By.LINK_TEXT, 'メッセージ作成'))
        self.driver.find_element(By.LINK_TEXT, 'メッセージ作成').click()

        self.wait_element((By.CLASS_NAME, 'message.work_btn'))
        self.driver.find_element(By.CLASS_NAME, 'message.work_btn').click()

        #メッセージ入力
        self.driver.find_element(By.ID, 'txtSubject').send_keys(message.title)
        self.driver.find_element(By.ID, 'txtaBody').send_keys(message.text)

        #送信者の選択
        self.driver.find_elements(By.CLASS_NAME, "work_btn.work_next.rightbtn")[1].click()
        self.driver.find_element(By.XPATH, '//div[text()="個人から選ぶ"]').click()
        self.driver.find_elements(By.CLASS_NAME, "work_btn.work_add.small")[2].click()

        Select(self.driver.find_element(By.ID, 'cmbAccountSearchAff')).select_by_visible_text('　高松キャンパス(全員)')

        for to in message.to:
            self.driver.find_element(By.XPATH, f"//*[@data-name='{to}']").click()

        self.driver.find_elements(By.CLASS_NAME, "work_btn.work_add.rightbtn")[0].click()
        self.driver.find_elements(By.CLASS_NAME, "work_btn.work_next.rightbtn")[3].click()

        #送信設定
        self.driver.find_element(By.XPATH, '//div[text()="設定"]').click()
        self.driver.find_element(By.XPATH, f"//*[@for='rdoInsertAccountName_ON']").click()
        self.driver.find_elements(By.CLASS_NAME, "work_btn.work_define.rightbtn")[4].click()

        #self.driver.find_element(By.XPATH, "//*[@onclick='MsgEditWorker.DefineOptionDialog()']").click()
        print("mail maked")

    # ------------------------------------------------------------------
    # 既存メッセージをコピーして宛先を個人指定で差し替える
    #
    # 画面の各ボタンは onclick に書かれた JS 関数を直接呼ぶ。ボタンの並び順や
    # 表示位置(画面サイズで変わる)に依存しないようにするため。関数名は
    # 2026-10 時点の実機で確認したもの。
    # ------------------------------------------------------------------
    def _accept_alerts(self, timeout=5):
        """ネイティブ alert/confirm をすべて OK で閉じ、その文言を返す。
        コピーは「コピーしますか？」→「コピーしました。」の2連続で出る。"""
        texts = []
        end = time.time() + timeout
        while time.time() < end:
            try:
                alert = self.driver.switch_to.alert
                texts.append(alert.text)
                alert.accept()
                end = time.time() + 2
            except NoAlertPresentException:
                time.sleep(0.3)
        return texts

    def _wait_js(self, script, timeout=20):
        return WebDriverWait(self.driver, timeout).until(lambda d: d.execute_script(script))

    def list_messages(self, subject_pattern):
        """メッセージ一覧から件名が subject_pattern(正規表現)に合う行を返す。
        [(distno, 件名, 状態), ...] を一覧の表示順(送信日時の降順)で返す。"""
        self.driver.get(MSGLIST_URL)
        self._wait_js("return document.querySelectorAll('tr[data-drawkey]').length > 0")
        rows = self.driver.execute_script("""
            return [...document.querySelectorAll('tr[data-drawkey]')].map(r => [
                r.dataset.drawkey,
                (r.querySelector('[data-column=subject]')||{}).innerText || '',
                (r.querySelector('[data-column=status_info]')||{}).innerText || '']);""")
        return [r for r in rows if re.search(subject_pattern, r[1])]

    def copy_message(self, distno):
        """送信済みメッセージ distno をコピーし、できた下書きの distno を返す。"""
        before = {r[0] for r in self.list_messages('')}
        self.driver.execute_script(f"Worker.OpenResult({distno})")
        self._wait_js("return typeof ResultWorker !== 'undefined' && "
                      "[...document.querySelectorAll('.work_btn')].some(e => e.offsetParent && "
                      "(e.getAttribute('onclick')||'').includes('ResultWorker.CopyDist'))")
        self.driver.execute_script("ResultWorker.CopyDist()")
        print("  ", " / ".join(self._accept_alerts()))
        new = [r for r in self.list_messages('') if r[0] not in before]
        if len(new) != 1:
            raise RuntimeError(f"コピーで作られた下書きを特定できません(新規 {len(new)} 件)")
        return new[0][0]

    def edit_subject(self, distno, subject):
        """下書きを編集画面で開いて件名を書き換え、宛先ページへ進む。"""
        self.driver.execute_script(f"OpenDistEdit_Update({distno})")
        #ダイアログの枠(txtSubject)は MsgEditWorker の初期化や下書きの読み込みより
        #先に表示されるので、件名が読み込まれるまで待つ
        self._wait_js("const e=document.getElementById('txtSubject');"
                      "return typeof MsgEditWorker !== 'undefined' && MsgEditWorker && "
                      "e && e.offsetParent !== null && e.value !== ''")
        box = self.driver.find_element(By.ID, 'txtSubject')
        box.clear()
        box.send_keys(subject)
        self.driver.execute_script("MsgEditWorker.MessageNextPage();")
        self._accept_alerts(timeout=2)
        self._wait_js("return [...document.querySelectorAll('.send-select-button')].some(e => e.offsetParent)")

    def new_message(self, subject, body):
        """メッセージを新規作成して件名と本文を入れ、宛先ページへ進む。

        本文エディタは Quill(MsgEditWorker.Editor)。「文字装飾OFF」のときだけ
        textarea(txtaBody)が使われるので、両方に対応する。
        """
        #直前にユーザーが送信した後の「メッセージの登録が完了しました。」が残っていると
        #driver.get が UnexpectedAlertPresentException になるので閉じておく
        self._accept_alerts(timeout=1)
        self.driver.get(MAIN_URL)
        self._wait_js("return typeof OpenDistEdit_New === 'function'")
        self.driver.execute_script("OpenDistEdit_New();")
        #種別選択(メッセージ/アンケート/安否確認)のボタンが出るまで待つ
        self._wait_js("return [...document.querySelectorAll('[onclick]')].some(e => e.offsetParent && "
                      "(e.getAttribute('onclick')||'').includes('DefineMessageType(DIST_MESSAGE_TYPE.MESSAGE)'))")
        self.driver.execute_script("MsgEditWorker.DefineMessageType(DIST_MESSAGE_TYPE.MESSAGE);")
        self._wait_js("const e=document.getElementById('txtSubject');"
                      "return MsgEditWorker && MsgEditWorker.Editor && e && e.offsetParent !== null")
        box = self.driver.find_element(By.ID, 'txtSubject')
        box.clear()
        box.send_keys(subject)
        self.driver.execute_script("""
            if (MsgEditWorker.UseNormalEditor) {
                document.getElementById('txtaBody').value = arguments[0];
            } else {
                MsgEditWorker.Editor.setText(arguments[0]);
            }""", body)
        self.driver.execute_script("MsgEditWorker.MessageNextPage();")
        self._accept_alerts(timeout=2)
        #新規作成では宛先ページを経ずに「宛先の選び方を選択してください」画面が直接開く
        self._wait_js(f"return {self._SEND_SELECT_SHOWN_JS}")

    #「宛先の選び方」画面(個人から選ぶ/グループから選ぶ等)が表示されているか
    _SEND_SELECT_SHOWN_JS = ("(!!(document.getElementById('screen-send-select')||{}).offsetParent || "
                             "[...document.querySelectorAll('[onclick]')].some(e => e.offsetParent && "
                             "(e.getAttribute('onclick')||'').includes('DefineSendSelect(')))")

    def set_recipients(self, names, affiliation):
        """宛先を「個人から選ぶ」で names(氏名のリスト)に差し替える。

        affiliation は「学年クラス」プルダウンの表示名(前後の全角空白は無視)。
        保護者用の同名グループ(例: 機械工学科３年（保護者）)と取り違えないよう完全一致で選ぶ。

        照合できなかった氏名は names 内の位置(0始まり)のリストで返す。
        氏名は個人情報なので、ログには件数と位置しか出さないこと。
        """
        if not self.driver.execute_script(f"return {self._SEND_SELECT_SHOWN_JS}"):
            #コピーした下書きは宛先ページから「宛先の選び方」画面を開く。新規作成では既に開いている
            self.driver.execute_script("MsgEditWorker.OpenSubModal('screen-send-select');")
        self._wait_js("return typeof DIST_SEND_SELECT_TYPE !== 'undefined'")
        self.driver.execute_script("MsgEditWorker.DefineSendSelect(DIST_SEND_SELECT_TYPE.ACCOUNT);")
        self._wait_js("const e=document.getElementById('lvSendAccount');return !!e")

        #コピー元の宛先を消す。Excel 取込で宛先を入れたメールからのコピーでは引き継がれないが、
        #「個人から選ぶ」で宛先を入れたメール(=このスクリプトで送ったもの)からのコピーでは
        #個人の宛先一覧がそのまま残る。
        self.driver.execute_script("MsgEditWorker.LvSendAccount.Clear();")
        existing = self.driver.execute_script("return document.querySelectorAll('#lvSendAccount > li').length")
        if existing:
            raise RuntimeError(f"宛先一覧を消せませんでした(残り {existing} 件)。手動で削除してから再実行してください。")

        self.driver.execute_script("MsgEditWorker.OpenAccountAddModal(MsgEditWorker.LvSendAccount);")
        self._wait_js("const e=document.getElementById('cmbAccountSearchAff');return e && e.offsetParent !== null")
        select = Select(self.driver.find_element(By.ID, 'cmbAccountSearchAff'))
        target = [o for o in select.options if o.text.strip('\u3000 ') == affiliation]
        if len(target) != 1:
            raise RuntimeError(f"学年クラス「{affiliation}」が {len(target)} 件見つかりました")
        select.select_by_value(target[0].get_attribute('value'))
        self._wait_js("return document.querySelectorAll('#lstAccountAdd input[type=checkbox]').length > 0")
        time.sleep(1)

        candidates = self.driver.execute_script(
            "return [...document.querySelectorAll('#lstAccountAdd input[type=checkbox]')]"
            ".map(c => [c.value, c.getAttribute('data-name')]);")
        by_name = {}
        for value, data_name in candidates:
            by_name.setdefault(normalize_name(data_name), []).append(value)

        values, unmatched = [], []
        for i, name in enumerate(names):
            hit = by_name.get(normalize_name(name), [])
            if len(hit) == 1:
                values.append(hit[0])
            else:
                unmatched.append(i)

        if not values:
            #誰も照合できなければ追加しない(宛先0件のまま確定すると一覧が空で待ち続ける)。
            #このダイアログは次の new_message() でページごと開き直すので閉じなくてよい
            print(f"   受信者一覧({len(candidates)} 名)に一致する氏名がありませんでした")
            return unmatched

        checked = self.driver.execute_script("""
            const want = new Set(arguments[0]); let n = 0;
            for (const c of document.querySelectorAll('#lstAccountAdd input[type=checkbox]')) {
                if (want.has(c.value) && !c.checked) { c.click(); }
                if (c.checked) n++;
            }
            return n;""", values)
        if checked != len(values):
            raise RuntimeError(f"チェック数が合いません(期待 {len(values)} / 実際 {checked})")

        self.driver.execute_script("MsgEditWorker.DefineAccountAddModal();")
        self._accept_alerts(timeout=2)
        added = self._wait_js(
            "const n=document.querySelectorAll('#lvSendAccount > li').length; return n > 0 ? n : false")
        if added != len(values):
            raise RuntimeError(f"宛先の件数が合いません(期待 {len(values)} / 実際 {added})")
        return unmatched

    def go_send_detail(self):
        """宛先ページの「次へ」。この先の送信はユーザーが手で行う。"""
        self.driver.execute_script("MsgEditWorker.DefineSendDetail();")
        return self._accept_alerts(timeout=3)

    #ユーザーが送信ボタンを押した後に出るネイティブ alert(2026-10 実機)
    SENT_ALERT = 'メッセージの登録が完了しました'

    def wait_for_send(self, keys='sq'):
        """送信確認画面で、ユーザーがブラウザで送信するか、コンソールでキーを押すのを待つ。

        送信完了の alert を検知したら閉じて 'sent' を返す。keys のどれかが押されたらその文字を返す。
        Enter を「送信した」とみなすと、送信できていないのに送信済みと記録してしまうため
        (2026-10-27 に実際に起きた)、完了の alert でだけ送信と判定する。
        それ以外の alert(送信前の確認等)はユーザーが操作するものなので触らない。
        """
        import msvcrt
        while msvcrt.kbhit():
            msvcrt.getwch()
        while True:
            try:
                alert = self.driver.switch_to.alert
                if self.SENT_ALERT in alert.text:
                    alert.accept()
                    return 'sent'
            except NoAlertPresentException:
                pass
            if msvcrt.kbhit():
                key = msvcrt.getwch().lower()
                if key in keys:
                    print(key)
                    return key
            time.sleep(0.3)

    def set_insert_recipient_name(self):
        """送信確認画面の「設定」で「受信者氏名を差し込む」を「する」にする。
        go_send_detail() の後に呼ぶ。"""
        self._wait_js("return typeof MsgEditWorker.OpenOptionDialog === 'function'")
        self.driver.execute_script("MsgEditWorker.OpenOptionDialog();")
        self._wait_js("return !!document.getElementById('rdoInsertAccountName_ON')")
        self.driver.execute_script("document.getElementById('rdoInsertAccountName_ON').click();")
        if not self.driver.execute_script("return document.getElementById('rdoInsertAccountName_ON').checked"):
            raise RuntimeError("「受信者氏名を差し込む」を「する」にできませんでした")
        self.driver.execute_script("MsgEditWorker.DefineOptionDialog();")
        return self._accept_alerts(timeout=2)


class Message():
    def __init__(self):
        self.title = ""
        self.text = ""
        self.to = []
        self.datetime = ""

    def get_data_from_excel(self, excelpath, sheetname):
        """エクセルから文章データを取得"""
        print("get mail data...")
        df = pandas.read_excel(excelpath, sheetname)

        self.title = df['表題'][0]
        self.text = df['本文'][0]
        self.to = df['対象者']


if __name__ == "__main__":
    print("test")

    excelpath = r"C:\Users\Yusaku\OneDrive - 独立行政法人 国立高等専門学校機構\Work\講義\そのた科目\さくら連絡網.xlsx"
    sheetname = r"出力"

    message = Message()
    message.get_data_from_excel(excelpath, sheetname)

    user_data_path = "C:/Users/Yusaku/AppData/Local/Google/Chrome/User Data/"
    sakura = Sakura(user_data_path)

    sakura.make_mail(message)


