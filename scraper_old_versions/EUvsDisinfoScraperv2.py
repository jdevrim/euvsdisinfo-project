# Selenium (page navigation)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service 
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import NoSuchElementException, TimeoutException, NoSuchWindowException, WebDriverException

# Web scraping libraries
from bs4 import BeautifulSoup
import requests
import cloudscraper #https://pypi.org/project/cloudscraper/

import csv # Writing to CSV file
import undetected_chromedriver as uc # Undetected chrome driver from cloudflare systems
import time # For wait times (testing)
import math # Calculating pages
import pandas as pd # Preprocessing
import subprocess # Killing chrome

# Function to scrape the webpage
def scrape_page(driver):
    # Get the HTML content of the page 
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

    # Extract title and remove "Disinfo: " prefix 
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
        response_texts = []  # Initialise an empty list to hold parts of the response text
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

# Function to kill chrome after driver is complete
def kill_chrome():
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe', '/T'], check=True)
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe', '/T'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error killing chrome process: {e}")

# Driver setup with options 
options = ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--no-sandbox")
options.add_argument("--disable-gpu")
options.add_argument("--disable-javascript")
options.add_argument("--disable-extensions")
options.add_argument('--disable-blink-features=AutomationControlled')

# Initialise the driver with specified options
driver = uc.Chrome(options=options) 
print("Driver initialised...")

# Chromedriver options continued, working window size
driver.set_window_size(600, 600)

# Get database URL
base_url = "https://euvsdisinfo.eu/disinformation-cases/?view=grid&numberposts=60"
driver.get(base_url)
WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.b-archive__database-item")))

# Get the last page divided by two
# Fix for database breaking after reaching large page numbers
# Fixed by finding last page number (half) and sorting by oldest entry and repeating scrape
page_html = driver.page_source
page = BeautifulSoup(page_html, "html.parser")
pagination_items = page.select('a.b-pagination__item')[-1].get_text()  
last_page = int(pagination_items) if pagination_items.isdigit() else 1
half_page = math.ceil(last_page / 2)

scraped_data = []
sort_order = "descending"  # Start with descending order
page_num = 1
halfway_reached = False  # Flag to indicate if page has reached halfway
page_limit = 50  # Set the number of pages you want to scrape if there is a limit
pages_scraped = 0  # Track number of pages scraped
items_scraped = 0 # Track items scraped
scraped_urls = set() # Track scraped urls to avoid scraping the same pages

# Cookie catcher
try:
    wait = WebDriverWait(driver, 10)
    cookies = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.c-button")))
    driver.execute_script("arguments[0].click();", cookies)
    print("Cookies accepted")
except (NoSuchElementException, TimeoutException):
    print("Cookies not found")

try:
    while True:
        try:
            # Load the first or next page
            print(f"Scraping page {page_num} in {sort_order} order.")
            print(f"Total pages scraped: {pages_scraped}")
            print(f"Total items scraped: {items_scraped}")

            # Adjust URL based on current page number and sort order
            next_page_link = f"{base_url}&sort={sort_order}"
            if page_num > 1:
                next_page_link = f"https://euvsdisinfo.eu/disinformation-cases/page/{page_num}/?numberposts=60&view=grid&sort={sort_order}"

            # Navigate to the next page link
            driver.get(next_page_link)
            WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.b-archive__database-item")))
        
            # Find all items on the page
            items = driver.find_elements(By.CSS_SELECTOR, "a.b-archive__database-item")
            item_links = [item.get_attribute('href') for item in items]
            # Loop through each item and apply scraping logic
            for link in item_links:
                if link in scraped_urls:
                    print("Detected a repeated page...")
                    break
                try: 
                    scraped_urls.add(link) # Add link to set of URLs
                    driver.get(link) 
                    data = scrape_page(driver)  # Scrape function call
                    scraped_data.append(data)  # Append data to list
                    items_scraped += 1
                except Exception as e:
                    print(f"Error scraping {link}: {e}")
                finally:
                    driver.back()
                    WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.b-archive__database-item")))
            else:
                pages_scraped += 1 # Increment counters
                page_num += 1
            

            # Check for halfway mark (fix for database breaking)
            if page_num >= half_page and not halfway_reached:
                sort_order = "ascending"  # Switch to ascending order
                page_num = 1  # Restart from the first page
                halfway_reached = True  # Prevent further changes in sort order
                continue  # Skip the rest of the loop and start over with new sort order
            
            # Check for page limit
            if pages_scraped >= page_limit:
                print(f"Reached the page limit of {page_limit} pages for scraping.")
                break
        
            # Break the loop if there are no more pages to process
            if not items:
                print("No more pages to process...")
                break

        except TimeoutException:
            print(f"Timed out waiting for page {page_num} to load, skipping to next page.")
            page_num += 1 # Skip to next page
            continue

        except NoSuchWindowException:
            print("Browser window closed unexpectedly.")
            break

        except Exception as e:
            print(f"An unexpected error occurred")
            break

except WebDriverException as e:
    print(f"WebDriver encountered an issue: {e}")
except KeyboardInterrupt:
    print("Scraping interuptted by user, exiting...")
except Exception as e:
    print(f"An unexpected error occured: {e}")
finally:
    driver.quit()
    kill_chrome()
    print("Driver closed, scraping terminated...")

# Write the list of dictionaries to a CSV file
if scraped_data:
    try:
        print("Sorting and cleaning data...")
        keys = scraped_data[0].keys()  # Get the keys from the first item in the list
        with open('euvsdisinfo_data.csv', 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, keys)
            dict_writer.writeheader()
            dict_writer.writerows(scraped_data)

        # Preprocessing
        df = pd.read_csv('euvsdisinfo_data.csv')
        df = df.drop_duplicates()
        df.to_csv('euvsdisinfo_data.csv', index=False)
    except IndexError:
        print("No data was scraped. CSV file will not be created")
    except Exception as e:
        print(f"An unknown error occured while writing to CSV: {e}")
else:
    print("No data was scraped. CSV file will not be created")