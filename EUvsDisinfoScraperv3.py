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
from tkinter import ttk
from tkinter import Tk, messagebox, END
from tkcalendar import Calendar  # Start and end dates
import customtkinter as ctk # Custom UI
from CTkListbox import CTkListbox
import threading
from threading import Thread

import csv # Writing to CSV file
import undetected_chromedriver as uc # Undetected chromedriver from cloudflare systems
import time # For wait times (testing)
import math # Calculating pages
import datetime # For adjusting dates
import pandas as pd # Preprocessing
import subprocess # Killing chrome
import json # Open json files

class Scraper:
    def __init__(self, base_url):
        # Initialise URL
        self.base_url = base_url
        # Initialise scraping states
        self.scraping = False # For when scraper is currently running
        self.pause_event = threading.Event() # For pausing scrape
        self.scraped_data = [] # List to hold scraped data
        self.sort_order = "descending"  # Start with descending order
        self.page_num = 1 # Starting page number
        self.halfway_reached = False  # Flag to indicate if page has reached halfway
        self.pages_scraped = 0  # Track number of pages scraped
        self.items_scraped = 0 # Track items scraped
        self.max_items = None # User can set max items to scrape 
        self.scraped_urls = set() # Track scraped urls to avoid scraping the same pages

        # Initalise filters
        self.selected_countries = []  
        self.selected_languages = []
        self.selected_tags = []
        self.start_date = None
        self.end_date = None

        # Initialise driver with URL
        self.driver = self.setup_driver()
        self.driver.get(self.base_url)
        self.wait_for_elements("a.b-archive__database-item", 5)


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
        if self.driver:
            try:
                wait = WebDriverWait(self.driver, 10)
                cookies = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.c-button")))
                self.driver.execute_script("arguments[0].click();", cookies)
                print("Cookies accepted")
            except (NoSuchElementException, TimeoutException):
                print("Cookies not found")
        else:
            pass


    def pagnation_info(self):
        if self.driver:
            # Get the last page divided by two
            # Fix for database breaking after reaching large page numbers
            # Fixed by finding last page number (half) and sorting by oldest entry and repeating scrape
            page_html = self.driver.page_source
            page = BeautifulSoup(page_html, "html.parser")
            pagination_items = page.select('a.b-pagination__item')[-1].get_text()  
            last_page = int(pagination_items) if pagination_items.isdigit() else 1
            half_page = math.ceil(last_page / 2)
            return half_page
        else:
            pass        


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
    

    def wait_for_elements(self, css_selector, timeout):
        # Wait for elements to be present on page
        WebDriverWait(self.driver, timeout).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, css_selector)))
    

    def check_if_scraping(self):
        # This method should be as simple as possible.
        if not self.scraping or not self.driver:
            return False
        return True


    def run(self):
        self.scraping = True
        print("Starting scraper...")
        try:
            self.accept_cookies()
            half_page = self.pagnation_info()
            print("Cookies accepted and pagination info retrieved.")
        except Exception as e:
            print(f"Initialisation error: {e}")
            self.scraping = False
            return 
        try:
            while self.check_if_scraping():
                url_size_before_scraping = len(self.scraped_urls) 
                try:
                    # Load the first or next page
                    print(f"Scraping page {self.page_num} in {self.sort_order} order.")
                    print(f"Total pages scraped: {self.pages_scraped}")
                    print(f"Total items scraped: {self.items_scraped}")

                    # Adjust URL based on current page number, sort order, languages and tags.
                    # Construct URL components conditionally
                    params = []

                    # Date parameters
                    if self.start_date and self.end_date:
                        date_params = f"date={self.start_date}%20-%20{self.end_date}"
                        params.append(date_params)

                    # Country parameters
                    if self.selected_countries:
                        country_params = "&".join([f"disinfo_countries[]={code}" for code in self.selected_countries])
                        params.append(country_params)

                    # Language parameters
                    if self.selected_languages:
                        language_params = "&".join([f"disinfo_language[]={lang}" for lang in self.selected_languages])
                        params.append(language_params)

                    # Tag parameters
                    if self.selected_tags:
                        tag_params = "&".join([f"disinfo_keywords[]={tag}" for tag in self.selected_tags])
                        params.append(tag_params)

                    # Append sort order and construct the full URL
                    params.append(f"sort={self.sort_order}")
                    if params:
                        next_page_link = f"{self.base_url}&{'&'.join(params)}"
                    else:
                        next_page_link = self.base_url  # No additional parameters to add
                    
                    # Go to adjusted URL
                    print(f"Navigating to: {next_page_link}")
                    self.driver.get(next_page_link)
                    try:
                        self.wait_for_elements("a.b-archive__database-item", 3)
                    except TimeoutException:
                        self.scraping = False
                        print("No more pages to process...")
                        break

                    # Find all items on the page
                    items = self.driver.find_elements(By.CSS_SELECTOR, "a.b-archive__database-item")
                    # Break if no items found
                    if items is None or len(items) == 0:
                        self.scraping = False
                        print("No more pages to process...")
                        break
                    item_links = [item.get_attribute('href') for item in items]

                    # Loop through each item and apply scraping logic
                    for item in item_links:
                        print(f"Processing: {item}")
                        if not self.check_if_scraping():
                            self.scraping = False
                            break
                        if item in self.scraped_urls:
                            self.scraping = False
                            print("Detected a repeated page...")
                            break
                        try: 
                            self.scraped_urls.add(item) # Add item to set of URLs
                            self.driver.get(item) 
                            data = self.scrape_page()  # Scrape function call
                            self.scraped_data.append(data)  # Append data to list
                            self.items_scraped += 1
                        except Exception as e:
                            print(f"Error scraping {item}: {e}")
                        finally:
                            self.driver.back()
                            self.wait_for_elements("a.b-archive__database-item", 5)
                    else:
                        self.pages_scraped += 1 # Increment counters
                        self.page_num += 1
                    
                    # Break the loop if no new items were added
                    if len(self.scraped_urls) == url_size_before_scraping:
                        self.scraping = False
                        print("No new items found, ending scrape.")
                        break  
                    
                    # Check for halfway mark (fix for database breaking)
                    if self.page_num >= half_page and not self.halfway_reached:
                        self.sort_order = "ascending"  # Switch to ascending order
                        self.page_num = 1  # Restart from the first page
                        self.halfway_reached = True  # Prevent further changes in sort order
                        continue  # Skip the rest of the loop and start over with new sort order
                    
                    # Check for page limit
                    if self.pages_scraped >= self.page_limit:
                        self.scraping = False
                        print(f"Reached the page limit of {self.page_limit}...")
                        break
                
                # Error catching
                except TimeoutException:
                    print(f"Timed out waiting for page {self.page_num} to load, skipping to next page.")
                    self.page_num += 1 # Skip to next page
                    continue

                except NoSuchWindowException:
                    self.scraping = False
                    print("Browser window closed unexpectedly.")
                    break

                except Exception as e:
                    self.scraping = False
                    print(f"An unexpected error has occured {e}")
                    break
        
        except WebDriverException as e:
            self.scraping = False
            print(f"WebDriver encountered an issue: {e}")

        except KeyboardInterrupt:
            self.scraping = False
            print("Scraping interrupted by user, exiting...")

        except Exception as e:
            self.scraping = False
            print(f"An unexpected error occured: {e}")

        # Complete process
        finally:
            self.complete_scraping_process()
    

    def complete_scraping_process(self):
        self.save_data()  # Ensure data saving process is visible
        try:
            if self.driver:
                self.driver.quit()
                print("Driver closed.")
        except Exception as e:
            print(f"Exception during driver closure: {e}")
        finally:
            self.driver = None
            self.scraping = False
            print("Scraping terminated.")


class ScraperGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("EUvsDisinfo Scraper")
        
        # Empty scraper placeholder
        self.scraper = None
        self.scrape_thread = None

        # Start/Pause button
        self.start_pause_button = ctk.CTkButton(self.master, text="Start", command=self.start_pause)
        self.start_pause_button.pack(pady=10) 

        # Exit button
        self.exit_button = ctk.CTkButton(self.master, text="Kill", command=self.kill_scraping)
        self.exit_button.pack(pady=10)
        
        # Calendar for start date
        self.temp_start_date = None
        self.start_date_label = ctk.CTkLabel(master, text="Start Date")
        self.start_date_label.pack(pady=(10, 0))
        self.start_calendar = Calendar(master, selectmode='day')
        self.start_calendar.pack(pady=10)

        # Calendar for end date
        self.temp_end_date = None
        self.end_date_label = ctk.CTkLabel(master, text="End Date")
        self.end_date_label.pack(pady=(10, 0))
        self.end_calendar = Calendar(master, selectmode='day')
        self.end_calendar.pack(pady=10)

        # Button to set the dates
        self.set_date_button = ctk.CTkButton(self.master, text="Set Date", command=self.set_dates)
        self.set_date_button.pack(pady=10)

        # Dictionary attributes for storing JSON data
        self.countries = {}
        self.languages = {}
        self.tags = {}

        # Listboxes for filters
        self.countries_listbox = self.create_listbox('filter_codes/countryregion_codes.json', "Countries / Regions", 'countries')
        self.languages_listbox = self.create_listbox('filter_codes/language_codes.json', "Languages", 'languages')
        self.tags_listbox = self.create_listbox('filter_codes/tag_codes.json', "Tags", 'tags')


    def create_listbox(self, file_path, label_text, attribute_name):
        listbox_label = ctk.CTkLabel(self.master, text=label_text)
        listbox_label.pack(pady=(10, 0))  

        try:
            with open(file_path, 'r') as f:
                items = json.load(f)  # Load JSON data into the attribute
                setattr(self, attribute_name, items)
        except FileNotFoundError:
            print(f"Failed to load {label_text.lower()}, disabling selector.")
            items = {}  # Keep as empty dictionary if file not found
        except json.JSONDecodeError as e:
            print(f"JSON decode error in {file_path}: {e}")

        # Create the listbox
        listbox = CTkListbox(self.master, multiple_selection=True)
        for item in sorted(items.keys()):
            listbox.insert(tk.END, item)
        listbox.pack(pady=10)  

        if not items:
            listbox.configure(state='disabled')  # Disable listbox if items are not fetched
        return listbox


    def set_dates(self):
        date_format = "%m/%d/%y"
        start_date = datetime.datetime.strptime(self.start_calendar.get_date(), date_format)
        end_date = datetime.datetime.strptime(self.end_calendar.get_date(), date_format)

        new_format = "%d.%m.%Y"
        self.temp_start_date = start_date.strftime(new_format)
        self.temp_end_date = end_date.strftime(new_format)

        messagebox.showinfo("Date Set", f"Start Date: {self.temp_start_date}\nEnd Date: {self.temp_end_date}")


    def fetch_dates_to_scraper(self):
        if self.temp_start_date and self.temp_end_date:
            self.scraper.start_date = self.temp_start_date
            self.scraper.end_date = self.temp_end_date
        else:
            pass


    def fetch_set_selected_filters(self, filter_type):
        listbox = getattr(self, f"{filter_type}_listbox")
        selected_indices = listbox.curselection()
        items_dict = getattr(self, filter_type)
        selected_codes = [items_dict[listbox.get(i)] for i in selected_indices if listbox.get(i) in items_dict]
        setattr(self.scraper, f"selected_{filter_type}", selected_codes)


    def scrape_process(self):
        self.fetch_set_selected_filters("countries")
        self.fetch_set_selected_filters("languages")
        self.fetch_set_selected_filters("tags")
        self.fetch_dates_to_scraper()

        try:
            while self.scraper.scraping:
                self.scraper.run()
        except Exception as e:
            print(f"Error during scraping: {e}")
        finally:
            if self.scraper:
                self.scraper.complete_scraping_process()
            print("Scraping process has completed.")

    
    def start_pause(self):
        if self.scraper and self.scraper.scraping:
            # If currently scraping, pause the process
            self.scraper.scraping = False
            self.scraper.pause_event.clear()
            self.start_pause_button.configure(text="Start")
            print("Scraping paused...")
        else: 
            # If not scraping, start the process
            # Start scraper if not started
            if not self.scraper: 
                self.scraper = Scraper("https://euvsdisinfo.eu/disinformation-cases/?view=grid&numberposts=60")
            print("Starting scraping...")
            self.scraper.scraping = True
            self.scraper.pause_event.set()
            self.start_pause_button.configure(text="Pause")
            
            # Start the scraping process in a separate thread
            if not self.scrape_thread or not self.scrape_thread.is_alive():
                self.scrape_thread = Thread(target=self.scrape_process)
                self.scrape_thread.start()
            else:
                print("Scrape thread is already running.")


    def kill_scraping(self):
        # Kills the scraping process
        # Prompt for user confirmation before killing the scraping process
        if messagebox.askyesno("Confirm", "Are you sure you want to kill the scraper? This will lose all progress."):
            if self.scraper:
                    print("Killing scraper...")
                    self.scraper.scraping = False
                    self.scraper.pause_event.set()  # In case the scraping process is paused, ensure it resumes to properly terminate
                    
            # Wait for the scraping thread to finish if it's running
            if self.scrape_thread and self.scrape_thread.is_alive():
                self.scrape_thread.join()
            
            # Change the Start/Pause button text back to "Start"
            self.scraper.driver.quit()
            self.scraper = None
            self.start_pause_button.configure(text="Start")          


if __name__ == "__main__":
    root = ctk.CTk()
    app = ScraperGUI(root)
    root.mainloop()