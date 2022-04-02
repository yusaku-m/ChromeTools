def path_change():
    import os
    print(os.getcwd())
    print(__file__)
    if 'Temp' not in __file__:
        print('ディレクトリを変更')
        CURRENTPATH = os.path.dirname(__file__)
        os.chdir(CURRENTPATH)
    print(os.getcwd())

class Browser:
    def __init__(self, driver_path):
        #初期設定
        import os
        from msedge.selenium_tools import Edge, EdgeOptions
        options = EdgeOptions()
        options.use_chromium = True
        #options.add_argument('--headless')  #非表示で起動
        options.add_argument('--user-data-dir=C:/Users/Yusaku/.edgebuf')
        options.add_argument('--profile-directory=Default')#ユーザーとして起動
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
    def __init__(self, driver_path):
        super().__init__(driver_path)
        self.driver.get('https://zaimu-kaikei.kosen-k.go.jp/llas5/view/login.html')
        from selenium.webdriver.support.select import Select
        Select(self.driver.find_element_by_id('cCdSb')).select_by_visible_text('39/39_香川高等専門学校')
        self.driver.find_element_by_id("doLogin").click()
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
    def input_orders(self):
        self.driver.get('https://zaimu-kaikei.kosen-k.go.jp/llas5/view/financialAccounting/supply/purchaseRequestDetailsEntry.html')
        #配分中以外も表示
        self.driver.find_element_by_id('hibnCheckYsn-1').click()
        #執行組織の変更
        self.driver.find_element_by_id('select2-skkuSskYsn-1-container').click()
        self.driver.find_element_by_class_name('select2-search__field').send_keys('前田')
        self.driver.find_element_by_xpath('//li[contains(@title,"前田")]').click()
        #予算の選択
        self.driver.find_element_by_xpath('//span[contains(text(),"21K18090若手研究（前田祐作）")]').click()
        #各項目の入力
        self.driver.find_element_by_id('select2-cCdNuhnPlc-container').click()
        self.driver.find_element_by_class_name('select2-search__field').send_keys('共同研究ｽﾍﾟｰｽ（１）')
        self.driver.find_element_by_xpath('//li[contains(@title,"共同研究ｽﾍﾟｰｽ（１）")]' ).click()
        self.driver.find_element_by_id('cHnName').send_keys('testitem')
        self.driver.find_element_by_id('cSu').send_keys('2')
        self.driver.find_element_by_id('cTnk').send_keys('1100')
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
        #ここから２件目(新規作成ページへ移動すればこの処理は不要)
        self.driver.find_element_by_id('systemMessage').click()
        self.driver.find_element_by_id('S_CreateNew').click()

        while not "登録しました" in self.driver.page_source:
            import time
            time.sleep(1)
            try:
                self.driver.switch_to_alert().accept()
            except:
                print('登録待機中…')
        self.driver.get('https://zaimu-kaikei.kosen-k.go.jp/llas5/view/financialAccounting/supply/purchaseRequestDetailsEntry.html')
class Order:
    def __init__(self, item, quantity, unit_price, place, organization, budget):
        self.item           = item
        self.quantity       = quantity
        self.unit_price     = unit_price
        self.place          = place
        self.organization   = organization
        self.budget         = budget

path_change()
import os
driver_path = os.getcwd() + '/msedgedriver.exe'

#会計システムにログイン
browser = Zaimu_Kaikei(driver_path)

import pandas as pd
df = pd.read_csv('ItemList20220401.csv', header=0, encoding = 'shift_jis')
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
browser = Zaimu_Kaikei(driver_path)
order = Order(item = 'Qrio Card 2枚 Q-CD1', quantity = '5', unit_price = 2200, place = '共同研究ｽﾍﾟｰｽ（１）', organization = '機械共通経費', budget = '(教育研究)研究実施経費')
browser.input_order(order)
print('作業完了')
import time
time.sleep(60)
'''