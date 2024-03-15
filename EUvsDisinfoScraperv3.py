# Selenium (page navigation and driver)
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

# Tkinter GUI
import tkinter as tk
import threading
from threading import Thread

import csv # Writing to CSV file
import undetected_chromedriver as uc # Undetected chromedriver from cloudflare systems
import time # For wait times (testing)
import math # Calculating pages
import pandas as pd # Preprocessing
import subprocess # Killing chrome


class Scraper:
    def __init__(self, base_url, page_limit = 1):
        # Initialise scraping states
        self.scraping = False # For pausing scrape
        self.pause_event = threading.Event()
        self.base_url = base_url
        self.page_limit = page_limit  # Set max number of pages to scrape
        self.scraped_data = [] # List to hold scraped data
        self.sort_order = "descending"  # Start with descending order
        self.page_num = 1 # Starting page number
        self.halfway_reached = False  # Flag to indicate if page has reached halfway
        self.pages_scraped = 0  # Track number of pages scraped
        self.items_scraped = 0 # Track items scraped
        self.scraped_urls = set() # Track scraped urls to avoid scraping the same pages

        # Initialise driver with URL
        self.driver = self.setup_driver()


    def setup_driver(self):
        # Driver setup with detailed options
        # Options help with speed of driver by disabling chrome features
        options = ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-javascript")
        options.add_argument("--disable-extensions")
        options.add_argument('--disable-blink-features=AutomationControlled')

        # Initialise the driver with specified options
        self.driver = uc.Chrome(options=options) 

        # Chromedriver options continued, set window size
        self.driver.set_window_size(600, 600)
        print("Driver initialised...")
        
        return self.driver


    def scrape_page(self):
        # Get the HTML content of the page 
        page_html = self.driver.page_source

        # Parse the HTML content with BeautifulSoup
        page = BeautifulSoup(page_html, "html.parser")
        print("Processing:", self.driver.current_url)

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
                outlet_text = li.find('a').text.strip()
                # Removes unwanted text
                clean_outlet_text = outlet_text.replace("(opens in a new tab)", "").strip()
                data["Outlet"] = clean_outlet_text
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
            summary_text = summary_section.find('div', class_='b-text').get_text(strip=True)
            # Remove newlines and carriage returns from the summary text
            summary_text_cleaned = summary_text.replace('\n', ' ').replace('\r', ' ')
            data["Summary"] = summary_text_cleaned

        # Extracting the RESPONSE
        response_section = page.find('div', class_='b-report__response')
        if response_section:
            response_texts = []  # Initialise an empty list to hold parts of the response text
            for child in response_section.find('div', class_='b-text').children:
                text = ''
                if child.name == 'a':
                    # Get text from <a> tags and ensure separation
                    text = ' ' + child.get_text()
                elif child.name == 'p':
                    # Get text from <p> tags and ensure paragraphs are separated
                    text = child.get_text()
                elif child.name is None:
                    # Get text directly from NavigableString objects
                    text = str(child)
                
                # Clean text of any non-printing characters and extra spaces
                text_cleaned = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').strip()
                response_texts.append(text_cleaned)

        # Join the parts into a single string, ensuring spaces are correctly managed
        response_text = ' '.join(response_texts).replace('  ', ' ')
        data["Response"] = response_text

        return data


    def accept_cookies(self):
        try:
            wait = WebDriverWait(self.driver, 10)
            cookies = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.c-button")))
            self.driver.execute_script("arguments[0].click();", cookies)
            print("Cookies accepted")
        except (NoSuchElementException, TimeoutException):
            print("Cookies not found")


    def pagnation_info(self):
        # Get the last page divided by two
        # Fix for database breaking after reaching large page numbers
        # Fixed by finding last page number (half) and sorting by oldest entry and repeating scrape
        page_html = self.driver.page_source
        page = BeautifulSoup(page_html, "html.parser")
        pagination_items = page.select('a.b-pagination__item')[-1].get_text()  
        last_page = int(pagination_items) if pagination_items.isdigit() else 1
        half_page = math.ceil(last_page / 2)
        return half_page        


    def save_data(self):
        # Write the list of dictionaries to a CSV file
        if self.scraped_data:
            try:
                print("Sorting and cleaning data...")
                keys = self.scraped_data[0].keys()  # Get the keys from the first item in the list
                with open('euvsdisinfo.csv', 'w', newline='', encoding='utf-8-sig') as output_file:
                    dict_writer = csv.DictWriter(output_file, keys)
                    dict_writer.writeheader()
                    dict_writer.writerows(self.scraped_data)

                # Preprocessing
                df = pd.read_csv('euvsdisinfo.csv')
                df = df.drop_duplicates()
                df.to_csv('euvsdisinfo.csv', index=False, encoding='utf-8-sig')
            except IndexError:
                print("No data was scraped. CSV file will not be created")
            except Exception as e:
                print(f"An unknown error occured while writing to CSV: {e}")
        else:
            print("No data was scraped. CSV file will not be created")
    

    def wait_for_elements(self, css_selector, timeout = 10):
        # Wait for elements to be present on page
        WebDriverWait(self.driver, timeout).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, css_selector)))
    

    def check_if_scraping(self):
        # Check if scraping should continue
        if not self.scraping:
            self.pause_event.wait()
        return self.scraping


    def run(self):
        self.scraping = True
        # Get URL and open site
        self.driver.get(self.base_url)
        self.wait_for_elements("a.b-archive__database-item")

        # Accept cookies and get pagnation info.
        self.accept_cookies()
        half_page = self.pagnation_info()

        try:
            while self.check_if_scraping():
                try:
                    # Load the first or next page
                    print(f"Scraping page {self.page_num} in {self.sort_order} order.")
                    print(f"Total pages scraped: {self.pages_scraped}")
                    print(f"Total items scraped: {self.items_scraped}")

                    # Adjust URL based on current page number and sort order
                    next_page_link = f"{self.base_url}&sort={self.sort_order}"
                    if self.page_num > 1:
                        next_page_link = f"https://euvsdisinfo.eu/disinformation-cases/page/{self.page_num}/?numberposts=60&view=grid&sort={self.sort_order}"

                    # Navigate to the next page link
                    self.driver.get(next_page_link)
                    self.wait_for_elements("a.b-archive__database-item")
                
                    # Find all items on the page
                    items = self.driver.find_elements(By.CSS_SELECTOR, "a.b-archive__database-item")
                    item_links = [item.get_attribute('href') for item in items]
                    # Loop through each item and apply scraping logic
                    for link in item_links:
                        if not self.check_if_scraping():
                            break
                        if link in self.scraped_urls:
                            print("Detected a repeated page...")
                            break
                        try: 
                            self.scraped_urls.add(link) # Add link to set of URLs
                            self.driver.get(link) 
                            data = self.scrape_page()  # Scrape function call
                            self.scraped_data.append(data)  # Append data to list
                            self.items_scraped += 1
                        except Exception as e:
                            print(f"Error scraping {link}: {e}")
                        finally:
                            self.driver.back()
                            self.wait_for_elements("a.b-archive__database-item")
                    else:
                        self.pages_scraped += 1 # Increment counters
                        self.page_num += 1
                    

                    # Check for halfway mark (fix for database breaking)
                    if self.page_num >= half_page and not self.halfway_reached:
                        self.sort_order = "ascending"  # Switch to ascending order
                        self.page_num = 1  # Restart from the first page
                        self.halfway_reached = True  # Prevent further changes in sort order
                        continue  # Skip the rest of the loop and start over with new sort order
                    
                    # Check for page limit
                    if self.pages_scraped >= self.page_limit:
                        print(f"Reached the page limit of {self.page_limit}...")
                        break
                
                    # Break the loop if there are no more pages to process
                    if not items:
                        print("No more pages to process...")
                        break
                
                # Error catching
                except TimeoutException:
                    print(f"Timed out waiting for page {self.page_num} to load, skipping to next page.")
                    self.page_num += 1 # Skip to next page
                    continue

                except NoSuchWindowException:
                    print("Browser window closed unexpectedly.")
                    break

                except Exception as e:
                    print(f"An unexpected error has occured {e}")
                    break

        except WebDriverException as e:
            print(f"WebDriver encountered an issue: {e}")
        except KeyboardInterrupt:
            print("Scraping interrupted by user, exiting...")
        except Exception as e:
            print(f"An unexpected error occured: {e}")

        # Complete process
        finally:
            self.save_data()
            self.driver.quit()
            print("Driver closed, scraping terminated...")


