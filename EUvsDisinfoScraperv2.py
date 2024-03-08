# Selenium (page navigation)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service 
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Web scraping libraries
from bs4 import BeautifulSoup
import requests
import cloudscraper #https://pypi.org/project/cloudscraper/

import csv # Writing to CSV file
import undetected_chromedriver as uc # Undetected driver from cloudflare systems
import time # For wait times (testing)
import math # Calculating pages

# Function to scrape the webpage
def scrape_page(driver):
    # Get the HTML content of the page from Selenium
    page_html = driver.page_source

    # Parse the HTML content with BeautifulSoup
    page = BeautifulSoup(page_html, "html.parser")
    print("Processing:", driver.current_url)

    # Initialise a dictionary to hold the scraped data
    data = {
        "Title": None,
        "Outlet": None,
        "Date of publication": None,
        "Article language(s)": None,
        "Countries / regions discussed": None,
        "Summary": None,
        "Response": None
    }

    # Extract title and remove "Disinfo: " prefix if present
    raw_title = page.find('title').get_text().strip()
    data["Title"] = raw_title.replace('Disinfo: ', '')

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

options = ChromeOptions()
options.add_argument("--headless=new")

# Initialise the driver with the service and options
driver = uc.Chrome(options=options) # python3 -m pip install setuptools
print("Driver initialised")

# Chromedriver options (working lol)
driver.set_window_size(600, 600)

# Get database URL
base_url = "https://euvsdisinfo.eu/disinformation-cases/?numberposts=60&view=grid&sort=desc"
driver.get(base_url)
WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.b-archive__database-item")))

# Get the last page divided by two
# Fix for database breaking after reaching large page numbers
# Fixed by finding last page number (half) and sorting by oldest entry and repeating scrape
page_html = driver.page_source
page = BeautifulSoup(page_html, "html.parser")
pagination_items = page.select('a.b-pagination__item')[-1].get_text()  # Corrected variable name from soup to page
last_page = int(pagination_items) if pagination_items.isdigit() else 1
half_page = math.ceil(last_page / 2)
print(last_page)
print(half_page)

scraped_data = []
sort_order = "desc"  # Start with descending order
page_num = 1
halfway_reached = False  # Flag to indicate if halfway point has been reached
page_limit = 1  # Set the number of pages you want to scrape
pages_scraped = 0  # Initialize a counter to track the number of pages scraped

try:
    while True:
        # Adjust URL based on current page number and sort order
        next_page_link = f"{base_url}&sort={sort_order}"
        if page_num > 1:
            next_page_link = f"https://euvsdisinfo.eu/disinformation-cases/page/{page_num}/?numberposts=60&view=grid&sort={sort_order}"

        # Navigate to the next page link
        driver.get(next_page_link)
        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.b-archive__database-item")))

        items = driver.find_elements(By.CSS_SELECTOR, "a.b-archive__database-item")
        item_links = [item.get_attribute('href') for item in items]

        for link in item_links:
            driver.get(link)
            data = scrape_page(driver)  # Assuming you have implemented this function
            scraped_data.append(data)  # Assuming scraped_data is initialized before the loop
            driver.back()
            WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.b-archive__database-item")))

        pages_scraped += 1  # Increment the counter after processing each page

        if page_num >= half_page and not halfway_reached:
            sort_order = "asc"  # Switch to ascending order
            page_num = 1  # Restart from the first page
            halfway_reached = True  # Prevent further changes in sort order
            continue  # Skip the rest of the loop and start over with new sort order

        if pages_scraped >= page_limit:
            print(f"Reached the limit of {page_limit} pages for scraping.")
            break
       
        page_num += 1  # Increment the page number for the next iteration

        # Break the loop if there are no more pages to process
        if not items:
            print("No more pages to process.")
            break

finally:
    driver.quit()

# Write the list of dictionaries to a CSV file
keys = scraped_data[0].keys()  # Get the keys from the first item in the list
with open('scraped_data.csv', 'w', newline='', encoding='utf-8') as output_file:
    dict_writer = csv.DictWriter(output_file, keys)
    dict_writer.writeheader()
    dict_writer.writerows(scraped_data)
