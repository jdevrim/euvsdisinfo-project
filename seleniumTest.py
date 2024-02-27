from selenium import webdriver
from selenium.webdriver.chrome.service import Service 
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import undetected_chromedriver as uc
import time

# https://sites.google.com/chromium.org/driver/
# Setup chrome driver
# Make sure correct driver is installed for OS and is in same location as the Python file
# Current driver is win64 version: 121.0.6167.184 (r1233107)

options = uc.ChromeOptions()
#options.add_argument("--headless")  # Uncomment if you want to run Chrome in headless mode
#options.add_argument('--window-size=1920,1080')
#options.add_argument('--enable-logging --v=1')

#service = Service(executable_path="C:/Users/james/OneDrive/Desktop/Assignments/Project/Project/euvsdisinfo-project/chromedriver.exe")
#driver = webdriver.Chrome(service=service, options=options)

driver = uc.Chrome(options=options) # python3 -m pip install setuptools

# Initialise the driver with the service and options
#driver = webdriver.Chrome(service=service, options=options)
print("Driver initialised")


base_url = "https://euvsdisinfo.eu/disinformation-cases/"
driver.get(base_url)

# Function to process each item
def process_item(item_url):
    driver.get(item_url)
    # Here you can add your scraping logic
    print("Processing:", item_url)
    time.sleep(2)  # Simulate processing time

try:
    page_num = 1  # Starting from the first page
    while True:        
        items = driver.find_elements(By.CSS_SELECTOR, "a.b-archive__database-item")
        item_links = [item.get_attribute('href') for item in items]

        for link in item_links:
            process_item(link)
            driver.back()
            time.sleep(1)  # Wait to ensure the list page has loaded
        
        # Attempt to go to the next page
        next_page_link = f"{base_url}page/{page_num + 1}/"
        driver.get(next_page_link)
        time.sleep(2)  # Wait for the next page to load

        # Check if the next page has items; if not, break the loop
        if not driver.find_elements(By.CSS_SELECTOR, "a.b-archive__database-item"):
            print("No more pages to process.")
            break
        
        page_num += 1

finally:
    driver.quit()