class ScraperGUI:
    def __init__(self, master, scraper):
        self.master = master
        self.master.title("EUvsDisinfo Scraper")

        # Pass instance of the Scraper class
        self.scraper = scraper

        # Initialise scraper state
        self.scraping = False
        self.scrape_thread = None

        # Start/Pause button
        self.start_pause_button = tk.Button(self.master, text="Start", command=self.start_pause)
        self.start_pause_button.pack(pady=10) 

        # Exit button
        self.exit_button = tk.Button(self.master, text="Kill", command=self.kill_scraping)
        self.exit_button.pack(pady=10)


    def scrape_process(self):
        while self.scraper.scraping:
            self.scraper.run()
            
    
    def start_pause(self):
        if self.scraper.scraping:
            # If currently scraping, pause the process
            self.scraper.scraping = False
            self.scraper.pause_event.clear()
            self.start_pause_button.config(text="Start")
            print("Scraping paused...")
        else:
            # If not scraping, start the process
            print("Starting scraping...")
            self.scraper.scraping = True
            self.scraper.pause_event.set()
            self.start_pause_button.config(text="Pause")
            # Start the scraping process in a separate thread
            if not self.scrape_thread or not self.scrape_thread.is_alive():
                self.scrape_thread = Thread(target=self.scrape_process)
                self.scrape_thread.start()


    def kill_scraping(self):
        # Kills the scraping process
        self.scraper.scraping = False
        self.start_pause_button.config(text="Start")
        if self.scrape_thread and self.scrape_thread.is_alive():
            self.scrape_thread.join()


if __name__ == "__main__":
    root = tk.Tk()
    scraper = Scraper("https://euvsdisinfo.eu/disinformation-cases/?view=grid&numberposts=60")
    app = ScraperGUI(root, scraper)
    root.mainloop()
 