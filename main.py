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
        driver.implicitly_wait(30) #要素が見つかるまで待つ時間
        self.driver = driver
class Zaimu_Kaikei(Browser):
    def __init__(self, driver_path):
        super().__init__(driver_path)
        self.driver.get('https://zaimu-kaikei.kosen-k.go.jp/llas5/view/login.html')
        from selenium.webdriver.support.select import Select
        Select(self.driver.find_element_by_id('cCdSb')).select_by_visible_text('39/39_香川高等専門学校')
        self.driver.find_element_by_id("doLogin").click()
    def input_order(self):
        self.driver.get('https://zaimu-kaikei.kosen-k.go.jp/llas5/view/financialAccounting/supply/purchaseRequestDetailsEntry.html')
        self.driver.find_element_by_id('select2-skkuSskYsn-1-container').click()
        self.driver.find_element_by_class_name('select2-search__field').send_keys('前田')
        self.driver.find_element_by_xpath('//li[contains(@title,"前田")]' ).click()
        self.driver.find_element_by_id('cHnName').send_keys('testitem')
        self.driver.find_element_by_id('cSu').send_keys('2')
        self.driver.find_element_by_id('cTnk').send_keys('1100')
        self.driver.find_element_by_class_name('select2-search__field').send_keys('共同研究ｽﾍﾟｰｽ（１）')
        self.driver.find_element_by_xpath('//li[contains(@title,"共同研究ｽﾍﾟｰｽ（１）")]' ).click()
    def input_order_test(self):
        self.driver.get('https://zaimu-kaikei.kosen-k.go.jp/llas5/view/financialAccounting/supply/purchaseRequestDetailsEntry.html')
        self.driver.find_element_by_id('select2-skkuSskYsn-1-container').click()
        self.driver.find_element_by_class_name('select2-search__field').send_keys('前田')
        self.driver.find_element_by_xpath('//li[contains(@title,"前田")]' ).click()
        self.driver.find_element_by_id('cHnName').send_keys('testitem')
        self.driver.find_element_by_id('cSu').send_keys('2')
        self.driver.find_element_by_id('cTnk').send_keys('1100')
        self.driver.find_element_by_class_name('select2-search__field').send_keys('共同研究ｽﾍﾟｰｽ（１）')
        self.driver.find_element_by_xpath('//li[contains(@title,"共同研究ｽﾍﾟｰｽ（１）")]' ).click()
path_change()
import os
driver_path = os.getcwd() + '/msedgedriver.exe'
browser = Zaimu_Kaikei(driver_path)
browser.input_order()

import time
time.sleep(60)
