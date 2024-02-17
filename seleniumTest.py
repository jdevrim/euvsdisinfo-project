from selenium import webdriver
from selenium.webdriver.chrome.service import Service 
from selenium.webdriver.common.keys import Keys
import time

# https://sites.google.com/chromium.org/driver/
# Setup chrome driver
# Make sure correct driver is installed for OS and is in same location as the Python file
# Current driver is win64 version: 121.0.6167.184 (r1233107)
service = Service(executable_path="C:/Users/james/OneDrive/Desktop/Assignments/Project/Project/euvsdisinfo-project/chromedriver.exe")
options = webdriver.ChromeOptions()
options.add_experimental_option('excludeSwitches', ['enable-logging'])

# Initialize the driver with the service and options
driver = webdriver.Chrome(service=service, options=options)

driver.get("https://euvsdisinfo.eu/disinformation-cases/")
time.sleep(10)
