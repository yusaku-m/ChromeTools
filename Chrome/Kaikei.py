from Chrome.Browser import Browser
from selenium.webdriver.common.by import By

class Kaikei(Browser):
    def __init__(self, userdata_path):
        super().__init__(userdata_path)
        self.driver.get('https://zaimu-kaikei.kosen-k.go.jp/llas5/view/login.html')
        self.driver.get('https://zaimu-kaikei.kosen-k.go.jp/llas5/view/login.html')
        self.wait_element((By.ID, 'cCdSb'))

        #ログイン
        from selenium.webdriver.support.select import Select
        print("login...")
        Select(self.driver.find_element(By.ID, 'cCdSb')).select_by_visible_text('39/39_香川高等専門学校')
        self.driver.find_element(By.ID, 'doLogin').click()

        #年度偏光
        self.wait_element((By.CLASS_NAME, 'S_layoutDisp'))
        self.driver.find_element(By.CLASS_NAME, 'By.CLASS_NAME').click()
        self.driver.find_element(By.XPATH, f'//li[contains(text(),"R05")]').click()

    def input_order(self, order):
        print("start input order...")
        self.driver.get('https://zaimu-kaikei.kosen-k.go.jp/llas5/view/financialAccounting/supply/purchaseRequestDetailsEntry.html')
        self.wait_element((By.ID, 'hibnCheckYsn-1'))
        print("select fand...")
        #配分中以外も表示
        self.driver.find_element(By.ID, 'hibnCheckYsn-1').click()
        #執行組織の変更
        self.driver.find_element(By.ID, 'select2-skkuSskYsn-1-container').click()
        self.driver.find_element(By.CLASS_NAME, 'select2-search__field').send_keys(order.organization)
        self.driver.find_element(By.XPATH, f'//li[contains(@title,"{order.organization}")]').click()
        #予算の選択
        self.driver.find_element(By.XPATH, f'//span[contains(text(),"{order.budget}")]').click()
        print("input detail...")
        #各項目の入力
        self.driver.find_element(By.ID, 'select2-cCdNuhnPlc-container').click()
        self.driver.find_element(By.CLASS_NAME, 'select2-search__field').send_keys(order.place)
        
        self.driver.find_element(By.XPATH, f'//li[contains(@title,"{order.place}")]' ).click()
        self.driver.find_element(By.ID, 'cHnNameRe').send_keys(order.item)
        self.driver.find_element(By.ID, 'cSu').send_keys(order.quantity)
        self.driver.find_element(By.ID, 'cTnk').send_keys(order.unit_price)
        #新規作成
        self.driver.find_element(By.ID, 'select2-skkuSskYsn-1-container').click()
        self.driver.find_element(By.ID, 'S_CreateNew').click()

        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        try:
            wait = WebDriverWait(self.driver, 30)
            wait.until(EC.alert_is_present())
            alert = self.driver.switch_to.alert
            print(alert.text)
            alert.accept()
            self.wait_element((By.ID, 'allMessages'))
        except TimeoutException:
            print("アラートは発生しませんでした")

class Order:
    def __init__(self, item, quantity, unit_price, place, organization, budget):
        self.item           = item
        self.quantity       = quantity
        self.unit_price     = unit_price
        self.place          = place
        self.organization   = organization
        self.budget         = budget
