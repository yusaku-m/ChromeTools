from Chrome.Browser import Browser
from selenium.webdriver.common.by import By

class Kaikei(Browser):
    def __init__(self, userdata_path):
        super().__init__(userdata_path)
        self.driver.get('https://zaimu-kaikei.kosen-k.go.jp/llas5/view/login.html')
        from selenium.webdriver.support.select import Select
        Select(self.driver.find_element(By.ID, 'cCdSb')).select_by_visible_text('39/39_香川高等専門学校')
        self.driver.find_element(By.ID, 'doLogin').click()

    def input_order(self, order):
        self.driver.get('https://zaimu-kaikei.kosen-k.go.jp/llas5/view/financialAccounting/supply/purchaseRequestDetailsEntry.html')
        #配分中以外も表示
        self.driver.find_element(By.ID, 'hibnCheckYsn-1').click()
        #執行組織の変更
        self.driver.find_element(By.ID, 'select2-skkuSskYsn-1-container').click()
        self.driver.find_element(By.CLASS_NAME, 'select2-search__field').send_keys(order.organization)
        self.driver.find_element(By.XPATH, f'//li[contains(@title,"{order.organization}")]').click()
        #予算の選択
        self.driver.find_element(By.XPATH, f'//span[contains(text(),"{order.budget}")]').click()
        #各項目の入力
        self.driver.find_element(By.ID, 'select2-cCdNuhnPlc-container').click()
        self.driver.find_element(By.CLASS_NAME, 'select2-search__field').send_keys(order.place)
        self.driver.find_element(By.XPATH, f'//li[contains(@title,"{order.place}")]' ).click()
        self.driver.find_element(By.ID, 'cHnName').send_keys(order.item)
        self.driver.find_element(By.ID, 'cSu').send_keys(order.quantity)
        self.driver.find_element(By.ID, 'cTnk').send_keys(order.unit_price)
        #新規作成
        self.driver.find_element(By.ID, 'select2-skkuSskYsn-1-container').click()
        self.driver.find_element(By.ID, 'S_CreateNew').click()
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
