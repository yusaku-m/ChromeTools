from Chrome.Browser import Browser
from selenium.webdriver.common.by import By

class GoogleCalender(Browser):
    def get_calender(self):
        self.driver.get('https://calendar.google.com/calendar/u/0/exporticalzip') 
        self.wait_download()
        self.calenderpass = './data/GoogleCalender'
        id = self.status.at['googleID', 'value']
        import shutil
        shutil.unpack_archive(f"./data/{id}@gmail.com.ical.zip", self.calenderpass)
        import os
        os.remove(f"./data/{id}@gmail.com.ical.zip")
        
    def set_id(self, id):
        self.open_status()
        self.set_status('googleID', id)
        self.save_status()