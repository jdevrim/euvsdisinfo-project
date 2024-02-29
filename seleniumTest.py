# Selenium (page navigation)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service 
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Web Scraping libraries
from bs4 import BeautifulSoup
import requests
import cloudscraper #https://pypi.org/project/cloudscraper/

import csv # Writing to CSV file
import undetected_chromedriver as uc # Undetected driver from cloudflare systems
import time # For wait times (testing)

options = uc.ChromeOptions()
#options.add_argument("--headless=new")
#options.add_argument('--window-size=1920,1080')
#options.add_argument('--enable-logging --v=1')


# Initialise the driver with the service and options
driver = uc.Chrome(options=options) # python3 -m pip install setuptools
print("Driver initialised")

# Get database URL
base_url = "https://euvsdisinfo.eu/disinformation-cases/"
driver.get(base_url)

# Function to scrape the webpage
def scrape_page(driver):
    # Get the HTML content of the page from Selenium
    page_html = driver.page_source

    # Parse the HTML content with BeautifulSoup
    page = BeautifulSoup(page_html, "html.parser")
    print("Processing:", driver.current_url)

    # Initialise a dictionary to hold the scraped data
    data = {
        "Outlet": None,
        "Date of publication": None,
        "Article language(s)": None,
        "Countries / regions discussed": None,
        "Summary": None,
        "Response": None
    }

    # Iterate through each list item in the details list 
    # (Outlet, Date of Pub, Article Lang, Countries / Regions discussed)
    for li in page.select('.b-report__details-list li'):
        text = li.text.strip()
        if "Outlet:" in text:
            # The outlet name is contained within the first <a> tag following "Outlet:"
            data["Outlet"] = li.find('a').text.strip()
        elif "Date of publication:" in text:
            # The date is within a <span> tag following this text
            data["Date of publication"] = li.find('span').text.strip()
        elif "Article language(s):" in text:
            # The language(s) is within a <span> tag following this text
            data["Article language(s)"] = li.find('span').text.strip()
        elif "Countries / regions discussed:" in text:
            # The countries/regions are within a <span> tag following this text
            data["Countries / regions discussed"] = li.find('span').text.strip()

    # Extracting the SUMMARY
    summary_section = page.find('div', class_='b-report__summary')
    if summary_section:
        data["Summary"] = summary_section.find('div', class_='b-text').get_text(strip=True)

    # Extracting the RESPONSE
    response_section = page.find('div', class_='b-report__response')

    # Implement spaces in response text
    if response_section:
        response_texts = []  # Initialize an empty list to hold parts of the response text
        for child in response_section.find('div', class_='b-text').children:
            if child.name == 'a':
                # Append text from <a> tags with a leading space to ensure separation
                response_texts.append(' ' + child.get_text())
            elif child.name == 'p':
                # For <p> tags, extract the text, ensuring paragraphs are separated
                response_texts.append(child.get_text())
            elif child.name is None:
                # Directly append NavigableString objects
                response_texts.append(child)

    # Join the parts into a single string, ensuring spaces are correctly managed
    response_text = ' '.join(response_texts).replace('  ', ' ')
    data["Response"] = response_text.strip()

    return data 

scraped_data = []

try:
    page_num = 1  # Starting from the first page
    while True:        
        items = driver.find_elements(By.CSS_SELECTOR, "a.b-archive__database-item")
        item_links = [item.get_attribute('href') for item in items]

        for link in item_links:
            driver.get(link)
            data = scrape_page(driver)
            scraped_data.append(data)
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

# Write the list of dictionaries to a CSV file
keys = all_scraped_data[0].keys()  # Get the keys from the first item in the list
with open('scraped_data.csv', 'w', newline='', encoding='utf-8') as output_file:
    dict_writer = csv.DictWriter(output_file, keys)
    dict_writer.writeheader()
    dict_writer.writerows(all_scraped_data)
