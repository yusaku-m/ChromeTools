class Browser:
    def __init__(self, driver_path, userdata_path):
        #初期設定
        import os
        from msedge.selenium_tools import Edge, EdgeOptions
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
        driver = Edge(executable_path = driver_path, options=options)
        #driver.maximize_window()
        #タイムアウト設定
        driver.set_page_load_timeout(120)
        driver.implicitly_wait(10) #要素が見つかるまで待つ時間
        self.driver = driver
class Zaimu_Kaikei(Browser):
    def __init__(self, driver_path, userdata_path):
        super().__init__(driver_path, userdata_path)
        self.driver.get('https://zaimu-kaikei.kosen-k.go.jp/llas5/view/login.html')
        from selenium.webdriver.support.select import Select
        Select(self.driver.find_element_by_id('cCdSb')).select_by_visible_text('39/39_香川高等専門学校')
        self.driver.find_element_by_id('doLogin').click()
    def input_order(self, order):
        self.driver.get('https://zaimu-kaikei.kosen-k.go.jp/llas5/view/financialAccounting/supply/purchaseRequestDetailsEntry.html')
        #配分中以外も表示
        self.driver.find_element_by_id('hibnCheckYsn-1').click()
        #執行組織の変更
        self.driver.find_element_by_id('select2-skkuSskYsn-1-container').click()
        self.driver.find_element_by_class_name('select2-search__field').send_keys(order.organization)
        self.driver.find_element_by_xpath(f'//li[contains(@title,"{order.organization}")]').click()
        #予算の選択
        self.driver.find_element_by_xpath(f'//span[contains(text(),"{order.budget}")]').click()
        #各項目の入力
        self.driver.find_element_by_id('select2-cCdNuhnPlc-container').click()
        self.driver.find_element_by_class_name('select2-search__field').send_keys(order.place)
        self.driver.find_element_by_xpath(f'//li[contains(@title,"{order.place}")]' ).click()
        self.driver.find_element_by_id('cHnName').send_keys(order.item)
        self.driver.find_element_by_id('cSu').send_keys(order.quantity)
        self.driver.find_element_by_id('cTnk').send_keys(order.unit_price)
        #新規作成
        self.driver.find_element_by_id('select2-skkuSskYsn-1-container').click()
        self.driver.find_element_by_id('S_CreateNew').click()
        while not "登録しました" in self.driver.page_source:
            import time
            time.sleep(1)
            try:
                self.driver.switch_to_alert().accept()
            except:
                print('登録待機中…')
class Order:
    def __init__(self, item, quantity, unit_price, place, organization, budget):
        self.item           = item
        self.quantity       = quantity
        self.unit_price     = unit_price
        self.place          = place
        self.organization   = organization
        self.budget         = budget

#作業ディレクトリを指定
import os
os.chdir('C:/Users/Yusaku/独立行政法人 国立高等専門学校機構/前田研究室 - General/研究室資料/物品購入')
#edgeドライバのパスを指定(使用バージョンに合わせたものをダウンロードhttps://developer.microsoft.com/ja-jp/microsoft-edge/tools/webdriver/)
driver_path = 'C:/Users/Yusaku/Documents/GitHub/msedgedriver.exe'
#edge一時データの保存先を指定（プロファイルがある場所でないと動かなくなった）
userdata_path = 'C:/Users/Yusaku/AppData/Local/Microsoft/Edge/User Data'

#会計システムにログイン（ユーザー名，パスワードはedgeに保存しておけば自動入力される）
browser = Zaimu_Kaikei(driver_path, userdata_path)

import pandas as pd
df = pd.read_csv('ItemList20220428.csv', header=0, encoding = 'shift_jis')
for index, row in df.iterrows():
    item        = f'{row["品名"]}_{row["型番"]}({row["色・サイズ等"]})'
    quantity    = row["数量"]
    unit_price  = row["単価（税込）"]
    place       = row["納入場所"]
    organization= row["執行組織"]
    budget      = row["予算"]
    #購入依頼データを作成
    order = Order(item, quantity, unit_price, place, organization, budget)
    #購入依頼を入力
    browser.input_order(order)

'''
入力項目ごとにクラスを作成し，inputメソッドをそれぞれオーバーライド
入力項目一覧をリストとしてfor文に渡すと，入力部分をfor文でinput回すだけで書ける。
'''