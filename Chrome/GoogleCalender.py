from Chrome.Browser import Browser
from selenium.webdriver.common.by import By

class GoogleCalender(Browser):
    def get_calender(self):
        print("Accessing Google Calendar export URL...")
        self.driver.get('https://calendar.google.com/calendar/u/0/exporticalzip') 
        
        self.wait_download()
        
        id = self.status.at['googleID', 'value']
        zip_path = os.path.join("./data", f"{id}@gmail.com.ical.zip")
        extract_path = os.path.join("./data", "GoogleCalender")
        
        print(f"Extracting {zip_path} to {extract_path}...")
        
        import zipfile
        if os.path.exists(zip_path):
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            os.remove(zip_path)
            print("Google Calendar export successful.")
        else:
            print(f"Error: {zip_path} not found. Download might have failed.")
        
    def set_id(self, id):
        self.open_status()
        self.set_status('googleID', id)
        self.save_status()