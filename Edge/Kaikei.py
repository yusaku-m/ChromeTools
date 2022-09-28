from Browser import Browser

class Kaikei(Browser):
    def __init__(self, userdata_path):
        super().__init__(userdata_path)
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
